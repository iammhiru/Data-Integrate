"""
core/dedup.py
─────────────
Chống gửi trùng (dedup) — kế thừa nguyên tắc từ middleware Laird.

Ba cơ chế liên quan:

1. **Dedup cache (LRU)** — NodeId → khóa dedup của lần gửi gần nhất.
   Khóa = ``(normalized_value, timestamp)`` nếu
   ``USE_TIMESTAMP_IN_RECONNECT_DEDUP=True``, ngược lại chỉ ``(normalized_value,)``
   (change-detection: chỉ phát khi giá trị thực sự đổi).

2. **Baseline snapshot** — ngay sau khi subscribe, chụp giá trị hiện tại của
   mọi node và KHÔNG phát ra Kafka. Đây là nguồn nhiễu lớn nhất sau reconnect:
   Kepware gửi lại toàn bộ giá trị cũ ngay khi subscribe.

3. **EventId tất định (UUID v5)** — xem ``utils/event_id.py``. Đây là tầng
   dedup thứ hai, ở phía downstream (Flink/consume), không phụ thuộc state
   của Middleware.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Any

from config import settings

logger = logging.getLogger("industrial_telemetry.dedup")


def normalize_value(value: Any) -> Any:
    """Chuẩn hóa giá trị OPC UA về kiểu Python serializable (float → round 6)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return str(value)
    return value


def normalize_compare_value(value: Any) -> str:
    """
    Chuẩn hóa giá trị để so sánh dedup (không phân biệt hoa thường).

    Quy tắc (giữ nguyên từ middleware Laird):
      - ``bool``         → "1" / "0"
      - số 0/1          → "0" / "1"
      - chuỗi           → strip + casefold; "true"/"1" → "1", "false"/"0" → "0"
      - còn lại          → ``str(value).strip().casefold()``
    """
    normalized = normalize_value(value)
    if isinstance(normalized, bool):
        return "1" if normalized else "0"
    if isinstance(normalized, (int, float)) and normalized in (0, 1):
        return str(int(normalized))
    if isinstance(normalized, str):
        text = normalized.strip().casefold()
        if text in ("true", "1"):
            return "1"
        if text in ("false", "0"):
            return "0"
        return text
    return str(normalized).strip().casefold()


def build_dedup_key(value: Any, timestamp: int) -> tuple:
    """
    Dựng khóa dedup.

    - ``USE_TIMESTAMP_IN_RECONNECT_DEDUP=True``  → ``(value, timestamp)``
    - ``USE_TIMESTAMP_IN_RECONNECT_DEDUP=False`` → ``(value,)``
    """
    v_key = normalize_compare_value(value)
    if settings.USE_TIMESTAMP_IN_RECONNECT_DEDUP:
        return (v_key, int(timestamp))
    return (v_key,)


class DedupCache:
    """
    LRU cache các khóa dedup đã gửi, giới hạn ``NODE_CACHE_MAX`` entry.

    Thread-safe: dùng cho cả callback thread (ghi) và worker thread (đọc/ghi).
    """

    def __init__(self, max_size: int | None = None):
        self._max_size = max_size or settings.NODE_CACHE_MAX
        self._cache: "OrderedDict[str, tuple]" = OrderedDict()
        self._lock = threading.Lock()

    def is_duplicate(self, node_id: str, key: tuple) -> bool:
        """True nếu khóa này đã được gửi rồi."""
        with self._lock:
            return self._cache.get(node_id) == key

    def remember(self, node_id: str, key: tuple) -> None:
        """Ghi nhớ khóa vừa gửi (LRU eviction)."""
        with self._lock:
            if node_id in self._cache:
                self._cache.pop(node_id)
            self._cache[node_id] = key
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def check_and_remember(self, node_id: str, key: tuple) -> bool:
        """
        Kiểm tra trùng và ghi nhớ trong một lần khoá.

        Returns:
            True nếu TRÙNG (đã gửi rồi — caller nên bỏ qua).
            False nếu mới (caller nên gửi).
        """
        with self._lock:
            if self._cache.get(node_id) == key:
                # Đụng cache → đưa lên đầu (LRU).
                self._cache.move_to_end(node_id)
                return True
            if node_id in self._cache:
                self._cache.pop(node_id)
            self._cache[node_id] = key
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
            return False

    def clear(self) -> None:
        """Xóa toàn bộ cache (dùng sau reconnect)."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


class BaselineSnapshot:
    """
    Snapshot giá trị ngay sau subscribe, dùng để loại bỏ baseline replay.

    Vòng đời:
      1. ``mark_pending(node_id)`` cho mọi node vừa subscribe.
      2. Lần datachange đầu tiên của node đó: nếu giá trị khớp baseline
         → bỏ qua (không gửi Kafka). Nếu khác → gửi bình thường.
      3. Node nào không có baseline (đọc lỗi) → gửi bình thường.
    """

    def __init__(self, max_size: int | None = None):
        self._max_size = max_size or settings.NODE_CACHE_MAX
        self._snapshot: "OrderedDict[str, tuple]" = OrderedDict()
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def capture(self, node_id: str, key: tuple) -> None:
        """Ghi nhận giá trị baseline của node."""
        with self._lock:
            if node_id in self._snapshot:
                self._snapshot.pop(node_id)
            self._snapshot[node_id] = key
            while len(self._snapshot) > self._max_size:
                self._snapshot.popitem(last=False)
            self._pending.add(node_id)

    def is_baseline_replay(self, node_id: str, key: tuple) -> bool:
        """
        True nếu đây là lần gửi lại đúng giá trị baseline (nên bỏ qua).

        Side-effect: node bị đánh dấu "đã xử lý baseline" sau lần kiểm tra đầu tiên.
        """
        with self._lock:
            if node_id not in self._pending:
                return False
            self._pending.discard(node_id)
            return self._snapshot.get(node_id) == key

    def clear(self) -> None:
        with self._lock:
            self._snapshot.clear()
            self._pending.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._snapshot)
