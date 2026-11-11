# -*- coding: utf-8 -*-
"""
tools/address_rules.py
──────────────────────
Quy tac sinh cot ``Address`` cho CSV Kepware (kiểu tag simulator).

Cot ``Address`` trong Kepware co dang:

    B0000   ← Boolean
    K0010   ← Word / Float / Int / Long / DWord  (gia tri so)
    S0020   ← String

Dac diem quan trong: **so thu tu dem lien tuc trong 1 CHANNEL** (khong reset
theo device, khong reset theo tung tien do). Vi du::

    # LINE_01/L01_AIRCONV_01.csv
    B0000,Boolean
    K0010,Float
    # LINE_01/L01_BLOWER_01.csv  ← ordinal tiep tuc, khong reset
    B0020,Boolean
    K0030,Long

Quy tac day du:

============================  ======  ==========================================
Kieu du lieu Kepware          Prefix  Ghi chu
============================  ======  ==========================================
Boolean                       B       rạc (discrete)
String                        S       chuoi
    30|Int, DWord, Long, Word,       K       gia tri so (analog / counter)
Float, Double
============================  ======  ==========================================

**Gian cach 10 don vi.** So thu tu duoc nhan voi he so ``ADDRESS_STRIDE``
(mac dinh = 10) de moi tag chiem mot "o dia chi" rieng, cach nhau 10 don vi:

    tag 1  → 0000
    tag 2  → 0010
    tag 3  → 0020
    ...

Muc dich: tranh ghi de vong dem trong bo dem (register / memory cua simulator)
va cho moi tag mot khoang trong giua, de khi can them tag moi vao giua
cac tag cu, khong phai sua lai toan bo dia chi cua cac tag phia sau.

⚠️ **Ordinal dem theo CHANNEL, khong phai theo device.** Kepware resolve
``Address`` theo pham vi channel — hai tag thuoc hai device khac nhau nhung
cung channel ma trung ``Address`` se bi ghi de len nhau khi simulator ghi
gia tri. Vi vay ``Address`` phai khong trung trong toan channel. Cac channel
khac nhau duoc phep dung lai cung dia chi.

⚠️ Cot nay KHONG phai NodeId. NodeId OPC UA van do Kepware sinh ra theo
``ns=2;s={channel}.{device}.{tagName}`` (xem §5.2 cua design doc).
"""
from __future__ import annotations

#: So chu so cua phan dia chi (0000, 0010, ...).
ADDRESS_DIGITS = 4

#: Gian cach giua 2 dia chi lien tiep (theo don vi).
#:
#: Tag thu N (1-based) nhan dia chi ``(N - 1) * ADDRESS_STRIDE``.
#: Dat = 10 de moi tag co mot khoang trong giua, tranh ghi de vong dem.
ADDRESS_STRIDE = 10

#: Tien do theo nhom kieu du lieu Kepware.
PREFIX_BOOLEAN = "B"
PREFIX_NUMERIC = "K"
PREFIX_STRING = "S"

#: Tap kieu so (analog + counter).
NUMERIC_TYPES = frozenset({
    "Byte", "Char", "Short", "Word", "Int", "DWord",
    "Long", "LLong", "LWord", "Float", "Double",
})

#: Tap kieu chuoi.
STRING_TYPES = frozenset({"String"})


def address_prefix(data_type: str) -> str:
    """
    Tra ve tien do cua ``Address`` theo kieu du lieu Kepware.

    Args:
        data_type: ten kieu theo Kepware, vi du ``Boolean``, ``Word``, ``Float``.

    Returns:
        ``"B"`` cho Boolean, ``"S"`` cho String, ``"K"`` cho moi kieu so.

    Raises:
        ValueError: neu kieu du lieu khong thuoc bat ky nhom nao.
    """
    dt = (data_type or "").strip()
    if dt == "Boolean":
        return PREFIX_BOOLEAN
    if dt in STRING_TYPES:
        return PREFIX_STRING
    if dt in NUMERIC_TYPES:
        return PREFIX_NUMERIC
    raise ValueError(
        f"Chua biet tien do Address cho kieu du lieu '{data_type}'. "
        f"Cho phep: Boolean, String, hoac mot trong {sorted(NUMERIC_TYPES)}"
    )


def make_address(data_type: str, ordinal: int) -> str:
    """
    Sinh mot ``Address`` day du.

    Args:
        data_type: ten kieu theo Kepware.
        ordinal: so thu tu cua tag trong device (bat dau tu 1).

    Returns:
        Vi du ``"B0000"``, ``"K0010"``, ``"S0020"``.
    """
    if ordinal < 1:
        raise ValueError(f"ordinal phai >= 1, nhan duoc {ordinal}")
    number = (ordinal - 1) * ADDRESS_STRIDE
    return f"{address_prefix(data_type)}{number:0{ADDRESS_DIGITS}d}"


def build_addresses(tags: list[dict], start_ordinal: int = 1) -> list[str]:
    """
    Sinh danh sach ``Address`` cho toan bo tag cua mot device.

    So thu tu dem chung cho moi loai kieu du lieu — dung logic cua file
    Kepware tham khau (Vinamilk) — va duoc nhan voi ``ADDRESS_STRIDE``.

    Args:
        tags: danh sach tag theo thu tu trong ``catalog.json``; moi tag co
            khoa ``dataType``.
        start_ordinal: ordinal cua tag dau tien trong device. Dung > 1 khi
            device da dung het mot doan ordinal trong channel (de dam bao
            ``Address`` khong trung giua cac device cung channel).

    Returns:
        Danh sach ``Address`` cung thu tu voi ``tags``.
    """
    return [
        make_address(tag.get("dataType", ""), start_ordinal + i)
        for i, tag in enumerate(tags)
    ]


def assign_channel_addresses(machines: list[dict]) -> dict[str, list[str]]:
    """
    Sinh ``Address`` cho tat ca device, KHONG trung trong cung channel.

    Kepware resolve ``Address`` theo pham vi **channel** (khong phai device):
    hai tag khong device nhung cung channel ma trung ``Address`` se bi ghi
    de len nhau. Vi vay ordinal phai dem lien tuc xuyen suot channel, theo
    thu tu: ten device (alphabet) → thu tu tag trong device.

    Args:
        machines: danh sach machine, moi phan tu co khoa ``machineId``,
            ``channel`` va ``tags``.

    Returns:
        Dict ``{machineId: [address, ...]}``.
    """
    by_channel: dict[str, list[dict]] = {}
    for machine in machines:
        by_channel.setdefault(machine["channel"], []).append(machine)

    result: dict[str, list[str]] = {}
    for channel_machines in by_channel.values():
        ordinal = 1
        for machine in sorted(channel_machines, key=lambda m: m["machineId"]):
            addresses = build_addresses(machine["tags"], start_ordinal=ordinal)
            ordinal += len(machine["tags"])
            result[machine["machineId"]] = addresses
    return result


def expected_channel_addresses(
    channel_devices: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    Tinh ``Address`` mong doi cho cac device cua MOT channel.

    Args:
        channel_devices: dict ``{device: [dataType, ...]}`` theo thu tu tag
            trong tung device.

    Returns:
        Dict ``{device: [address, ...]}`` — cung thu tu vao.
    """
    ordinal = 1
    result: dict[str, list[str]] = {}
    for device in sorted(channel_devices):
        data_types = channel_devices[device]
        result[device] = [
            make_address(dt, ordinal + i) for i, dt in enumerate(data_types)
        ]
        ordinal += len(data_types)
    return result
