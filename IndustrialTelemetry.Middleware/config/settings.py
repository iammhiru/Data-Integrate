"""
config/settings.py
──────────────────
Tải và validate toàn bộ cấu hình từ biến môi trường / file .env.

Nguyên tắc: KHÔNG module nào đọc os.getenv trực tiếp. Tất cả tập trung ở đây
để dễ kiểm soát và dễ deploy (chỉ cần đổi .env, không sửa code).
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv là dependency nhưng không bắt buộc
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False

load_dotenv()

#: Thư mục gốc của project middleware (IndustrialTelemetry.Middleware/).
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


# ─── helpers ────────────────────────────────────────────────────────────────

def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _int(key: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(key, str(default))))
    except (TypeError, ValueError):
        return default


def _float(key: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(key, str(default))))
    except (TypeError, ValueError):
        return default


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _path(key: str, default: str) -> Path:
    raw = os.getenv(key, default).strip()
    path = Path(raw)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


# ─── OPC UA ──────────────────────────────────────────────────────────────────

OPC_SERVER_URL: str = _str("OPC_SERVER_URL", "opc.tcp://localhost:49320")
OPC_SUB_PUBLISHING_INTERVAL_MS: int = _int("OPC_SUB_PUBLISHING_INTERVAL_MS", 100, minimum=10)
OPC_SESSION_TIMEOUT_MS: int = _int("OPC_SESSION_TIMEOUT_MS", 600_000, minimum=10_000)

# ─── Metadata (đọc kiểu Vinamilk: TAG_FOLDER/<Channel>/<Device>.csv) ─────────

#: Thư mục gốc chứa <Channel>/<Device>.csv
TAG_FOLDER: Path = _path("TAG_FOLDER", "metadata/TAG_FOLDER")

#: JSON map: "Channel.Device" → metadata máy
EQUIPMENT_MAP_FILE: Path = _path("EQUIPMENT_MAP_FILE", "metadata/equipment_map.json")

#: File catalog đầy đủ (tuỳ chọn — dùng cho validation và sinh tài liệu)
CATALOG_FILE: Path = _path("CATALOG_FILE", "metadata/catalog.json")

#: Bỏ qua tag không có TagCode khi load (tag chưa cấu hình nghiệp vụ)
REQUIRE_TAG_CODE: bool = _bool("REQUIRE_TAG_CODE", True)

# ─── Kafka ───────────────────────────────────────────────────────────────────

KAFKA_BROKERS: list[str] = [
    b.strip() for b in _str("KAFKA_BROKERS", "localhost:9092").split(",") if b.strip()
]
KAFKA_TOPIC: str = _str("KAFKA_TOPIC", "industrial.telemetry")
KAFKA_ACKS: str = _str("KAFKA_ACKS", "all")
KAFKA_RETRIES: int = _int("KAFKA_RETRIES", 10, minimum=0)
KAFKA_MAX_IN_FLIGHT: int = _int("KAFKA_MAX_IN_FLIGHT", 1, minimum=1)
KAFKA_LINGER_MS: int = _int("KAFKA_LINGER_MS", 50, minimum=0)
KAFKA_BATCH_SIZE: int = _int("KAFKA_BATCH_SIZE", 65536, minimum=1024)
KAFKA_BUFFER_MEMORY: int = _int("KAFKA_BUFFER_MEMORY", 33554432, minimum=1024)
KAFKA_COMPRESSION_TYPE: str = _str("KAFKA_COMPRESSION_TYPE", "gzip")
KAFKA_SEND_TIMEOUT_SEC: int = _int("KAFKA_SEND_TIMEOUT_SEC", 30, minimum=1)
#: Timeout chờ ack khi flush/shutdown.
KAFKA_FLUSH_TIMEOUT_SEC: int = _int("KAFKA_FLUSH_TIMEOUT_SEC", 10, minimum=1)

# ─── Data contract ───────────────────────────────────────────────────────────

#: version của schema message — tăng khi thêm/bớt trường.
SCHEMA_VERSION: str = _str("SCHEMA_VERSION", "1.0")

#: eventType duy nhất của hệ thống.
EVENT_TYPE: str = _str("EVENT_TYPE", "machine.telemetry")

#: Hệ thống nguồn ghi trong source.system.
SOURCE_SYSTEM: str = _str("SOURCE_SYSTEM", "kepware")

# ─── Value queue ─────────────────────────────────────────────────────────────

VALUE_QUEUE_MAXSIZE: int = _int("VALUE_QUEUE_MAXSIZE", 200_000, minimum=1_000)
VALUE_QUEUE_WARN_THRESHOLD: int = _int("VALUE_QUEUE_WARN_THRESHOLD", 50_000, minimum=1)
VALUE_QUEUE_GET_TIMEOUT_SEC: int = _int("VALUE_QUEUE_GET_TIMEOUT_SEC", 1, minimum=1)

# ─── Dedup ───────────────────────────────────────────────────────────────────

#: Số entry tối đa trong LRU dedup cache.
NODE_CACHE_MAX: int = _int("NODE_CACHE_MAX", 50_000, minimum=100)

#: True  → dedup key = (value, timestamp): cùng giá trị nhưng timestamp khác vẫn gửi.
#: False → dedup key = (value,): gửi chỉ khi giá trị thực sự đổi.
#:
#: Baseline của design doc là change-detection (chỉ phát khi giá trị đổi) vì
#: eventId được sinh từ nội dung sự kiện — nếu gửi lặp lại giá trị không đổi
#: với timestamp khác nhau thì eventId khác nhau và dedup downstream vô nghĩa.
USE_TIMESTAMP_IN_RECONNECT_DEDUP: bool = _bool(
    "USE_TIMESTAMP_IN_RECONNECT_DEDUP", False
)

# ─── Connection health ───────────────────────────────────────────────────────

#: Nếu không có datachange trong khoảng này (giây) → kích hoạt reconnect.
INACTIVITY_TIMEOUT_S: int = _int("INACTIVITY_TIMEOUT_S", 600, minimum=30)

#: Số lỗi transport liên tiếp trước khi reconnect.
TRANSPORT_ERROR_THRESHOLD: int = _int("TRANSPORT_ERROR_THRESHOLD", 3, minimum=1)

#: Thời gian yên lặng (không lỗi OPC UA) trước khi thăng lên STABLE.
STABLE_QUIET_SECONDS: int = _int("STABLE_QUIET_SECONDS", 10, minimum=0)

#: Tỷ lệ subscribe thành công tối thiểu để được coi là STABLE.
STABLE_MIN_SUBSCRIBE_RATIO: float = _float("STABLE_MIN_SUBSCRIBE_RATIO", 0.90, minimum=0.0)

# ─── Simulation mode (giả lập — KHÔNG cần Kepware) ──────────────────────────

#: True → middleware KHÔNG kết nối Kepware, tự sinh dữ liệu giả lập cho toàn bộ
#: tag trong TAG_FOLDER rồi gửi vào Kafka đúng data contract.
#: Dùng cho máy của đồng đội không cài được Kepware.
SIMULATION_MODE: bool = _bool("SIMULATION_MODE", False)

#: Nhịp quét của simulator (ms) — nhịp kiểm tra xem tag nào đã đến hạn phát.
SIMULATION_TICK_MS: int = _int("SIMULATION_TICK_MS", 200, minimum=10)

#: Hệ số tốc độ mô phỏng — 1.0 = thời gian thực, 10.0 = nhanh gấp 10.
SIMULATION_SPEED_FACTOR: float = _float("SIMULATION_SPEED_FACTOR", 1.0, minimum=0.01)

#: Scan Rate mặc định (ms) cho tag không khai báo trong CSV.
SIMULATION_DEFAULT_SCAN_MS: int = _int("SIMULATION_DEFAULT_SCAN_MS", 1000, minimum=10)

#: Seed cho RNG — cùng seed ⇒ cùng chuỗi dữ liệu (tiện cho test).
SIMULATION_SEED: int = _int("SIMULATION_SEED", 20261111, minimum=0)

#: Tỷ lệ phát lỗi chất lượng giả lập (0 = luôn Good).
#: 0.01 → 1% Bad, 1% Uncertain, 98% Good.
SIMULATION_QUALITY_FAULT_RATE: float = _float(
    "SIMULATION_QUALITY_FAULT_RATE", 0.01, minimum=0.0
)

#: Ghi trong source.system — "simulator" khi chạy chế độ giả lập.
SIMULATION_SOURCE_SYSTEM: str = _str("SIMULATION_SOURCE_SYSTEM", "simulator")

# ─── Logging ─────────────────────────────────────────────────────────────────

LOGS_DIR: Path = _path("LOGS_DIR", "logs")
LOG_MAX_FILES: int = _int("LOG_MAX_FILES", 7, minimum=1)
LOG_FILE_LEVEL: str = _str("LOG_FILE_LEVEL", "INFO").upper()
LOG_CONSOLE_LEVEL: str = _str("LOG_CONSOLE_LEVEL", "INFO").upper()
OPCUA_LOG_LEVEL: str = _str("OPCUA_LOG_LEVEL", "WARNING").upper()

# ─── Chống trùng lặp giữa các instance ──────────────────────────────────────

#: Ghi log mỗi N giây về tình trạng queue + số message đã gửi.
STATS_INTERVAL_SEC: int = _int("STATS_INTERVAL_SEC", 60, minimum=5)


def validate() -> None:
    """Kiểm tra cấu hình bắt buộc; raise nếu thiếu hoặc sai."""
    errors: list[str] = []

    if not OPC_SERVER_URL and not SIMULATION_MODE:
        errors.append("OPC_SERVER_URL is required")
    if not KAFKA_BROKERS:
        errors.append("KAFKA_BROKERS is required")
    if not KAFKA_TOPIC:
        errors.append("KAFKA_TOPIC is required")
    if not TAG_FOLDER:
        errors.append("TAG_FOLDER is required")
    if not EQUIPMENT_MAP_FILE:
        errors.append("EQUIPMENT_MAP_FILE is required")

    if errors:
        raise EnvironmentError(
            "Missing required configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )
