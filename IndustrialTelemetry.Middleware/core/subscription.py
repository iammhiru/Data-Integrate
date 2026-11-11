"""
core/subscription.py
───────────────────
Quản lý OPC UA subscription:
  - ``SubscriptionRegistry``: lưu mapping NodeId ↔ tag info / node / quality
  - ``SubHandler``: callback datachange từ python-opcua
  - ``subscribe_all``: tạo subscription và subscribe toàn bộ tag
  - Baseline snapshot ngay sau subscribe để loại bỏ baseline replay

Cơ chế cốt lõi (giữ nguyên từ middleware Laird / Vinamilk):
  - Callback thread KHÔNG gửi Kafka trực tiếp — chỉ đẩy payload thô vào
    ``value_queue`` bằng ``put_nowait``. Nếu gửi trực tiếp, một lần Kafka
    chậm sẽ chặn luồng callback của thư viện OPC UA → Kepware bắt đầu queue
    notification và cuối cùng bỏ dữ liệu.
  - Sự kiện có quality Bad bị bỏ qua (trừ khi vừa phục hồi từ Bad → Good).
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Any

from config import settings
from core.dedup import BaselineSnapshot, DedupCache, build_dedup_key, normalize_value
from core.state_machine import OpcConnectionState
from core.tag_loader import TagDefinition
from utils.status_codes import is_bad_status, normalize_status_code

logger = logging.getLogger("industrial_telemetry.subscription")

try:  # pragma: no cover - phụ thuộc phiên bản thư viện
    from opcua.ua.uaerrors._base import UaError as OpcUaUaError
except ImportError:  # pragma: no cover

    class OpcUaUaError(Exception):
        pass


# ─── Registry (shared state) ────────────────────────────────────────────────


class SubscriptionRegistry:
    """
    Lưu toàn bộ mapping liên quan đến tag đang subscribe.

    Thread-safe: callback thread ghi, worker thread đọc.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()

        # NodeId → TagDefinition
        self.tag_by_node_id: dict[str, TagDefinition] = {}

        # NodeId → python-opcua Node object
        self.node_by_id: dict[str, Any] = {}

        # NodeId → quality text lần cuối cùng
        self.last_quality: dict[str, str] = {}

        # NodeId đã subscribe thành công
        self.valid: set[str] = set()

        # NodeId đã biết là không hợp lệ (BadNodeIdUnknown) — không thử lại
        self.invalid: set[str] = set()

        # Dedup cache: NodeId → dedup_key
        self.dedup = DedupCache()

        # Baseline snapshot ngay sau subscribe
        self.baseline = BaselineSnapshot()

    # ── lifecycle ───────────────────────────────────────────────────────────

    def register_tags(self, tags: list[TagDefinition]) -> None:
        """Nạp metadata tag vào registry (không đụng tới node/subscription)."""
        with self.lock:
            self.tag_by_node_id = {t.node_id: t for t in tags}

    def clear_nodes(self) -> None:
        """Xóa thông tin node/subscription (giữ nguyên tag metadata)."""
        with self.lock:
            self.node_by_id.clear()
            self.last_quality.clear()
            self.valid.clear()

    def clear_dedup(self) -> None:
        """Xóa dedup + baseline sau reconnect (timestamp nguồn đã đổi)."""
        self.dedup.clear()
        self.baseline.clear()
        logger.info("[DEDUP] Cache cleared after reconnect")

    def ok_ratio(self) -> float:
        """Tỷ lệ subscribe thành công (dùng cho cổng chặn STABLE)."""
        with self.lock:
            expected = [
                nid for nid in self.tag_by_node_id if nid not in self.invalid
            ]
            if not expected:
                return 1.0
            return sum(1 for nid in expected if nid in self.valid) / len(expected)

    def __len__(self) -> int:
        with self.lock:
            return len(self.tag_by_node_id)


# ─── Trích xuất dữ liệu từ DataValue ─────────────────────────────────────────


