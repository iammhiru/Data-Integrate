"""
main.py
───────
Entry point của IndustrialTelemetry.Middleware.

Luồng:
    KEPWARE (OPC UA)  ──subscription──▶  SubHandler
                                            │ put_nowait
                                            ▼
                                       value_queue
                                            │ get
                                            ▼
                                       ValueWorker
                                            ├─ STABLE gate
                                            ├─ dedup (LRU + baseline)
                                            ├─ Normalizer (message chuẩn)
                                            └─ KafkaProducer.send(key=machineId)
                                                     │
                                                     ▼
                                          Kafka: industrial.telemetry
                                          8 partitions, key=machineId

Vòng lặp chính (main thread) chỉ làm 3 việc:
  1. Kick off kết nối OPC UA (và retry với backoff nếu chưa được).
  2. Định kỳ tick: thăng cấp STABLE, kiểm tra inactivity, log thống kê.
  3. Xử lý tín hiệu dừng (Ctrl+C / SIGTERM) → shutdown sạch.

Chế độ giả lập (``SIMULATION_MODE=true``):
  - KHÔNG tạo OpcUaService, KHÔNG kết nối Kepware.
  - ``SimulatedSource`` sinh dữ liệu cho toàn bộ tag rồi đẩy vào **cùng**
    ``value_queue`` → message ra Kafka giống hệt chế độ thật.
"""

from __future__ import annotations

import logging
import queue
import signal
import sys
import threading
import time

from config import settings
from config.logging_config import setup_logging
from core.equipment_map import EquipmentMap
from core.state_machine import ConnectionState, OpcConnectionState, ReconnectController
from core.subscription import SubscriptionRegistry
from core.tag_loader import load_all_tags
from services.kafka_publisher import KafkaPublisher, get_stats, wait_for_broker
from services.normalizer import Normalizer
from services.opcua_client import OpcUaService
from services.simulator import SimulatedSource
from services.value_worker import ValueWorker

logger = logging.getLogger("industrial_telemetry.main")

_shutdown_event = threading.Event()


def _handle_signal(signum, _frame) -> None:
    name = signal.Signals(signum).name
    logger.warning("[STOP] Signal received: %s", name)
    _shutdown_event.set()


def _load_metadata() -> tuple[EquipmentMap, list]:
    """Nạp equipment_map + tag CSV. Raise nếu lỗi."""
    equipment_map = EquipmentMap.load()
    tags = load_all_tags()

    if not tags:
        raise RuntimeError(
            f"No tags loaded from {settings.TAG_FOLDER} — check TAG_FOLDER setting"
        )

    # Cảnh báo nếu có device trong CSV chưa có trong equipment_map.
    channel_devices = {t.channel_device for t in tags}
    missing = equipment_map.missing_keys(channel_devices)
    if missing:
        logger.warning(
            "[MAIN] %d device(s) in CSV missing from equipment_map.json: %s",
            len(missing),
            ", ".join(missing[:10]),
        )

    # Cảnh báo nếu có máy trong equipment_map nhưng không có tag.
    known = equipment_map.known_keys()
    orphan = sorted(known - channel_devices)
    if orphan:
        logger.warning(
            "[MAIN] %d machine(s) in equipment_map.json have no CSV: %s",
            len(orphan),
            ", ".join(orphan[:10]),
        )

    return equipment_map, tags


def _print_banner(tags: list, equipment_map: EquipmentMap) -> None:
    """In tổng quan cấu hình lúc khởi động."""
    channels = sorted({t.channel for t in tags})
    logger.info("=" * 72)
    logger.info("IndustrialTelemetry.Middleware")
    if settings.SIMULATION_MODE:
        logger.info("  MODE            : SIMULATION (không dùng Kepware)")
        logger.info("  Source system   : %s", settings.SIMULATION_SOURCE_SYSTEM)
        logger.info("  Tick / speed    : %dms / x%.2f",
                    settings.SIMULATION_TICK_MS,
                    settings.SIMULATION_SPEED_FACTOR)
    else:
        logger.info("  OPC UA server   : %s", settings.OPC_SERVER_URL)
    logger.info("  Kafka brokers   : %s", ",".join(settings.KAFKA_BROKERS))
    logger.info("  Kafka topic     : %s", settings.KAFKA_TOPIC)
    logger.info("  Tag folder      : %s", settings.TAG_FOLDER)
    logger.info("  Equipment map   : %s", settings.EQUIPMENT_MAP_FILE)
    logger.info("  Machines        : %d", len(equipment_map))
    logger.info("  Channels        : %s", ", ".join(channels))
    logger.info("  Tags            : %d", len(tags))
    logger.info("  Schema version  : %s", settings.SCHEMA_VERSION)
    logger.info("  Event type      : %s", settings.EVENT_TYPE)
    logger.info("=" * 72)


