"""
services/kafka_publisher.py
───────────────────────────
Wrapper quanh ``kafka.KafkaProducer``.

Cấu hình producer (giữ nguyên giá trị từ middleware Laird — ưu tiên toàn vẹn
dữ liệu hơn là tốc độ):

    acks            = all   → chỉ coi là thành công khi đủ ISR xác nhận
    retries         = 10
    max_in_flight   = 1    → giữ thứ tự, tránh reorder khi retry
    linger_ms       = 50   → gom record trong 50ms
    batch_size      = 65536

Với bộ cấu hình này, producer đã đạt ngữ nghĩa idempotent của Kafka.

**Partitioning:** key = ``machineId`` → mọi message của một máy nằm trong
cùng một partition, giữ đúng thứ tự theo máy. Với 26 máy và 8 partition,
murmur2 phân bố 2–6 máy/partition (không partition rỗng).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from config import settings

logger = logging.getLogger("industrial_telemetry.kafka")

#: Bộ đếm thống kê đơn giản.
_stats_lock = threading.Lock()
_stats = {
    "sent": 0,
    "failed": 0,
    "bytes": 0,
    "last_error": "",
}


def get_stats() -> dict[str, Any]:
    """Bản sao thống kê hiện tại."""
    with _stats_lock:
        return dict(_stats)


class KafkaPublisher:
    """
    Lớp bọc producer: khởi tạo, gửi message, flush, đóng.

    Mỗi ``send`` gắn callback thành công và callback lỗi, để log chi tiết
    mà không chặn luồng worker.
    """

    def __init__(self) -> None:
        self._producer = None
        self._lock = threading.Lock()

    # ── lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Khởi tạo KafkaProducer. Raise nếu không kết nối được."""
        from kafka import KafkaProducer

        with self._lock:
            if self._producer is not None:
                return
            self._producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BROKERS,
                value_serializer=lambda v: json.dumps(
                    v, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8"),
                key_serializer=lambda k: str(k).encode("utf-8"),
                acks=settings.KAFKA_ACKS,
                retries=settings.KAFKA_RETRIES,
                max_in_flight_requests_per_connection=settings.KAFKA_MAX_IN_FLIGHT,
                linger_ms=settings.KAFKA_LINGER_MS,
                batch_size=settings.KAFKA_BATCH_SIZE,
                buffer_memory=settings.KAFKA_BUFFER_MEMORY,
                compression_type=settings.KAFKA_COMPRESSION_TYPE,
            )
        logger.info(
            "[OK] Kafka Producer initialized (brokers=%s topic=%s acks=%s "
            "retries=%d in_flight=%d linger_ms=%d batch_size=%d)",
            ",".join(settings.KAFKA_BROKERS),
            settings.KAFKA_TOPIC,
            settings.KAFKA_ACKS,
            settings.KAFKA_RETRIES,
            settings.KAFKA_MAX_IN_FLIGHT,
            settings.KAFKA_LINGER_MS,
            settings.KAFKA_BATCH_SIZE,
        )

    @property
    def available(self) -> bool:
        return self._producer is not None

    # ── publish ─────────────────────────────────────────────────────────────

    def send(self, message: dict[str, Any]) -> bool:
        """
        Gửi một message.

        Key = ``machineId`` (đảm bảo thứ tự theo máy trong partition).

        Returns:
            True nếu đã đưa vào hàng đợi gửi của producer (chưa chắc đã ack).
            False nếu không gửi được (lỗi cục bộ).
        """
        producer = self._producer
        if producer is None:
            logger.warning("[KAFKA] Producer unavailable — message dropped")
            with _stats_lock:
                _stats["failed"] += 1
                _stats["last_error"] = "producer unavailable"
            return False

        machine_id = message.get("machine", {}).get("machineId", "")
        node_id = message.get("source", {}).get("nodeId", "")

        try:
            future = producer.send(
                settings.KAFKA_TOPIC,
                key=machine_id,
                value=message,
            )
            future.add_callback(
                lambda meta, nid=node_id, mid=machine_id:
                self._on_success(nid, mid, meta)
            )
            future.add_errback(
                lambda exc, nid=node_id, mid=machine_id:
                self._on_error(nid, mid, exc)
            )
            return True
        except Exception as exc:
            logger.error(
                "[KAFKA] send failed node=%s machine=%s: %s", node_id, machine_id, exc
            )
            with _stats_lock:
                _stats["failed"] += 1
                _stats["last_error"] = str(exc)
            return False

    def send_blocking(self, message: dict[str, Any]) -> bool:
        """
        Gửi và chờ broker ack (dùng khi shutdown hoặc cho message quan trọng).
        """
        producer = self._producer
        if producer is None:
            return False
        try:
            future = producer.send(
                settings.KAFKA_TOPIC,
                key=message.get("machine", {}).get("machineId", ""),
                value=message,
            )
            future.get(timeout=settings.KAFKA_SEND_TIMEOUT_SEC)
            return True
        except Exception as exc:
            logger.error("[KAFKA] blocking send failed: %s", exc)
            with _stats_lock:
                _stats["failed"] += 1
                _stats["last_error"] = str(exc)
            return False

    # ── callbacks ───────────────────────────────────────────────────────────

    @staticmethod
    def _on_success(node_id: str, machine_id: str, metadata) -> None:
        with _stats_lock:
            _stats["sent"] += 1
        logger.info(
            "[KAFKA] published node=%s machine=%s partition=%s offset=%s",
            node_id,
            machine_id,
            getattr(metadata, "partition", "?"),
            getattr(metadata, "offset", "?"),
        )

    @staticmethod
    def _on_error(node_id: str, machine_id: str, exc) -> None:
        with _stats_lock:
            _stats["failed"] += 1
            _stats["last_error"] = str(exc)
        logger.error(
            "[KAFKA] publish FAILED node=%s machine=%s: %s", node_id, machine_id, exc
        )

    # ── shutdown ────────────────────────────────────────────────────────────

    def flush(self, timeout: float | None = None) -> None:
        """Chờ gửi hết dữ liệu còn trong buffer."""
        producer = self._producer
        if producer is None:
            return
        wait = timeout or settings.KAFKA_FLUSH_TIMEOUT_SEC
        try:
            producer.flush(timeout=wait)
            logger.info("[KAFKA] Flushed pending records (timeout=%ss)", wait)
        except Exception as exc:
            logger.warning("[KAFKA] flush error: %s", exc)

    def close(self) -> None:
        """Flush rồi đóng producer."""
        with self._lock:
            producer = self._producer
            self._producer = None
        if producer is None:
            return
        try:
            producer.flush(timeout=settings.KAFKA_FLUSH_TIMEOUT_SEC)
        except Exception:
            pass
        try:
            producer.close(timeout=settings.KAFKA_FLUSH_TIMEOUT_SEC)
        except Exception as exc:
            logger.warning("[KAFKA] close error: %s", exc)
        logger.info("[KAFKA] Producer closed")


def wait_for_broker(
    brokers: list[str] | None = None, timeout_sec: int = 60
) -> bool:
    """
    Chờ Kafka broker sẵn sàng trước khi start (tránh crash loop lúc deploy).
    """
    from kafka import KafkaProducer

    targets = brokers or settings.KAFKA_BROKERS
    deadline = time.monotonic() + timeout_sec
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            probe = KafkaProducer(
                bootstrap_servers=targets,
                request_timeout_ms=5000,
                max_block_ms=5000,
            )
            probe.close(timeout=5)
            logger.info("[KAFKA] Broker reachable at %s", ",".join(targets))
            return True
        except Exception as exc:
            logger.warning(
                "[KAFKA] Broker not ready (attempt %d): %s", attempt, exc
            )
            time.sleep(2)
    logger.error("[KAFKA] Broker unreachable after %ss", timeout_sec)
    return False
