"""
tools/write_tag.py
─────────────────
GHI giá trị vào Kepware (OPC UA server) để kiểm thử luồng realtime.

Vì sao cần tool này?
  Middleware ở chế độ thật dùng **change-detection** (chỉ phát ra Kafka khi
  giá trị THAY ĐỔI). Nếu Kepware giữ nguyên giá trị thì không có gì để
  hiển thị. Tool này ghi một giá trị mới vào tag → Kepware phát
  notification → middleware đẩy Kafka → Spark → state-api → WebSocket → UI.

Cách dùng (từ thư mục IndustrialTelemetry.Middleware/):
    python tools/write_tag.py L01_FILLER_01.CurrentSpeed 42.5
    python tools/write_tag.py L01_FILLER_01.MachineState 2
    python tools/write_tag.py --list L01_FILLER_01          # xem các tag của máy
    python tools/write_tag.py --watch L01_FILLER_01.CurrentSpeed 42.5 --interval 3

Lưu ý:
  - Chỉ ghi được với tag mà Kepware cho phép Write (AccessLevel có bit Write).
    Tag đọc-only sẽ báo lỗi rõ ràng.
  - Kiểu dữ liệu phải khớp với tag (Kepware chặn sai kiểu).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Cho phép chạy như `python tools/write_tag.py` từ gốc project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opcua import Client, ua  # noqa: E402

from config import settings  # noqa: E402
from core.tag_loader import load_all_tags  # noqa: E402
from core.value_types import (  # noqa: E402
    KEPWARE_BOOLEAN,
    KEPWARE_DOUBLE,
    KEPWARE_FLOAT,
    KEPWARE_INT,
    KEPWARE_LONG,
    KEPWARE_STRING,
    KEPWARE_WORD,
    KEPWARE_DWORD,
    canonical_kepware_type,
)

#: Kepware datatype -> VariantType tương ứng để ghi đúng kiểu.
_VARIANT_FOR_KEPWARE = {
    KEPWARE_BOOLEAN: ua.VariantType.Boolean,
    KEPWARE_INT: ua.VariantType.Int32,
    KEPWARE_WORD: ua.VariantType.UInt16,
    KEPWARE_DWORD: ua.VariantType.UInt32,
    KEPWARE_LONG: ua.VariantType.Int64,
    KEPWARE_FLOAT: ua.VariantType.Float,
    KEPWARE_DOUBLE: ua.VariantType.Double,
    KEPWARE_STRING: ua.VariantType.String,
}


def _parse_value(raw: str, kepware_type: str):
    """Ép chuỗi người dùng nhập về kiểu đúng với tag."""
    ktype = canonical_kepware_type(kepware_type)
    text = raw.strip()
    if ktype == KEPWARE_BOOLEAN:
        return text.casefold() in ("true", "1", "yes", "on")
    if ktype in (KEPWARE_INT, KEPWARE_WORD, KEPWARE_DWORD, KEPWARE_LONG):
        return int(round(float(text)))
    if ktype in (KEPWARE_FLOAT, KEPWARE_DOUBLE):
        return float(text)
    return text


def _variant_type_for_node(node, tag_def) -> ua.VariantType:
    """
    Xác định VariantType thực sự của node trên Kepware.

    CSV khai báo "Int" → canonical Int32, nhưng Kepware thường lưu `Int`
    dưới kiểu OPC UA `UInt16`/`Int16`. Ghi bằng sai kiểu → `BadTypeMismatch`.
    Vì vậy đọc `Value` attribute (server tự trả về đúng VariantType của nó)
    rồi dùng luôn kiểu đó.
    """
    try:
        val = node.get_attribute(ua.AttributeIds.Value)
        vt = val.Value.VariantType
        if vt is not None and vt != ua.VariantType.Null:
            return vt
    except Exception:
        pass
    # Fallback: dùng kiểu trong CSV.
    return _VARIANT_FOR_KEPWARE.get(
        canonical_kepware_type(tag_def.kepware_type), ua.VariantType.Double
    )


#: OPC UA numeric node-id (namespace 0) → VariantType.
_VARIANT_BY_NODEID = {
    1: ua.VariantType.Boolean,
    2: ua.VariantType.SByte,
    3: ua.VariantType.Int16,
    4: ua.VariantType.Int32,
    5: ua.VariantType.Int64,
    6: ua.VariantType.Byte,
    7: ua.VariantType.UInt16,
    8: ua.VariantType.UInt32,
    9: ua.VariantType.UInt64,
    10: ua.VariantType.Float,
    11: ua.VariantType.Double,
    12: ua.VariantType.String,
}


def _find_tag(tags, device: str, tag_name: str):
    """Tìm tag theo `<Device>.<TagName>` (không phân biệt hoa thường)."""
    needle = f"{device}.{tag_name}".casefold()
    for t in tags:
        if f"{t.device}.{t.tag_name}".casefold() == needle:
            return t
    return None


def _list_device(tags, device: str) -> None:
    print(f"Tags cua '{device}':")
    for t in sorted(tags, key=lambda x: x.tag_name):
        if t.device.casefold() != device.casefold():
            continue
        print(
            f"  {t.tag_name:22s} type={t.kepware_type:8s} "
            f"unit={t.unit or '-':8s} node={t.node_id}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Ghi gia tri vao Kepware (OPC UA)")
    ap.add_argument("tag", nargs="?", help="<Device>.<TagName>, vd L01_FILLER_01.CurrentSpeed")
    ap.add_argument("value", nargs="?", help="gia tri moi")
    ap.add_argument("--server", default=settings.OPC_SERVER_URL, help="OPC UA endpoint")
    ap.add_argument("--list", metavar="DEVICE", help="liet ke cac tag cua mot may")
    ap.add_argument("--watch", metavar="<Device>.<TagName>", help="ghi lien tuc (xem --interval)")
    ap.add_argument("--interval", type=float, default=5.0, help="chu ky ghi (giay) cho --watch")
    ap.add_argument("--count", type=int, default=0, help="so lan ghi (0 = vo han)")
    args = ap.parse_args()

    tags = load_all_tags()

    if args.list:
        _list_device(tags, args.list)
        return 0

    if not args.tag:
        ap.print_help()
        return 1

    target = args.watch or args.tag
    if "." not in target:
        print("LOI: tag phai co dang <Device>.<TagName>", file=sys.stderr)
        return 1

    device, tag_name = target.rsplit(".", 1)
    tag_def = _find_tag(tags, device, tag_name)
    if tag_def is None:
        print(f"LOI: khong tim thay tag '{target}' trong TAG_FOLDER", file=sys.stderr)
        return 1

    if args.watch and args.value is None:
        print("LOI: --watch can them gia tri", file=sys.stderr)
        return 1

    value = _parse_value(args.value, tag_def.kepware_type) if args.value is not None else None

    client = Client(args.server, timeout=15)
    client.connect()
    node = client.get_node(tag_def.node_id)

    # Kepware dung kieu thuc te cua node (Int16 / Float / Boolean ...), KHAC
    # voi kieu trong CSV ("Int" -> Int32). Neu dung kieu sai, Kepware tra
    # BadTypeMismatch. Do la datatype Attribute cua node roi ep value theo do.
    variant_type = _variant_type_for_node(node, tag_def)

    def write_once(v) -> bool:
        try:
            before = node.get_value()
        except Exception:
            before = "<doc loi>"
        try:
            node.set_data_value(ua.DataValue(ua.Variant(v, variant_type)))
        except Exception as exc:  # noqa: BLE001
            print(f"LOI GHI {tag_def.node_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return False
        after = node.get_value()
        print(f"[{time.strftime('%H:%M:%S')}] {target}: {before!r} -> {after!r}  (ghi OK)")
        return True

    if args.watch:
        print(f"Ghi lien tuc {target} = {value} (Ctrl+C de dung)")
        n = 0
        try:
            while True:
                write_once(value)
                n += 1
                if args.count and n >= args.count:
                    break
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nDung.")
    else:
        write_once(value)

    client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
