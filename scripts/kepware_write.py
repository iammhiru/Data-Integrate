"""
GHI gia tri vao Kepware (OPC UA) — dung de KIEM THU luong realtime.

Vi sao can tool nay:
  · Middleware chi PHAT message khi gia tri THAY DOI (change-detection dedup).
  · Kepware tren may nay doc-only theo cau hinh, nen tu dong khong doi duoc
    gia tri -> can ghi thu cong tu Quick Client / Explorer cua Kepware.
  · Script nay ghi truc tiep qua OPC UA (server cho phep ghi node co
    AccessLevel = CurrentWrite) de kiem thu nhanh tren may Windows.

Dung:
    .\\.venv\\Scripts\\python.exe scripts\\kepware_write.py --list
    .\\.venv\\Scripts\\python.exe scripts\\kepware_write.py --machine L01_AIRCONV_01 --tag CurrentSpeed --value 3333
    .\\.venv\\Scripts\\python.exe scripts\\kepware_write.py --machine L01_FILLER_01 --tag MachineState --value 2
    .\\.venv\\Scripts\\python.exe scripts\\kepware_write.py --watch L01_AIRCONV_01 CurrentSpeed --interval 3

Sau khi ghi, doi lai gia tri (--value) hoac dung --watch de theo doi gia tri
trong Kepware. Moi lan doi -> 1 message -> UI cap nhat sau ~1-2 giay.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from opcua import Client, ua

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "IndustrialTelemetry.Middleware"))

OPC_URL = "opc.tcp://127.0.0.1:49320"

# Kieu du lieu trong Kepware -> VariantType tuong ung (ghi sai kieu se bi
# BadTypeMismatch).
#
# ⚠ `kepware_type` trong CSV dung ten KHAC voi OPC UA canonical:
#    Kepware "Float"    -> OPC UA Float
#    Kepware "Double"   -> OPC UA Double
#    Kepware "Int"/"Word"/"DWord"/"Long" -> OPC UA Int32/Int64 (de an toan)
#    Kepware "Boolean"  -> OPC UA Boolean
#    Kepware "String"   -> OPC UA String
#
# Ghi Float cho node thuc te co DataType = Double se bi BadTypeMismatch,
# nen thu Float truoc, fallback sang Double neu that bai.
TYPE_BY_NAME = {
    "Float": ua.VariantType.Float,
    "Double": ua.VariantType.Double,
    "Int": ua.VariantType.Int32,
    "Int32": ua.VariantType.Int32,
    "Word": ua.VariantType.Int32,
    "DWord": ua.VariantType.Int64,
    "Long": ua.VariantType.Int64,
    "Int64": ua.VariantType.Int64,
    "Boolean": ua.VariantType.Boolean,
    "String": ua.VariantType.String,
}


def load_tags():
    """Nap danh sach tag tu metadata cua middleware (cung CSV voi dong doi)."""
    from core.tag_loader import load_all_tags

    return load_all_tags()


def build_index(tags):
    """(machineId, tagName) -> node_id + kieu du lieu.

    ⚠ `TagDefinition` dung `kepware_type` (Boolean/Int/Word/DWord/Long/Float/
    Double/String) — KHONG phai `data_type`. `value_type` là tên kiểu OPC UA
    canonical dùng cho Kafka.
    """
    idx = {}
    for t in tags:
        idx[(t.device, t.tag_name)] = (t.node_id, t.kepware_type)
    return idx


def pick_type(node, declared: str | None):
    """Chon VariantType: uu tien kieu khai bao trong CSV, fallback doc thuc te."""
    if declared and declared in TYPE_BY_NAME:
        return TYPE_BY_NAME[declared]
    try:
        dt = node.get_data_type()
        name = str(dt).split("=")[-1].split("(")[0].strip()
        if name in TYPE_BY_NAME:
            return TYPE_BY_NAME[name]
    except Exception:  # noqa: BLE001
        pass
    return ua.VariantType.Double


def write_value(client, node_id, value, declared_type=None):
    """Ghi gia tri, thu nhieu kieu Variant cho den khi server nhan.

    Kepware reject kieu khong khop voi DataType cua node
    (``BadTypeMismatch``), va reject khi kem ca status/timestamp
    (``BadWriteNotSupported``). Vì vậy phai thu theo thu tu:
    Float -> Double -> Int64 -> Int32, chi gui Value.
    """
    node = client.get_node(node_id)
    order = []
    primary = pick_type(node, declared_type)
    for vt in (primary, ua.VariantType.Float, ua.VariantType.Double,
               ua.VariantType.Int64, ua.VariantType.Int32):
        if vt not in order:
            order.append(vt)

    last_err: Exception | None = None
    for vt in order:
        try:
            candidate = value
            if vt in (ua.VariantType.Int32, ua.VariantType.Int64):
                candidate = int(value)
            elif vt in (ua.VariantType.Float, ua.VariantType.Double):
                candidate = float(value)
            elif vt == ua.VariantType.Boolean:
                candidate = bool(value)
            node.set_data_value(ua.DataValue(ua.Variant(candidate, vt)))
            return node.get_value()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise last_err if last_err else RuntimeError("khong ghi duoc")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="In danh sach tag co the ghi")
    ap.add_argument("--machine", help="machineId, vi du L01_AIRCONV_01")
    ap.add_argument("--tag", help="Ten tag, vi du CurrentSpeed")
    ap.add_argument("--value", help="Gia tri moi (chieu so hoac chuoi)")
    ap.add_argument("--watch", nargs=2, metavar=("MACHINE", "TAG"),
                    help="Theo doi gia tri cua 1 tag (poll moi 2 giay)")
    ap.add_argument("--interval", type=float, default=3.0, help="Chu ky poll (giay)")
    ap.add_argument("--url", default=OPC_URL, help="OPC UA endpoint")
    args = ap.parse_args()

    tags = load_tags()
    idx = build_index(tags)

    if args.list:
        print(f"{'machineId':<18} {'tagName':<20} {'nodeId':<50} type")
        for (dev, name), (node_id, dtype) in sorted(idx.items()):
            print(f"{dev:<18} {name:<20} {node_id:<50} {dtype}")
        print(f"\nTong: {len(idx)} tag tren {len({d for d, _ in idx})} may.")
        return 0

    if args.watch:
        dev, name = args.watch
        key = (dev, name)
        if key not in idx:
            print(f"[X] Khong co tag '{name}' cua may '{dev}'")
            return 1
        node_id, dtype = idx[key]
        client = Client(args.url, timeout=10)
        client.connect()
        print(f"[*] Theo doi {dev}/{name} ({node_id}) — Ctrl+C de dung")
        try:
            while True:
                try:
                    val = client.get_node(node_id).get_value()
                    print(f"  {time.strftime('%H:%M:%S')}  {dev}/{name} = {val!r}")
                except Exception as exc:  # noqa: BLE001
                    print(f"  doc loi: {type(exc).__name__}: {exc}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[OK] Dung theo doi.")
        finally:
            client.disconnect()
        return 0

    if not (args.machine and args.tag):
        ap.print_help()
        return 1

    key = (args.machine, args.tag)
    if key not in idx:
        print(f"[X] Khong co tag '{args.tag}' cua may '{args.machine}'")
        print("    Xem danh sach: --list")
        return 1

    node_id, dtype = idx[key]

    if args.value is None:
        # Chi doc
        client = Client(args.url, timeout=10)
        client.connect()
        val = client.get_node(node_id).get_value()
        print(f"{args.machine}/{args.tag} = {val!r}")
        client.disconnect()
        return 0

    # Parse value theo kieu khai bao
    raw = args.value
    if dtype == "Boolean":
        value = raw.strip().lower() in ("1", "true", "yes", "on")
    elif dtype in ("Int", "Int32", "Int64", "Long", "Short", "Word", "DWord"):
        value = int(float(raw))
    elif dtype == "String":
        value = raw
    else:
        value = float(raw)

    client = Client(args.url, timeout=10)
    client.connect()
    try:
        before = client.get_node(node_id).get_value()
        after = write_value(client, node_id, value, dtype)
        print(f"[OK] {args.machine}/{args.tag}: {before!r} -> {after!r}")
        print("     -> middleware se phat message (gia tri thay doi) -> UI cap nhat sau ~1-2s")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[X] Ghi that bai: {type(exc).__name__}: {exc}")
        print("    Node co the read-only. Hay doi gia tri trong Kepware Quick Client.")
        return 1
    finally:
        client.disconnect()


if __name__ == "__main__":
    sys.exit(main())
