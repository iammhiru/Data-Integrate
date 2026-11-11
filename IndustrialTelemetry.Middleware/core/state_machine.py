"""
core/state_machine.py
─────────────────────
Máy trạng thái kết nối OPC UA + bộ điều khiển reconnect.

Sơ đồ trạng thái (giữ nguyên từ middleware Laird):

    CONNECTING ──▶ SUBSCRIBING ──▶ DEGRADED ──▶ STABLE
         ▲             │              │           │
         └─────────────┴──────────────┴───────────┘
                       RECONNECTING

Cổng chặn trạng thái (``should_publish``): chỉ gửi Kafka khi trạng thái là
``STABLE`` và kết nối còn active. Sự kiện phát ra lúc ``DEGRADED`` bị bỏ qua —
gửi dữ liệu khi kết nối chập chờn tạo nhiễu lớn hơn giá trị của nó.

ReconnectController:
  - **single-flight**: chỉ một chu kỳ reconnect chạy tại một thời điểm.
  - **backoff**: ``1s, 2s, 5s, 10s, 20s, 30s`` + jitter nhỏ.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from enum import Enum

from config import settings

logger = logging.getLogger("industrial_telemetry.state")

#: Các bước backoff giữ nguyên từ middleware hiện tại.
BACKOFF_STEPS: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 20.0, 30.0)

#: Jitter tối đa (giây) để tránh nhiều middleware reconnect đồng loạt.
JITTER_MAX_SEC = 1.0


class OpcConnectionState(str, Enum):
    CONNECTING = "CONNECTING"
    SUBSCRIBING = "SUBSCRIBING"
    STABLE = "STABLE"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"


class ConnectionState:
    """
    Giữ trạng thái kết nối + bộ đếm sức khoẻ.

    Thread-safe: nhiều thread (OPC callback, worker, main) cùng đọc/ghi.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = OpcConnectionState.CONNECTING
        self.active = False

        self._transport_error_streak = 0
        self._last_opc_error_mono = 0.0
        self._last_datachange_mono = 0.0
        self._had_any_datachange = False
        self._subscribe_ok_ratio = 1.0

    # ── state ───────────────────────────────────────────────────────────────

    @property
    def state(self) -> OpcConnectionState:
        with self._lock:
            return self._state

    def set_state(self, new_state: OpcConnectionState, detail: str = "") -> None:
        with self._lock:
            old = self._state
            if old == new_state:
                return
            self._state = new_state
        extra = f" ({detail})" if detail else ""
        logger.info("[STATE] %s -> %s%s", old.value, new_state.value, extra)

    def set_active(self, active: bool) -> None:
        with self._lock:
            self.active = active

    def should_publish(self) -> bool:
        """Cổng chặn: chỉ gửi Kafka khi STABLE và kết nối còn active."""
        with self._lock:
            return self._state == OpcConnectionState.STABLE and self.active

    # ── health counters ─────────────────────────────────────────────────────

    def note_error(self, source: str, err: BaseException | None = None) -> bool:
        """
        Ghi nhận lỗi transport/session.

        Returns:
            True nếu nên kích hoạt reconnect (đạt ngưỡng lỗi liên tiếp).
        """
        with self._lock:
            self._last_opc_error_mono = time.monotonic()
            self._transport_error_streak += 1
            streak = self._transport_error_streak
            self._state = OpcConnectionState.DEGRADED

        msg = f"{source}: {err!s}" if err is not None else source
        logger.warning(
            "[OPC] Error -> DEGRADED: %s | streak=%d/%d",
            msg,
            streak,
            settings.TRANSPORT_ERROR_THRESHOLD,
        )
        return streak >= settings.TRANSPORT_ERROR_THRESHOLD

    def note_datachange(self) -> None:
        """Ghi nhận hoạt động datachange; reset error streak."""
        with self._lock:
            self._last_datachange_mono = time.monotonic()
            self._had_any_datachange = True
            had_streak = self._transport_error_streak
            self._transport_error_streak = 0
        if had_streak:
            logger.info("[HEALTH] Transport error streak reset after datachange")

    def note_subscribe_ratio(self, ratio: float) -> None:
        with self._lock:
            self._subscribe_ok_ratio = ratio

    @property
    def subscribe_ok_ratio(self) -> float:
        with self._lock:
            return self._subscribe_ok_ratio

    def tick_stable(self) -> bool:
        """
        Thăng cấp lên STABLE nếu đủ điều kiện.

        Điều kiện: tỷ lệ subscribe ≥ ngưỡng VÀ đã yên lặng ≥ STABLE_QUIET_SECONDS.
        """
        with self._lock:
            if self._state != OpcConnectionState.DEGRADED:
                return False
            if self._subscribe_ok_ratio < settings.STABLE_MIN_SUBSCRIBE_RATIO:
                return False
            if time.monotonic() - self._last_opc_error_mono < settings.STABLE_QUIET_SECONDS:
                return False
            ratio = self._subscribe_ok_ratio
        self.set_state(
            OpcConnectionState.STABLE,
            f"ratio {ratio:.0%}, {settings.STABLE_QUIET_SECONDS}s without errors",
        )
        return True

    def tick_inactivity(self) -> int | None:
        """
        Guard an toàn: nếu lâu không có datachange → trả về số giây im lặng
        để caller kích hoạt reconnect. Trả None nếu chưa đủ điều kiện.
        """
        with self._lock:
            if not self.active:
                return None
            if not self._had_any_datachange:
                return None
            idle = time.monotonic() - self._last_datachange_mono
        if idle >= settings.INACTIVITY_TIMEOUT_S:
            return int(idle)
        return None

    def snapshot(self) -> dict:
        """Ảnh chụp trạng thái để log định kỳ."""
        with self._lock:
            now = time.monotonic()
            return {
                "state": self._state.value,
                "active": self.active,
                "streak": self._transport_error_streak,
                "last_datachange_age_s": (
                    int(now - self._last_datachange_mono)
                    if self._had_any_datachange
                    else -1
                ),
                "last_error_age_s": (
                    int(now - self._last_opc_error_mono)
                    if self._last_opc_error_mono
                    else -1
                ),
                "subscribe_ratio": round(self._subscribe_ok_ratio, 3),
            }


