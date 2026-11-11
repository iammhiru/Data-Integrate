"""
utils/event_id.py
─────────────────
Sinh ``eventId`` tất định (UUID v5) cho mỗi sự kiện telemetry.

Mục đích: cho phép dedup ở mọi tầng downstream (Flink, consumer, lưu trữ)
mà không cần state phía server.

Công thức (chốt trong design doc §5.3):
    eventId = uuid5(NAMESPACE, f"{machineId}|{tagName}|{sourceTimestamp}|{value}|{statusCode}")

Lưu ý quan trọng:
  - ``sourceTimestamp`` là timestamp NGUỒN từ Kepware, KHÔNG phải thời điểm
    middleware nhận được. Nếu dùng thời điểm nhận, mỗi lần reconnect sẽ sinh
    eventId khác → mất khả năng dedup.
  - Giá trị số thực phải được làm tròn trước khi nối chuỗi, nếu không
    ``87.5`` và ``87.5000000001`` sẽ cho hai eventId khác nhau.
"""

from __future__ import annotations

import uuid
from typing import Any

#: Namespace cố định của hệ thống telemetry.
#:
#: QUAN TRỌNG: không được đổi giá trị này. Đổi = hỏng dedup của toàn hệ thống.
#: Được sinh một lần và ghim cứng trong design doc + data contract.
TELEMETRY_NS = uuid.UUID("6f0d2b1e-9a4c-4c0e-9a1b-2c3d4e5f6a7b")

#: Số chữ số thập phân giữ lại khi làm tròn số thực trước khi sinh eventId.
FLOAT_PRECISION = 6


def canonical_value_str(value: Any) -> str:
    """
    Chuyển giá trị đã chuẩn hóa thành chuỗi ổn định để nối vào canonical string.

    Quy tắc:
      - ``None``            → chuỗi rỗng
      - ``bool``            → "True"/"False"
      - ``float``           → làm tròn FLOAT_PRECISION chữ số rồi format gọn
      - ``int``             → str()
      - ``str``             → chính nó
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        rounded = round(value, FLOAT_PRECISION)
        # Bỏ ".0" để 87.0 và 87 cho cùng một eventId.
        if rounded == int(rounded) and abs(rounded) < 1e15:
            return str(int(rounded))
        return repr(rounded)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value)


def build_canonical_string(
    machine_id: str,
    tag_name: str,
    source_timestamp: str,
    value: Any,
    status_code: str,
) -> str:
    """Dựng canonical string dùng làm input của UUID v5."""
    return "|".join(
        [
            str(machine_id or ""),
            str(tag_name or ""),
            str(source_timestamp or ""),
            canonical_value_str(value),
            str(status_code or ""),
        ]
    )


def build_event_id(
    machine_id: str,
    tag_name: str,
    source_timestamp: str,
    value: Any,
    status_code: str,
) -> str:
    """
    Sinh ``eventId`` (UUID v5, tất định) cho một sự kiện telemetry.

    Args:
        machine_id:      machineId (trùng source.device).
        tag_name:        tên tag trong Kepware.
        source_timestamp: ISO-8601 của SourceTimestamp.
        value:           giá trị đã chuẩn hóa (bool/int/float/str/None).
        status_code:     "Good" | "Uncertain" | "Bad".

    Returns:
        Chuỗi UUID, ví dụ "3f2504e0-4f89-41d3-9a0c-0305e82c3301".
    """
    canonical = build_canonical_string(
        machine_id, tag_name, source_timestamp, value, status_code
    )
    return str(uuid.uuid5(TELEMETRY_NS, canonical))
