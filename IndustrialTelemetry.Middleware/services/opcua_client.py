"""
services/opcua_client.py
────────────────────────
Quản lý vòng đời kết nối OPC UA: connect → subscribe → theo dõi sức khoẻ →
reconnect khi cần.

Chu kỳ reconnect (hard reset) — giữ nguyên từ middleware Laird:

  1. subscription.delete() → client.disconnect()
  2. Xóa cache node, xóa dedup cache
  3. Tạo Client mới, session_timeout = 600000
  4. Nạp lại tag từ metadata
  5. Subscribe hàng loạn, đếm tỷ lệ thành công
  6. Chụp baseline snapshot
  7. Vào DEGRADED, chờ đủ STABLE_QUIET_SECONDS không lỗi → STABLE

Backoff: 1s → 2s → 5s → 10s → 20s → 30s (giữ ở mức cuối), kèm jitter nhỏ.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import time

from config import settings
from core.dedup import normalize_value
from core.state_machine import (
    ConnectionState,
    OpcConnectionState,
    ReconnectController,
)
from core.subscription import (
    SubscriptionRegistry,
    SubHandler,
    capture_baseline,
    subscribe_all,
    unsubscribe,
)
from utils.status_codes import is_bad_status

logger = logging.getLogger("industrial_telemetry.opcua")

#: Marker trong log của thư viện opcua báo session/channel đã chết.
_FATAL_LOG_MARKERS = (
    "BadTcpSecureChannelUnknown",
    "No future object found",
    "BadSessionClosed",
    "UaError",
)


class _OpcUaFatalLogHandler(logging.Handler):
    """
    Bắt log lỗi từ thư viện ``opcua`` để kích hoạt reconnect.

    python-opcua đôi khi không ném exception ra ngoài mà chỉ log ra
    ``BadTcpSecureChannelUnknown`` — nếu không bắt, middleware sẽ treo im lặng.
    """

    def __init__(self, connection_state: ConnectionState):
        super().__init__()
        self._connection_state = connection_state

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if not any(marker in msg for marker in _FATAL_LOG_MARKERS):
                return
            if self._connection_state.note_error("OPC UA library fatal log"):
                ReconnectController.request("OPC UA library fatal log")
        except Exception:
            self.handleError(record)


class OpcUaService:
    """
    Service quản lý kết nối OPC UA và chu kỳ subscribe/reconnect.
    """

    def __init__(self, registry: SubscriptionRegistry, tags_provider):
        """
        Args:
            registry: SubscriptionRegistry dùng chung.
            tags_provider: callable() -> list[TagDefinition] — nạp lại tag từ
                           metadata. Được gọi lại ở MỖI chu kỳ reconnect,
                           nên nếu file CSV có đổi (thêm/bớt tag) thì tag mới
                           sẽ được subscribe sau lần reconnect kế tiếp.

                           ⚠️ KHÔNG có cơ chế hot-reload tự động: sửa CSV
                           không kích hoạt subscribe ngay — phải restart
                           middleware hoặc chờ một chu kỳ reconnect.
        """
        self._registry = registry
        self._tags_provider = tags_provider

        self.connection_state = ConnectionState()
        self._client = None
        self._subscription = None
        self._client_lock = threading.Lock()
        self._log_handler_installed = False

        #: Đã hoàn thành ít nhất một chu kỳ subscribe chưa?
        #: Chu kỳ đầu tiên luôn được coi là STABLE (xem connect_and_subscribe).
        self._first_cycle_done = False

        #: Mốc thời gian lần refresh gần nhất (monotonic) — cho cơ chế
        #: periodic refresh (đọc lại tag tĩnh).
        self._last_refresh_mono = 0.0

        #: Con trỏ xoay vòng qua danh sách tag khi refresh (0 = bắt đầu).
        self._refresh_cursor = 0

    # ── log handler ─────────────────────────────────────────────────────────

    def install_log_handler(self) -> None:
        """Cài handler bắt lỗi fatal từ log của thư viện opcua."""
        if self._log_handler_installed:
            return
        handler = _OpcUaFatalLogHandler(self.connection_state)
        handler.setLevel(logging.WARNING)
        logging.getLogger("opcua").addHandler(handler)
        self._log_handler_installed = True

    # ── connect ─────────────────────────────────────────────────────────────

    def _connect(self):
        """Tạo client mới và kết nối. Raise nếu thất bại."""
        from opcua import Client

        client = Client(settings.OPC_SERVER_URL)
        client.session_timeout = settings.OPC_SESSION_TIMEOUT_MS
        client.connect()
        logger.info("[OK] Connected to OPC UA server: %s", settings.OPC_SERVER_URL)
        return client

    def connect_and_subscribe(self) -> bool:
        """
        Kết nối + subscribe toàn bộ tag + chụp baseline.

        Returns:
            True nếu thành công.
        """
        self.connection_state.set_state(OpcConnectionState.CONNECTING)
        tags = self._tags_provider()
        if not tags:
            logger.error("[OPC] No tags loaded — cannot subscribe")
            return False

        self._registry.register_tags(tags)

        try:
            client = self._connect()
        except Exception as exc:
            logger.error("[OPC] Connect failed: %s", exc)
            self.connection_state.set_state(
                OpcConnectionState.DEGRADED, f"connect failed: {exc}"
            )
            return False

        self.connection_state.set_state(OpcConnectionState.SUBSCRIBING)

        # ── Cổng chặn STABLE ─────────────────────────────────────────────
        # Với PUBLISH_INITIAL_SNAPSHOT, mở cổng TRƯỚC khi subscribe:
        # nếu không, lô datachange đầu tiên (mà ta muốn phát) sẽ tới lúc
        # connection_state vẫn còn ở SUBSCRIBING / active=False → bị cổng
        # chặn bỏ qua.
        #
        # An toàn: đây là chu kỳ khởi động đầu tiên, subscribe ratio chưa biết,
        # nhưng chỉ gate theo state — mọi tag đều có quality Good từ Kepware.
        if settings.PUBLISH_INITIAL_SNAPSHOT and not self._first_cycle_done:
            self.connection_state.set_state(
                OpcConnectionState.STABLE,
                "initial snapshot publish — gate open",
            )
            self.connection_state.set_active(True)

        handler = SubHandler(
            registry=self._registry,
            connection_state=self.connection_state,
            enqueue=self._enqueue,
        )

        try:
            subscription, ok, fail = subscribe_all(
                client, tags, self._registry, handler
            )
        except Exception as exc:
            logger.error("[OPC] Subscribe failed: %s", exc)
            self.connection_state.note_error("subscribe", exc)
            try:
                client.disconnect()
            except Exception:
                pass
            return False

        # Tỷ lệ subscribe — CHỈ tính trên các tag KHÔNG bị invalid.
        #
        # Lưu ý: phải loại tag BadNodeIdUnknown khỏi mẫu số, nếu không tỷ lệ
        # luôn thấp và cổng chặn STABLE không bao giờ mở. Cả 2 middleware tham
        # khảo đều làm đúng điều này:
        #   - Laird : recompute_subscribe_gate_ratio() → expected = tags - invalid
        #   - Vinamilk: SubscriptionRegistry.ok_ratio()   → expected = tags - invalid
        ratio = self._registry.ok_ratio()
        self.connection_state.note_subscribe_ratio(ratio)

        with self._client_lock:
            self._client = client
            self._subscription = subscription

        # ── Baseline snapshot ────────────────────────────────────────────
        # Chụp giá trị hiện tại của mọi node, KHÔNG phát ra Kafka. Loại bỏ
        # nguồn nhiễu lớn nhất sau reconnect.
        #
        # Ngoại lệ (PUBLISH_INITIAL_SNAPSHOT=True): ở chu kỳ khởi động ĐẦU
        # TIÊN, ta KHÔNG chụp baseline — để lần datachange đầu tiên của mỗi
        # node được phát đi ngay. Nhờ vậy dashboard có trạng thái hiện tại của
        # toàn bộ máy ngay khi bật, thay vì phải chờ giá trị đổi lần đầu.
        #
        # Sau reconnect (first_cycle_done=True) cơ chế chặn baseline replay vẫn
        # hoạt động bình thường để không phát lại lô giá trị cũ.
        if settings.PUBLISH_INITIAL_SNAPSHOT and not self._first_cycle_done:
            logger.info(
                "[OPC] PUBLISH_INITIAL_SNAPSHOT=true — bo qua chan baseline "
                "replay cho chu ky khoi dong dau tien"
            )
        else:
            for tag_def in tags:
                if tag_def.node_id in self._registry.valid:
                    capture_baseline(self._registry, tag_def.node_id)

        self.connection_state.set_active(True)

        if not self._first_cycle_done:
            # Chu kỳ khởi động đầu tiên: coi là STABLE ngay.
            #
            # Lý do: tag thật chưa được tạo đầy đủ trong Kepware là chuyện
            # bình thường lúc setup. Chặn STABLE theo tỷ lệ subscribe ở chu
            # kỳ đầu sẽ khiến middleware không gửi được gì lên Kafka, dù các
            # tag đã subscribe thành công đều có dữ liệu tốt.
            #
            # Cả 2 middleware tham khảo đều có cùng hành vi này:
            #   - Laird  : "first startup cycle completed" → STABLE
            #   - Vinamilk: "first startup cycle"            → STABLE
            self._first_cycle_done = True
            self.connection_state.set_state(
                OpcConnectionState.STABLE,
                "first startup cycle completed",
            )
        else:
            self.connection_state.set_state(
                OpcConnectionState.DEGRADED,
                f"subscribed {ok}/{len(tags)} (ratio {ratio:.0%} of valid tags)",
            )
        logger.info(
            "[OPC] Subscription established: %d tag(s), ratio=%.0f%%",
            len(tags),
            ratio * 100,
        )
        return True

    # ── reconnect ───────────────────────────────────────────────────────────

    def reconnect_cycle(self) -> bool:
        """
        Một chu kỳ reconnect đầy đủ (hard reset).

        Trả về True nếu kết nối lại thành công.
        """
        if not ReconnectController.enter():
            return False

        success = False
        try:
            self.connection_state.set_state(OpcConnectionState.RECONNECTING)
            logger.info("[RECONNECT] Start")

            # 1. Dọn tài nguyên cũ
            self._teardown()

            # 2. Xóa dedup cache (timestamp nguồn đã đổi)
            self._registry.clear_dedup()
            self._registry.clear_nodes()

            # 3–7. Connect → subscribe → baseline → DEGRADED
            success = self.connect_and_subscribe()

            if success:
                logger.info("[RECONNECT] End OK")
            else:
                logger.warning("[RECONNECT] End FAILED")
            return success
        except Exception as exc:
            logger.error("[RECONNECT] Unexpected error: %s", exc)
            return False
        finally:
            # Luôn gỡ cờ in_progress để không kẹt vòng reconnect.
            ReconnectController.leave(success)

    def reconnect_with_backoff(self) -> bool:
        """
        Chu kỳ reconnect kèm backoff.

        Nếu kết nối thất bại → ngủ theo lịch backoff ``1→2→5→10→20→30s`` rồi
        thử lại ở lần gọi sau. Nếu không có backoff ở đây, vòng chính sẽ gọi
        liên tục không ngừng → busy loop, dễ làm sập Kepware.

        Returns:
            True nếu kết nối lại thành công.
        """
        if ReconnectController.in_progress:
            # Một chu kỳ khác đang chạy → không cần backoff thêm.
            return False

        success = self.reconnect_cycle()
        if not success:
            ReconnectController.backoff_and_wait()
        return success

    def _teardown(self) -> None:
        """Xóa subscription và disconnect client (bỏ qua lỗi)."""
        with self._client_lock:
            subscription = self._subscription
            client = self._client
            self._subscription = None
            self._client = None

        self.connection_state.set_active(False)

        unsubscribe(subscription)
        if client is not None:
            try:
                client.disconnect()
            except Exception as exc:
                logger.warning("[OPC] Disconnect error (ignored): %s", exc)

    # ── health loop ─────────────────────────────────────────────────────────

    def tick_stable(self) -> None:
        """Thăng cấp DEGRADED → STABLE nếu đủ điều kiện."""
        self.connection_state.tick_stable()

    def tick_inactivity(self) -> None:
        """Guard an toàn: im lặng quá lâu → reconnect."""
        idle = self.connection_state.tick_inactivity()
        if idle is not None:
            ReconnectController.request(
                f"No datachange for {idle}s "
                f"(threshold={settings.INACTIVITY_TIMEOUT_S}s)"
            )

    # ── periodic refresh ───────────────────────────────────────────────────

    def tick_refresh(self) -> None:
        """
        Đọc lại giá trị hiện tại của các tag theo chu kỳ.

        VÌ SAO CẦN:
          Subscription chỉ báo khi giá trị THAY ĐỔI. Với tag tĩnh (máy dừng,
          counter đứng yên), không có datachange nào → `eventTime` của bản ghi
          cũ dần "hết hạn" → dashboard hiển thị NO_DATA dù kết nối hoàn hảo.

          Cơ chế này đọc lại node (giống polling của OPC UA client thông
          thường) và đẩy vào đúng hàng đợi, đúng đường ống như datachange.
          Dedup vẫn hoạt động bình thường: chỉ khi timestamp nguồn/giá trị
          thực sự khác mới phát.

        Chạy ở thread chính (vòng tick 0.5s), mỗi lần chỉ đọc tối đa
        ``REFRESH_BATCH_SIZE`` node để không tắc cổng chặn STABLE quá lâu.
        """
        if settings.REFRESH_INTERVAL_S <= 0:
            return

        now = time.monotonic()
        if now - self._last_refresh_mono < settings.REFRESH_INTERVAL_S:
            return
        self._last_refresh_mono = now

        if not self.connection_state.should_publish():
            return

        client = self._client
        if client is None:
            return

        tag_defs = self._tags_provider()
        if not tag_defs:
            return

        # Xoay vòng qua các tag để không bao giờ đọc hết 404 node trong 1 lượt.
        total = len(tag_defs)
        batch = min(settings.REFRESH_BATCH_SIZE, total)
        start = self._refresh_cursor % total
        selected = [tag_defs[(start + i) % total] for i in range(batch)]
        self._refresh_cursor = (start + batch) % total

        now_utc = dt.datetime.now(tz=dt.timezone.utc)
        sent = 0
        for tag_def in selected:
            node = self._registry.node_by_id.get(tag_def.node_id)
            if node is None:
                continue
            try:
                dv = node.get_data_value()
                raw = dv.Value.Value if dv is not None and dv.Value is not None else None
                # StatusCode nằm ở cấp DataValue (không phải ở trong Variant).
                status = dv.StatusCode if dv is not None else None
                ts = dv.SourceTimestamp if dv is not None else None
            except Exception as exc:  # noqa: BLE001
                logger.debug("[REFRESH] Read failed node=%s: %s", tag_def.node_id, exc)
                continue

            if raw is None:
                continue

            # Bỏ qua giá trị quality Bad/Uncertain — giống SubHandler, để
            # không phát ra giá trị 0 gây hiểu sai (counter reset, máy dừng).
            if is_bad_status(status):
                continue

            # Timestamp nguồn: ưu tiên SourceTimestamp của Kepware (Kepware
            # cập nhật nó ở MỖI lần scan, kể cả khi giá trị không đổi) → nhờ đó
            # eventTime của bản ghi vẫn "sống" dù tag tĩnh.
            src_ts = ts or now_utc

            self._enqueue(
                {
                    "node_id": tag_def.node_id,
                    "tag_def": tag_def,
                    "value": normalize_value(raw),
                    "raw_value": raw,
                    "source_timestamp": src_ts,
                    "server_timestamp": now_utc,
                    "quality_raw": status,
                    "force": False,
                }
            )
            sent += 1

        if sent:
            logger.info("[REFRESH] Re-read %d/%d tag(s)", sent, total)

    def request_reconnect(self, reason: str) -> None:
        """Yêu cầu reconnect từ bất kỳ thread nào."""
        ReconnectController.request(reason)

    def note_error(self, source: str, exc: BaseException | None = None) -> None:
        """Ghi nhận lỗi; tự reconnect nếu đạt ngưỡng."""
        if self.connection_state.note_error(source, exc):
            ReconnectController.request(
                f"Transport error threshold reached "
                f"({settings.TRANSPORT_ERROR_THRESHOLD}): {source}"
            )

    # ── enqueue bridge ──────────────────────────────────────────────────────

    def _enqueue(self, payload: dict) -> None:
        """Được SubHandler gọi — forward sang value worker."""
        worker = self._worker
        if worker is not None:
            worker.enqueue(payload)

    #: Value worker, gán sau khi khởi tạo (tránh phụ thuộc vòng).
    _worker = None

    def set_worker(self, worker) -> None:
        self._worker = worker

    # ── shutdown ────────────────────────────────────────────────────────────

    def disconnect(self) -> None:
        self._teardown()
