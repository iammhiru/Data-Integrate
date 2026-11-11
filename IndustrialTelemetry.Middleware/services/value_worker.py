"""
services/value_worker.py
────────────────────────
Thread worker: lấy payload thô từ queue → normalize → dedup → gửi Kafka.

Kiến trúc (giữ nguyên từ middleware Laird):

    OPC UA callback thread ──put_nowait──▶ value_queue ──get──▶ ValueWorker
                                                              ├─ STABLE gate
                                                              ├─ dedup (LRU)
                                                              ├─ normalize
                                                              └─ producer.send()

Vì sao tách thread:
  - Callback thread của thư viện OPC UA phải luôn trả về nhanh. Nếu gửi Kafka
    ngay trong callback, một lần Kafka chậm sẽ chặn luồng callback → Kepware
    queue notification → cuối cùng bỏ dữ liệu.
  - Worker thread là nơi duy nhất chạm vào Kafka producer, nên producer không
    cần khoá.

Backpressure:
  - ``put_nowait`` → nếu queue đầy, event bị drop kèm log cảnh báo.
    Không bao giờ chặn luồng OPC UA.
"""

from __future__ import annotations

import logging
import queue
import threading
import time

from config import settings
from core.dedup import build_dedup_key
from core.subscription import SubscriptionRegistry
from services.normalizer import Normalizer

logger = logging.getLogger("industrial_telemetry.worker")


class ValueWorker:
    """
    Worker thread xử lý value queue và gửi Kafka.
    """

    def __init__(
        self,
        value_queue: queue.Queue,
        registry: SubscriptionRegistry,
        normalizer: Normalizer,
        publisher,
        connection_state,
    ):
        self._queue = value_queue
        self._registry = registry
        self._normalizer = normalizer
        self._publisher = publisher
        self._connection_state = connection_state

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._processed = 0
        self._skipped_state = 0
        self._skipped_dedup = 0
        self._skipped_baseline = 0
        self._failed = 0

    # ── enqueue (gọi từ OPC callback thread) ────────────────────────────────

    def enqueue(self, payload: dict) -> None:
        """
        Đẩy payload vào queue — KHÔNG chặn.

        Nếu queue đầy → drop event + log cảnh báo (đây là backpressure có chủ
        đích: giữ luồng OPC UA sống, chấp nhận mất dữ liệu hơn là mất toàn bộ).
        """
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            self._failed += 1
            logger.error(
                "[VALUE WORKER] Queue full (max=%d), dropped node=%s",
                settings.VALUE_QUEUE_MAXSIZE,
                payload.get("node_id"),
            )

    # ── lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> threading.Thread:
        """Khởi động worker thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="value-worker", daemon=True
        )
        self._thread.start()
        logger.info(
            "[VALUE WORKER] Started (queue_max=%d warn=%d)",
            settings.VALUE_QUEUE_MAXSIZE,
            settings.VALUE_QUEUE_WARN_THRESHOLD,
        )
        return self._thread

    def stop(self, timeout: float = 10.0) -> None:
        """Dừng worker thread (đợi tối đa ``timeout`` giây)."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            logger.info("[VALUE WORKER] Stopped")

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── main loop ───────────────────────────────────────────────────────────

    def _run(self) -> None:
        last_warn_mono = 0.0
        while not self._stop_event.is_set():
            try:
                payload = self._queue.get(
                    timeout=settings.VALUE_QUEUE_GET_TIMEOUT_SEC
                )
            except queue.Empty:
                continue

            try:
                self._process(payload)
            except Exception as exc:
                self._failed += 1
                logger.error(
                    "[VALUE WORKER] Unhandled error node=%s: %s",
                    payload.get("node_id"),
                    exc,
                )
            finally:
                self._queue.task_done()

            # Cảnh báo backlog (throttle 5s)
            qsize = self._queue.qsize()
            if qsize >= settings.VALUE_QUEUE_WARN_THRESHOLD:
                now = time.monotonic()
                if now - last_warn_mono >= 5:
                    last_warn_mono = now
                    logger.warning(
                        "[VALUE WORKER] Queue backlog high: size=%d / max=%d",
                        qsize,
                        settings.VALUE_QUEUE_MAXSIZE,
                    )

    # ── xử lý 1 payload ────────────────────────────────────────────────────

    def _process(self, payload: dict) -> None:
        node_id = payload["node_id"]
        tag_def = payload["tag_def"]
        value = payload["value"]
        force = bool(payload.get("force", False))

        if not tag_def.tag_code:
            logger.debug(
                "[VALUE WORKER] Skipped — empty tagCode node=%s", node_id
            )
            return

        # ── Cổng chặn trạng thái ─────────────────────────────────────────
        # Chỉ gửi khi kết nối STABLE. Dữ liệu lúc DEGRADED là nhiễu.
        if not force and not self._connection_state.should_publish():
            self._skipped_state += 1
            logger.debug(
                "[VALUE WORKER] Skipped (not STABLE): node=%s", node_id
            )
            return

        # ── Baseline replay ───────────────────────────────────────────────
        # Giá trị đầu tiên ngay sau subscribe = dữ liệu cũ Kepware gửi lại.
        from utils.time_utils import to_epoch_seconds

        timestamp = to_epoch_seconds(payload.get("source_timestamp"))
        dedup_key = build_dedup_key(value, timestamp)

        if not force and self._registry.baseline.is_baseline_replay(
            node_id, dedup_key
        ):
            self._skipped_baseline += 1
            logger.debug("[DEDUP] node=%s skip baseline replay", node_id)
            return

        # ── Dedup (giá trị không đổi → không phát lại) ───────────────────
        if not force:
            if self._registry.dedup.check_and_remember(node_id, dedup_key):
                self._skipped_dedup += 1
                logger.debug("[DEDUP] node=%s skip duplicate", node_id)
                return
        else:
            self._registry.dedup.remember(node_id, dedup_key)

        # ── Normalize ─────────────────────────────────────────────────────
        message = self._normalizer.normalize(
            tag_def=tag_def,
            value=value,
            source_timestamp=payload.get("source_timestamp"),
            server_timestamp=payload.get("server_timestamp"),
            quality_raw=payload.get("quality_raw"),
        )
        if message is None:
            return

        # ── Gửi Kafka ─────────────────────────────────────────────────────
        if self._publisher.send(message):
            self._processed += 1
            logger.info("[KAFKA] publish %s", Normalizer.preview(message))
        else:
            self._failed += 1

    # ── thống kê ────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        return {
            "processed": self._processed,
            "skipped_state": self._skipped_state,
            "skipped_dedup": self._skipped_dedup,
            "skipped_baseline": self._skipped_baseline,
            "failed": self._failed,
        }
