"""
config/logging_config.py
───────────────────────
Cấu hình logging: console + file theo ngày (daily rollover).

Kế thừa từ middleware Laird:
  - Log chia 2 loại: "middleware" (vòng đời, trạng thái) và "kafka-publish"
    (chi tiết từng message gửi Kafka) — để khi debug Kafka không bị ngợp
    bởi log chung.
  - File log theo thư mục ngày (dd-MM-YYYY), tự xoay lúc nửa đêm, tự prune
    file cũ theo LOG_MAX_FILES.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

from config import settings

_CONSOLE_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("industrial_telemetry")


class DailyFolderFileHandler(logging.FileHandler):
    """
    FileHandler tự xoay theo ngày mà không cần restart process.

    Mỗi ngày → thư mục con ``<LOGS_DIR>/dd-MM-YYYY/`` và file
    ``<dd-MM-YYYY>_<log_kind>.log``.
    """

    def __init__(self, log_kind: str, encoding: str = "utf-8"):
        self.log_kind = log_kind
        self.encoding = encoding
        self.current_date = ""
        self._root = Path(settings.LOGS_DIR)
        self._root.mkdir(parents=True, exist_ok=True)
        super().__init__(filename=str(self._path_for(self._today())), encoding=encoding)
        self.current_date = self._today()
        self._prune_old_logs()

    # ── internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _today() -> str:
        import datetime as dt

        return dt.datetime.now().strftime("%d-%m-%Y")

    def _path_for(self, date_str: str) -> Path:
        daily_dir = Path(settings.LOGS_DIR) / date_str
        daily_dir.mkdir(parents=True, exist_ok=True)
        return daily_dir / f"{date_str}_{self.log_kind}.log"

    def _prune_old_logs(self) -> None:
        """Giữ tối đa LOG_MAX_FILES file cho mỗi loại log."""
        try:
            pattern = f"*/*_{self.log_kind}.log"
            files = sorted(
                (p for p in Path(settings.LOGS_DIR).glob(pattern) if p.is_file()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for stale in files[settings.LOG_MAX_FILES :]:
                try:
                    os.remove(stale)
                except OSError:
                    pass
        except Exception:
            pass

    def _roll_if_needed(self) -> None:
        today = self._today()
        if today == self.current_date:
            return
        self.current_date = today
        new_path = self._path_for(today)
        self.baseFilename = str(new_path)
        self.stream = self._open()
        self._prune_old_logs()

    # ── logging.Handler API ─────────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._roll_if_needed()
            super().emit(record)
        except Exception:
            self.handleError(record)


class _ConsoleFormatter(logging.Formatter):
    """Console gọn hơn file: bỏ milliseconds, rút gọn message quen thuộc."""

    _SHORTEN = {
        "[OK] Connected to OPC UA server": "OPC: connected",
        "[OK] Kafka Producer initialized": "Kafka: producer ready",
        "[KAFKA] publish": "Kafka: publish",
        "[STATE]": "State",
    }

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        if record.levelno >= logging.WARNING:
            return original
        for prefix, replacement in self._SHORTEN.items():
            if prefix in original:
                return original.replace(prefix, replacement, 1)
        return original


def setup_logging() -> logging.Logger:
    """
    Cài đặt logging cho toàn bộ middleware.

    Returns:
        Logger gốc ``industrial_telemetry``.
    """
    root = logging.getLogger("industrial_telemetry")
    root.setLevel(logging.DEBUG)
    root.propagate = False
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(getattr(logging, settings.LOG_CONSOLE_LEVEL, logging.INFO))
    console.setFormatter(_ConsoleFormatter(_CONSOLE_FORMAT, _DATE_FORMAT))
    root.addHandler(console)

    middleware_file = DailyFolderFileHandler("middleware")
    middleware_file.setLevel(getattr(logging, settings.LOG_FILE_LEVEL, logging.INFO))
    middleware_file.setFormatter(logging.Formatter(_FILE_FORMAT, _DATE_FORMAT))
    root.addHandler(middleware_file)

    kafka_file = DailyFolderFileHandler("kafka-publish")
    kafka_file.setLevel(getattr(logging, settings.LOG_FILE_LEVEL, logging.INFO))
    kafka_file.setFormatter(logging.Formatter(_FILE_FORMAT, _DATE_FORMAT))
    root.addHandler(kafka_file)

    # Thư viện opcua rất ồn → hạ level.
    logging.getLogger("opcua").setLevel(
        getattr(logging, settings.OPCUA_LOG_LEVEL, logging.WARNING)
    )

    return root


def get_logger(name: str | None = None) -> logging.Logger:
    """Lấy logger con của middleware."""
    if not name:
        return logging.getLogger("industrial_telemetry")
    return logging.getLogger(f"industrial_telemetry.{name}")