class ReconnectController:
    """
    Điều khiển chu kỳ reconnect (single-flight + exponential backoff).
    """

    _lock = threading.Lock()
    requested: bool = False
    in_progress: bool = False
    _backoff_idx: int = 0

    @classmethod
    def request(cls, reason: str) -> None:
        """Yêu cầu reconnect từ bất kỳ thread nào (bỏ qua nếu đang chạy)."""
        with cls._lock:
            if cls.in_progress:
                logger.info("[RECONNECT] Ignored (already in progress): %s", reason)
                return
            cls.requested = True
        logger.warning("[RECONNECT] Requested: %s", reason)

    @classmethod
    def enter(cls) -> bool:
        """
        Bắt đầu chu kỳ reconnect.

        Returns:
            False nếu đã có reconnect đang chạy (caller nên bỏ qua).
        """
        with cls._lock:
            if cls.in_progress:
                return False
            cls.in_progress = True
            return True

    @classmethod
    def leave(cls, success: bool) -> None:
        """Kết thúc chu kỳ reconnect; reset backoff nếu thành công."""
        with cls._lock:
            cls.in_progress = False
            if success:
                cls._backoff_idx = 0
                cls.requested = False

    @classmethod
    def is_requested(cls) -> bool:
        with cls._lock:
            return cls.requested

    @classmethod
    def clear_request(cls) -> None:
        """Xoá cờ yêu cầu reconnect (dùng sau khi kết nối thành công)."""
        with cls._lock:
            cls.requested = False
            cls._backoff_idx = 0

    @classmethod
    def backoff_and_wait(cls) -> float:
        """
        Tăng backoff và ngủ trước khi thử lại.

        Returns:
            Số giây đã ngủ.
        """
        with cls._lock:
            wait = BACKOFF_STEPS[min(cls._backoff_idx, len(BACKOFF_STEPS) - 1)]
            cls._backoff_idx = min(cls._backoff_idx + 1, len(BACKOFF_STEPS) - 1)
            cls.requested = True
        actual = wait + random.uniform(0, JITTER_MAX_SEC)
        logger.warning("[RECONNECT] Backoff %.1fs before retry", actual)
        time.sleep(actual)
        return actual