def extract_quality(data: Any) -> str | None:
    """Lấy StatusCode gốc từ notification."""
    try:
        monitored = getattr(data, "monitored_item", None)
        value = getattr(monitored, "Value", None) if monitored else None
        status = getattr(value, "StatusCode", None) if value is not None else None
        return str(status) if status is not None else None
    except Exception:
        return None


def extract_source_timestamp(data: Any) -> dt.datetime | None:
    """Lấy SourceTimestamp (timestamp nguồn — dùng cho eventId)."""
    try:
        monitored = getattr(data, "monitored_item", None)
        value = getattr(monitored, "Value", None) if monitored else None
        if value is not None:
            ts = getattr(value, "SourceTimestamp", None)
            if ts is not None:
                return ts
    except Exception:
        pass
    return None


def extract_server_timestamp(data: Any) -> dt.datetime | None:
    """Lấy ServerTimestamp (dùng để đo độ trễ)."""
    try:
        monitored = getattr(data, "monitored_item", None)
        value = getattr(monitored, "Value", None) if monitored else None
        if value is not None:
            ts = getattr(value, "ServerTimestamp", None)
            if ts is not None:
                return ts
    except Exception:
        pass
    return None


# ─── SubHandler ─────────────────────────────────────────────────────────────


class SubHandler:
    """
    Handler OPC UA datachange.

    Nhiệm vụ: nhận notification → kiểm tra chất lượng → đẩy payload thô vào
    ``value_queue``. KHÔNG chuẩn hóa, KHÔNG gửi Kafka ở đây.
    """

    def __init__(self, registry: SubscriptionRegistry, connection_state, enqueue):
        """
        Args:
            registry: SubscriptionRegistry dùng chung.
            connection_state: ConnectionState để cập nhật health.
            enqueue: callable(payload: dict) — hàm enqueue non-blocking.
        """
        self.registry = registry
        self.connection_state = connection_state
        self.enqueue = enqueue

    def datachange_notification(self, node, val, data) -> None:  # noqa: ANN001
        try:
            node_id = node.nodeid.to_string()
            tag_def = self.registry.tag_by_node_id.get(node_id)
            if tag_def is None:
                return

            force_publish = False

            # ── Quality tracking ─────────────────────────────────────────
            quality_raw = extract_quality(data)
            if quality_raw:
                prev = self.registry.last_quality.get(node_id)
                if prev != quality_raw:
                    label, _ = normalize_status_code(quality_raw)
                    logger.info(
                        "[QUALITY] node=%s %s -> %s",
                        node_id,
                        prev if prev is not None else "<none>",
                        label,
                    )
                    if label == "Good" and prev is not None:
                        prev_label, _ = normalize_status_code(prev)
                        if prev_label != "Good":
                            # Vừa phục hồi từ Bad/Uncertain → phát lại ngay.
                            force_publish = True
                            logger.info(
                                "[QUALITY RECOVERED] node=%s quality=%s", node_id, label
                            )
                            self.connection_state.set_state(
                                OpcConnectionState.STABLE,
                                f"quality recovered {node_id}",
                            )
                self.registry.last_quality[node_id] = quality_raw

            # ── Timestamp ─────────────────────────────────────────────────
            source_ts = extract_source_timestamp(data)
            server_ts = extract_server_timestamp(data)

            # ── Giá trị ───────────────────────────────────────────────────
            normalized = normalize_value(val)

            self.connection_state.note_datachange()

            # ── Bỏ qua khi quality Bad/Uncertain ──────────────────────────
            # Kepware mất kết nối → OPC UA báo quality Bad và value thường = 0.
            # Gửi giá trị 0 này sẽ làm downstream hiểu sai (counter reset, máy dừng).
            # Khi phục hồi (force_publish=True) giá trị thật sẽ được gửi lại ngay.
            if is_bad_status(quality_raw) and not force_publish:
                logger.debug(
                    "[QUALITY] node=%s bad quality — skip dispatch", node_id
                )
                return

            self.enqueue(
                {
                    "node_id": node_id,
                    "tag_def": tag_def,
                    "value": normalized,
                    "raw_value": val,
                    "source_timestamp": source_ts,
                    "server_timestamp": server_ts,
                    "quality_raw": quality_raw,
                    "force": force_publish,
                }
            )

        except Exception as exc:
            if "BadSessionClosed" in str(exc):
                logger.warning(
                    "[WARN] BadSessionClosed in datachange callback — triggering reconnect"
                )
                self.connection_state.note_error("datachange BadSessionClosed", exc)
            else:
                logger.error("[ERROR] SubHandler exception: %s", exc)
                if isinstance(exc, OpcUaUaError) or "UaError" in type(exc).__name__:
                    self.connection_state.note_error("datachange UA error", exc)


