"""
utils/time_utils.py
───────────────────
Chuyển đổi timestamp giữa OPC UA (datetime) và chuỗi ISO-8601 UTC.

Data contract quy định:
  - ``eventTime``       : ISO-8601 UTC, milliseconds — lấy từ SourceTimestamp
  - ``source.serverTimestamp`` : ISO-8601 UTC — lấy từ ServerTimestamp

Luôn dùng UTC, luôn có milliseconds, luôn kết thúc bằng "Z" — để consumer
ở mọi ngôn ngữ đều parse được mà không cần cấu hình timezone.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

#: ISO format chuẩn của contract: 2026-11-11T09:15:32.412Z
ISO_MILLIS = "%Y-%m-%dT%H:%M:%S.%f"

_UTC = dt.timezone.utc


def utc_now() -> dt.datetime:
    """Thời điểm hiện tại, timezone-aware UTC."""
    return dt.datetime.now(tz=_UTC)


def to_utc(value: dt.datetime | None) -> dt.datetime | None:
    """
    Chuẩn hóa datetime về timezone-aware UTC.

    - ``None`` → ``None``
    - naive datetime → coi là UTC (Kepware server chạy UTC)
    - aware datetime → chuyển sang UTC
    """
    if value is None:
        return None
    if not isinstance(value, dt.datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=_UTC)
    return value.astimezone(_UTC)


def to_iso(value: dt.datetime | None, *, default_now: bool = False) -> str | None:
    """
    Chuyển datetime → chuỗi ISO-8601 UTC milliseconds (kết thúc bằng "Z").

    Args:
        value: datetime nguồn.
        default_now: True → nếu value là None thì dùng thời điểm hiện tại
                     (dùng cho ``eventTime`` khi server không trả timestamp).

    Returns:
        "2026-11-11T09:15:32.412Z" hoặc None.
    """
    dt_utc = to_utc(value)
    if dt_utc is None:
        if not default_now:
            return None
        dt_utc = utc_now()
    # %f cho 6 chữ số (micro); cắt còn 3 để khớp milliseconds.
    return dt_utc.strftime(ISO_MILLIS)[:-3] + "Z"


def to_epoch_seconds(value: dt.datetime | None) -> int:
    """Chuyển datetime → Unix epoch (giây). None → thời điểm hiện tại."""
    dt_utc = to_utc(value)
    if dt_utc is None:
        return int(time.time())
    return int(dt_utc.timestamp())


def to_epoch_millis(value: dt.datetime | None) -> int:
    """Chuyển datetime → Unix epoch (milli giây)."""
    dt_utc = to_utc(value)
    if dt_utc is None:
        return int(time.time() * 1000)
    return int(dt_utc.timestamp() * 1000)