def main() -> int:
    setup_logging()
    settings.validate()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("[START] IndustrialTelemetry.Middleware starting...")

    # ── 1. Metadata ────────────────────────────────────────────────────────
    try:
        equipment_map, tags = _load_metadata()
    except Exception as exc:
        logger.error("[START] Failed to load metadata: %s", exc)
        return 2

    _print_banner(tags, equipment_map)

    # ── 2. Kafka ───────────────────────────────────────────────────────────
    if not wait_for_broker(timeout_sec=60):
        logger.error("[START] Kafka broker unreachable — aborting")
        return 3

    publisher = KafkaPublisher()
    try:
        publisher.start()
    except Exception as exc:
        logger.error("[START] Kafka producer init failed: %s", exc)
        return 3

    # ── 3. Queues + worker ─────────────────────────────────────────────────
    value_queue: queue.Queue = queue.Queue(maxsize=settings.VALUE_QUEUE_MAXSIZE)
    registry = SubscriptionRegistry()
    registry.register_tags(tags)

    # Chế độ giả lập: nguồn dữ liệu là simulator, không có OPC UA.
    source_system = (
        settings.SIMULATION_SOURCE_SYSTEM if settings.SIMULATION_MODE
        else settings.SOURCE_SYSTEM
    )
    normalizer = Normalizer(equipment_map, source_system=source_system)

    connection_state = ConnectionState()

    if settings.SIMULATION_MODE:
        # Cổng STABLE mở sẵn — không có kết nối nào để "chờ yên lặng".
        connection_state.set_state(OpcConnectionState.STABLE, "simulation mode")
        connection_state.set_active(True)

        worker = ValueWorker(
            value_queue=value_queue,
            registry=registry,
            normalizer=normalizer,
            publisher=publisher,
            connection_state=connection_state,
        )
        worker.start()

        simulator = SimulatedSource(tags=tags, enqueue=worker.enqueue)
        simulator.start()
        logger.info("[START] Simulation mode ON — dữ liệu giả lập đang chạy.")
        return _run_simulation_loop(worker, value_queue, simulator, publisher)

    # ── Chế độ thật: kết nối Kepware ───────────────────────────────────────
    opc_service = OpcUaService(
        registry=registry,
        tags_provider=lambda: load_all_tags(),
    )
    worker = ValueWorker(
        value_queue=value_queue,
        registry=registry,
        normalizer=normalizer,
        publisher=publisher,
        connection_state=opc_service.connection_state,
    )
    opc_service.set_worker(worker)
    opc_service.install_log_handler()
    worker.start()

    # ── 4. Kết nối OPC UA (có retry/backoff) ───────────────────────────────
    connected = False
    attempt = 0
    while not _shutdown_event.is_set() and not connected:
        attempt += 1
        try:
            connected = opc_service.connect_and_subscribe()
        except Exception as exc:
            logger.error("[START] Connect attempt %d failed: %s", attempt, exc)
            connected = False
        if not connected:
            ReconnectController.backoff_and_wait()

    if not connected:
        logger.error("[START] Could not establish OPC UA connection — aborting")
        worker.stop()
        publisher.close()
        return 4

    # Kết nối thành công → xoá cờ reconnect tồn dư từ các lần thử trước,
    # nếu không vòng chính sẽ tự kích hoạt một chu kỳ reconnect vô nghĩa.
    ReconnectController.clear_request()

    # ── 5. Vòng lặp chính ──────────────────────────────────────────────────
    logger.info("[START] Middleware running. Press Ctrl+C to stop.")
    last_stats_mono = time.monotonic()

    while not _shutdown_event.is_set():
        time.sleep(0.5)

        # Thăng cấp DEGRADED → STABLE
        opc_service.tick_stable()

        # Guard im lặng
        opc_service.tick_inactivity()

        # Xử lý yêu cầu reconnect (kèm backoff nếu thất bại)
        if ReconnectController.is_requested():
            opc_service.reconnect_with_backoff()

        # Log thống kê định kỳ
        now = time.monotonic()
        if now - last_stats_mono >= settings.STATS_INTERVAL_SEC:
            last_stats_mono = now
            _log_stats(opc_service, worker, value_queue)

    # ── 6. Shutdown ────────────────────────────────────────────────────────
    logger.info("[STOP] Shutting down...")
    opc_service.disconnect()
    worker.stop(timeout=15)
    publisher.flush()
    publisher.close()
    logger.info("[STOP] Middleware stopped.")
    return 0


def _run_simulation_loop(
    worker: ValueWorker,
    value_queue: queue.Queue,
    simulator: SimulatedSource,
    publisher: KafkaPublisher,
) -> int:
    """Vòng lặp chính của chế độ giả lập — chỉ log thống kê + chờ tín hiệu dừng."""
    logger.info("[START] Middleware running (simulation). Press Ctrl+C to stop.")
    last_stats_mono = time.monotonic()

    while not _shutdown_event.is_set():
        time.sleep(0.5)
        now = time.monotonic()
        if now - last_stats_mono >= settings.STATS_INTERVAL_SEC:
            last_stats_mono = now
            _log_stats(None, worker, value_queue)

    # ── Shutdown ───────────────────────────────────────────────────────────
    logger.info("[STOP] Shutting down (simulation)...")
    simulator.stop()
    worker.stop(timeout=15)
    publisher.flush()
    publisher.close()
    logger.info("[STOP] Middleware stopped.")
    return 0


def _log_stats(opc_service: OpcUaService, worker: ValueWorker, value_queue: queue.Queue) -> None:
    """Log ảnh chụp trạng thái định kỳ."""
    if opc_service is not None:
        health = opc_service.connection_state.snapshot()
        state_txt = health["state"]
        active_txt = str(health["active"])
    else:
        state_txt = "SIMULATION"
        active_txt = "True"
    wstats = worker.stats()
    kstats = get_stats()
    logger.info(
        "[STATS] state=%s active=%s queue=%d/%d "
        "published=%d skipped(dedup=%d baseline=%d state=%d) failed=%d kafka(sent=%d err=%d)",
        state_txt,
        active_txt,
        value_queue.qsize(),
        settings.VALUE_QUEUE_MAXSIZE,
        wstats["processed"],
        wstats["skipped_dedup"],
        wstats["skipped_baseline"],
        wstats["skipped_state"],
        wstats["failed"],
        kstats["sent"],
        kstats["failed"],
    )


if __name__ == "__main__":
    sys.exit(main())
