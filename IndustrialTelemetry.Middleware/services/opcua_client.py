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

import logging
import threading
import time

from config import settings
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