# ─── subscribe_all ──────────────────────────────────────────────────────────


def subscribe_all(client, tags: list[TagDefinition], registry: SubscriptionRegistry,
                  handler: SubHandler):
    """
    Tạo subscription mới và subscribe toàn bộ tag.

    Returns:
        (subscription, ok_count, fail_count)
    """
    sub = client.create_subscription(
        settings.OPC_SUB_PUBLISHING_INTERVAL_MS, handler
    )

    registry.clear_nodes()

    filtered = [t for t in tags if t.node_id not in registry.invalid]
    skipped = len(tags) - len(filtered)
    if skipped:
        logger.info("[SUBSCRIBE] Skipped %d known-invalid tag(s)", skipped)

    ok = fail = 0
    for tag_def in filtered:
        try:
            node = client.get_node(tag_def.node_id)
            registry.node_by_id[tag_def.node_id] = node
            registry.last_quality.pop(tag_def.node_id, None)
            sub.subscribe_data_change(node)
            registry.valid.add(tag_def.node_id)
            ok += 1
        except Exception as exc:
            fail += 1
            if "BadNodeIdUnknown" in str(exc) or "NodeIdUnknown" in str(exc):
                registry.invalid.add(tag_def.node_id)
                logger.warning(
                    "[SUBSCRIBE] BadNodeIdUnknown — marked invalid: %s", tag_def.node_id
                )
            else:
                logger.error(
                    "[ERROR] Subscribe failed %s: %s", tag_def.node_id, exc
                )

    logger.info(
        "[SUBSCRIBE] tags=%d attempted=%d ok=%d fail=%d invalid(cumulative)=%d",
        len(tags),
        len(filtered),
        ok,
        fail,
        len(registry.invalid),
    )
    return sub, ok, fail


def capture_baseline(registry: SubscriptionRegistry, node_id: str) -> None:
    """
    Đọc giá trị hiện tại của node để làm baseline.

    Mục đích: loại bỏ dữ liệu cũ Kepware gửi lại ngay khi subscribe — đây là
    nguồn nhiễu lớn nhất sau reconnect.
    """
    node = registry.node_by_id.get(node_id)
    if node is None:
        return
    try:
        data_value = node.get_data_value()
        if hasattr(data_value, "Value") and hasattr(data_value.Value, "Value"):
            raw = data_value.Value.Value
        else:
            raw = node.get_value()
        ts = getattr(data_value, "SourceTimestamp", None) or getattr(
            data_value, "ServerTimestamp", None
        )
        from utils.time_utils import to_epoch_seconds

        key = build_dedup_key(normalize_value(raw), to_epoch_seconds(ts))
        registry.baseline.capture(node_id, key)
    except Exception as exc:
        logger.warning("[BASELINE] Read failed node=%s: %s", node_id, exc)


def unsubscribe(subscription) -> None:
    """Xoá subscription (bỏ qua lỗi)."""
    if subscription is None:
        return
    try:
        subscription.delete()
    except Exception as exc:
        logger.warning("[SUBSCRIBE] subscription.delete failed: %s", exc)
