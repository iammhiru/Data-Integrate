"""
utils/status_codes.py
─────────────────────
Chuẩn hóa OPC UA StatusCode về 3 mức: Good / Uncertain / Bad.

Đây là phần "data quality" của data contract (§5.3 của design doc):
  - Good       → value giữ nguyên, isGood = true
  - Uncertain  → value giữ nguyên, isGood = false  (đọc được nhưng không chắc chắn)
  - Bad        → value = null,     isGood = false  (không đọc được)

Nguyên tắc: không bao giờ bịa giá trị thay thế cho dữ liệu hỏng.

⚠️ BẪY ĐÃ GẶP — định dạng thật của python-opcua
─────────────────────────────────────────────────
``str(ua.StatusCode)`` **KHÔNG** trả về ``"Good"`` mà trả về chuỗi có
wrapper:

    StatusCode(Good)
    StatusCode(BadNoCommunication)
    StatusCode(UncertainLastUsableValue)

Nếu dùng ``text.startswith("good")`` thì ``"statuscode(good)"`` không khớp
→ rơi xuống nhánh "không nhận diện được" → bị coi là **Bad** → mọi giá trị
đều bị ghi ra Kafka với ``value = null``.

Đây chính là lý do 2 middleware tham khảu (Laird, Vinamilk) dùng phép
**chứa** (``"bad" in s``) chứ không dùng ``startswith``.

Vì vậy ở đây:
  1. Bóc wrapper ``StatusCode(...)`` ra trước khi so khớp.
  2. Dùng phép **chứa**, không dùng ``startswith`` — an toàn với mọi biến
     thể (``BadOutOfService``, ``BadUnexpectedError``, ``UncertainReferenceOut
     ofServer``...).
  3. Ưu tiên đối tượng ``ua.StatusCode`` nguyên bản (có ``is_good()``) khi
     còn dùng được.
"""

from __future__ import annotations

import re
from typing import Any

#: 3 mức chuẩn hóa — đây là giá trị duy nhất được ghi ra Kafka.
GOOD = "Good"
UNCERTAIN = "Uncertain"
BAD = "Bad"

#: Tập giá trị hợp lệ của ``quality.statusCode`` trong message.
QUALITY_LABELS: frozenset[str] = frozenset({GOOD, UNCERTAIN, BAD})

#: Wrapper của python-opcua: "StatusCode(Good)" → "Good"
_STATUSCODE_WRAPPER_RE = re.compile(r"^statuscode\(\s*(?P<inner>.*?)\s*\)$")


def _unwrap(text: str) -> str:
    """Bóc wrapper ``StatusCode(...)`` của python-opcua nếu có."""
    m = _STATUSCODE_WRAPPER_RE.match(text)
    return m.group("inner") if m else text


def normalize_status_code(status_code: Any) -> tuple[str, bool]:
    """Chuẩn hóa một StatusCode OPC UA (bất kỳ) → ``(label, is_good)``.

    Args:
        status_code: ``ua.StatusCode`` của python-opcua, hoặc chuỗi, hoặc None.

    Returns:
        ``("Good", True)`` | ``("Uncertain", False)`` | ``("Bad", False)``
    """
    if status_code is None:
        return GOOD, True

    # 1) Đối tượng ua.StatusCode nguyên bản — đáng tin nhất.
    #    Chỉ dùng được khi caller KHÔNG ép thành chuỗi trước.
    is_good = getattr(status_code, "is_good", None)
    if callable(is_good):
        try:
            if is_good():
                return GOOD, True
        except Exception:
            pass

    is_uncertain = getattr(status_code, "is_uncertain", None)
    if callable(is_uncertain):
        try:
            if is_uncertain():
                return UNCERTAIN, False
        except Exception:
            pass

    # 1b) ua.StatusCode cũng có .name = "Good" / "BadNoCommunication"...
    name = getattr(status_code, "name", None)
    if isinstance(name, str) and name.strip():
        label, is_ok = _label_from_text(name)
        if label is not None:
            return label, is_ok

    # 2) Chuỗi. Bóc wrapper "StatusCode(...)" trước, rồi so với phép CHỨA
    #    (không dùng startswith — xem giải thích ở đầu file).
    text = _unwrap(str(status_code).strip().casefold())
    if not text:
        return GOOD, True

    label, is_ok = _label_from_text(text)
    if label is not None:
        return label, is_ok

    # 3) Chuỗi không nhận diện được → coi như Bad (an toàn: không bịa dữ liệu)
    return BAD, False


def _label_from_text(text: str) -> tuple[str | None, bool]:
    """
    Phân loại một chuỗi trạng thái (đã lowercase, đã bóc wrapper).

    Returns:
        ``(label, is_good)`` — ``label`` là None nếu không nhận diện được.
    """
    # "good" — nhưng "goodmore" không phải. Kiểm tra ranh giới từ.
    if re.fullmatch(r"good[a-z]*", text):
        return GOOD, True
    if "uncertain" in text:
        return UNCERTAIN, False
    if "bad" in text:
        return BAD, False
    return None, False


def is_bad_status(status_code: Any) -> bool:
    """True nếu status là Bad hoặc Uncertain."""
    label, _ = normalize_status_code(status_code)
    return label in (UNCERTAIN, BAD)


def quality_payload(status_code: Any) -> dict[str, Any]:
    """Dựng khối ``quality`` của message."""
    label, is_good = normalize_status_code(status_code)
    return {"statusCode": label, "isGood": is_good}
