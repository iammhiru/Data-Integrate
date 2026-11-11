"""
core/value_types.py
───────────────────
Tầng mapping kiểu dữ liệu 3 tầng (design doc §9.5):

    CSV (tên Kepware)  →  Python native  →  Kafka valueType (tên OPC UA)

    Boolean                bool                Boolean
    Int                    int                 Int32
    Word                   int                 UInt16
    DWord                  int                 UInt32
    Long                   int                 Int64
    Float                  float               Float
    Double                 float               Double
    String                 str                 String

Ràng buộc của bài tập: kiểu số nguyên lớn nhất chỉ dùng ``Long`` và ``DWord``.
Không có LWord / UInt64 trong catalog.

Vì sao phải ép kiểu theo metadata chứ không đoán từ giá trị?
  - ``Long`` và ``Int`` đều là Python ``int`` — nhìn runtime không phân biệt được.
  - Nếu không ép, ``valueType`` sẽ phụ thuộc vào giá trị đọc được, và cùng một
    tag có thể đổi ``valueType`` giữa các message → consumer không parse ổn định.
  - Ép theo CSV ⇒ ``valueType`` của một tag là hằng số suốt vòng đời.
"""

from __future__ import annotations

from typing import Any

# ─── Tầng 1: tên kiểu Kepware (đúng chữ trong cột "Data Type" của CSV) ──────

KEPWARE_BOOLEAN = "Boolean"
KEPWARE_INT = "Int"
KEPWARE_WORD = "Word"
KEPWARE_DWORD = "DWord"
KEPWARE_LONG = "Long"
KEPWARE_FLOAT = "Float"
KEPWARE_DOUBLE = "Double"
KEPWARE_STRING = "String"

#: Tên kiểu trong cột "Data Type" của CSV → tên kiểu canonical OPC UA ghi ra Kafka.
KEPWARE_TO_OPCUA: dict[str, str] = {
    KEPWARE_BOOLEAN: "Boolean",
    KEPWARE_INT: "Int32",
    KEPWARE_WORD: "UInt16",
    KEPWARE_DWORD: "UInt32",
    KEPWARE_LONG: "Int64",
    KEPWARE_FLOAT: "Float",
    KEPWARE_DOUBLE: "Double",
    KEPWARE_STRING: "String",
}

#: Tên kiểu trong cột "Data Type" của CSV → kiểu Python native.
KEPWARE_TO_PYTHON: dict[str, type] = {
    KEPWARE_BOOLEAN: bool,
    KEPWARE_INT: int,
    KEPWARE_WORD: int,
    KEPWARE_DWORD: int,
    KEPWARE_LONG: int,
    KEPWARE_FLOAT: float,
    KEPWARE_DOUBLE: float,
    KEPWARE_STRING: str,
}

#: Các tên kiểu khác có thể gặp trong CSV do Kepware sinh ra (đọc tương thích).
_ALIASES: dict[str, str] = {
    "bool": KEPWARE_BOOLEAN,
    "boolean": KEPWARE_BOOLEAN,
    "int": KEPWARE_INT,
    "int16": KEPWARE_INT,
    "short": KEPWARE_INT,
    "word": KEPWARE_WORD,
    "uint16": KEPWARE_WORD,
    "dword": KEPWARE_DWORD,
    "uint32": KEPWARE_DWORD,
    "long": KEPWARE_LONG,
    "int64": KEPWARE_LONG,
    "float": KEPWARE_FLOAT,
    "single": KEPWARE_FLOAT,
    "double": KEPWARE_DOUBLE,
    "string": KEPWARE_STRING,
}

#: Giá trị mặc định khi CSV không khai báo "Data Type".
DEFAULT_KEPWARE_TYPE = KEPWARE_FLOAT


def canonical_kepware_type(raw: str | None) -> str:
    """
    Chuẩn hóa tên kiểu trong CSV về tên chuẩn của Kepware.

    Trả về ``DEFAULT_KEPWARE_TYPE`` nếu không nhận diện được.
    """
    if not raw:
        return DEFAULT_KEPWARE_TYPE
    text = str(raw).strip()
    if not text:
        return DEFAULT_KEPWARE_TYPE
    for known in KEPWARE_TO_OPCUA:
        if text.casefold() == known.casefold():
            return known
    alias = _ALIASES.get(text.casefold())
    if alias:
        return alias
    return DEFAULT_KEPWARE_TYPE


def opcua_type_for(kepware_type: str | None) -> str:
    """Tên kiểu OPC UA canonical tương ứng với kiểu Kepware."""
    return KEPWARE_TO_OPCUA.get(
        canonical_kepware_type(kepware_type), "Double"
    )


def python_type_for(kepware_type: str | None) -> type:
    """Kiểu Python native tương ứng với kiểu Kepware."""
    return KEPWARE_TO_PYTHON.get(canonical_kepware_type(kepware_type), float)


def coerce_value(value: Any, kepware_type: str | None) -> Any:
    """
    Ép giá trị đọc từ OPC UA về kiểu Python đúng theo metadata CSV.

    - ``Boolean`` → bool (chấp nhận "true"/"1"/1)
    - Kiểu số nguyên → int (làm tròn về phía 0)
    - Kiểu số thực → float, làm tròn 6 chữ số
    - ``String`` → str
    - ``None`` → None (giữ nguyên, quality xử lý)
    """
    if value is None:
        return None

    ktype = canonical_kepware_type(kepware_type)

    try:
        if ktype == KEPWARE_BOOLEAN:
            if isinstance(value, str):
                return value.strip().casefold() in ("true", "1", "yes", "on")
            return bool(value)

        if ktype in (KEPWARE_INT, KEPWARE_WORD, KEPWARE_DWORD, KEPWARE_LONG):
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, str):
                return int(round(float(value.strip())))
            # round thay vì trunc: tránh 42.999999 (nhiễu float) thành 42.
            return int(round(float(value)))

        if ktype in (KEPWARE_FLOAT, KEPWARE_DOUBLE):
            return round(float(value), 6)

        if ktype == KEPWARE_STRING:
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return str(value)
    except (TypeError, ValueError):
        # Không ép được → trả nguyên giá trị, quality vẫn do StatusCode quyết định.
        return value

    return value
