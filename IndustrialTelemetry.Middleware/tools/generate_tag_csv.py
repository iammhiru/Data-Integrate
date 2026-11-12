# -*- coding: utf-8 -*-
"""
Sinh catalog.json + 26 file CSV theo dung dinh dang import cua Kepware.

- Cột "Data Type" dung TEN KIEU KEPWARE (Boolean, Int, Float, Long...)
- Cột "Address" theo logic tag simulator: <prefix><ordinal 4 chữ số>,
  prefix B (Boolean) / K (giá trị số) / S (String), ordinal đếm CHUNG TRONG
  CHANNEL (liên tục xuyên suốt các device của cùng channel) — Kepware resolve
  Address theo phạm vi channel nên phải không trùng trong channel
- CSV theo 18 cot chuan cua Kepware + 2 cot bo sung (TagCode, Acquisition Class)
- NodeId: ns=2;s={channel}.{device}.{tagName}

Usage:
    python tools/generate_tag_csv.py [--catalog metadata/catalog.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# Cho phep import "address_rules" khi chay truc tiep file nay
sys.path.insert(0, str(Path(__file__).resolve().parent))
from address_rules import assign_channel_addresses  # noqa: E402

#: Thu goc project (IndustrialTelemetry.Middleware/) — dung de resolve duong dan
#: tuong doi trong CLI (vi du "metadata/catalog.json").
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(raw: str) -> Path:
    """Chuyen duong dan tuong doi (theo PROJECT_ROOT) thanh Path tuyet doi."""
    path = Path(raw)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


# --- BANG ANH XA TEN KIEU KEPWARE -> OPC UA ---
# Khop voi bang trong Vinamilk.Kepware.Middleware/utils/value_helpers.py
KEPWARE_TO_OPCUA: dict[str, str] = {
    "Boolean": "Boolean",
    "Byte":    "Byte",
    "Short":   "Int16",
    "Word":    "UInt16",
    "Int":     "Int32",
    "DWord":   "UInt32",
    "Long":    "Int64",
    "LWord":   "UInt64",
    "Float":   "Float",
    "Double":  "Double",
    "String":  "String",
}

# TagType -> kieu Kepware mac dinh (khi CSV thieu cot "Data Type")
TAGTYPE_FALLBACK: dict[str, str] = {
    "DIGITAL": "Boolean",
    "ANALOG":  "Float",
    "COUNTER": "Long",
    "STRING":  "String",
}

# 18 cot chuan cua Kepware (export/import)
KEPWARE_COLUMNS: list[str] = [
    "Tag Name", "Address", "Data Type", "Respect Data Type", "Client Access",
    "Scan Rate", "Scaling", "Raw Low", "Raw High", "Scaled Low",
    "Scaled High", "Scaled Data Type", "Clamp Low", "Clamp High",
    "Eng Units", "Description", "Negate Value", "TagType",
]

# Cot bo sung cua project nay - dat SAU "TagType"
EXTRA_COLUMNS: list[str] = ["TagCode", "Acquisition Class"]

# Scan rate goi y theo loai tag
SCAN_RATE = {
    "DIGITAL": 100,
    "ANALOG": 500,
    "COUNTER": 1000,
    "STRING": 1000,
}


def build_csv_rows(tags: list[dict], device: str, addresses: list[str]) -> list[dict]:
    """Bien danh sach tag thanh cac dong CSV theo format Kepware."""
    rows: list[dict] = []
    for tag, address in zip(tags, addresses):
        tag_type = tag.get("tagType", "ANALOG")
        data_type = tag.get("dataType") or TAGTYPE_FALLBACK.get(tag_type, "Float")
        if data_type not in KEPWARE_TO_OPCUA:
            raise ValueError(
                f"[{device}] tag '{tag['name']}' co Data Type '{data_type}' "
                f"khong phai ten kieu cua Kepware. "
                f"Cho phep: {', '.join(KEPWARE_TO_OPCUA)}"
            )
        rows.append({
            "Tag Name": tag["name"],
            "Address": address,
            "Data Type": data_type,
            "Respect Data Type": 1,
            "Client Access": "R/W",
            "Scan Rate": SCAN_RATE.get(tag_type, 500),
            "Scaling": "",
            "Raw Low": "",
            "Raw High": "",
            "Scaled Low": "",
            "Scaled High": "",
            "Scaled Data Type": "",
            "Clamp Low": "",
            "Clamp High": "",
            "Eng Units": tag.get("unit") or "-",
            "Description": tag.get("meaning", ""),
            "Negate Value": "",
            "TagType": tag_type,
            "TagCode": tag.get("tagCode", ""),
            "Acquisition Class": tag.get("acquisitionClass", "PERIODIC"),
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=KEPWARE_COLUMNS + EXTRA_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="metadata/catalog.json")
    ap.add_argument("--out", default="metadata/TAG_FOLDER")
    ap.add_argument("--map-out", default="metadata/equipment_map.json")
    args = ap.parse_args()

    catalog_path = _resolve(args.catalog)
    if not catalog_path.exists():
        raise SystemExit(f"Khong tim thay catalog: {catalog_path}")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    out_root = _resolve(args.out)

    total_tags = 0
    machines = []

    # Address: ordinal dem LIEN TOC xuyen suot channel (khong trung giua
    # cac device cung channel) — Kepware resolve Address theo pham vi channel.
    channel_addresses = assign_channel_addresses(catalog["machines"])

    for machine in catalog["machines"]:
        mid = machine["machineId"]
        channel = machine["channel"]
        tags = machine["tags"]

        # Bo sung TagType + TagCode + acquisitionClass neu thieu
        for tag in tags:
            tag.setdefault("tagType", _infer_tag_type(tag))
            tag.setdefault("tagCode", _make_tag_code(machine, tag))
            tag.setdefault("acquisitionClass", "PERIODIC")
            tag["opcUaType"] = KEPWARE_TO_OPCUA[tag["dataType"]]
        rows = build_csv_rows(tags, mid, channel_addresses[mid])
        write_csv(out_root / channel / f"{mid}.csv", rows)
        total_tags += len(rows)

        machines.append({
            "machineId": mid,
            "machineType": machine["machineType"],
            "equipmentCode": machine.get("equipmentCode", f"{mid}-EQ"),
            "lineId": machine["lineId"],
            "processId": machine["processId"],
            "tagCount": len(rows),
        })

    # equipment_map.json - khoa theo "channel.device" nhu Vinamilk
    eq_map = {
        "plantId": catalog["plantId"],
        "machines": {
            f"{m['lineId']}.{m['machineId']}": {
                k: v for k, v in m.items() if k != "tagCount"
            }
            for m in machines
        },
    }
    Path(args.map_out).parent.mkdir(parents=True, exist_ok=True)
    _resolve(args.map_out).write_text(
        json.dumps(eq_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Da sinh {len(machines)} file CSV, {total_tags} tag -> {out_root}")
    print(f"Da sinh equipment_map.json -> {args.map_out}")


def _infer_tag_type(tag: dict) -> str:
    dt = tag.get("dataType", "Float")
    if dt == "Boolean":
        return "DIGITAL"
    if dt == "String":
        return "STRING"
    if dt in ("Long", "DWord", "LWord", "Word"):
        return "COUNTER"
    return "ANALOG"


def _make_tag_code(machine: dict, tag: dict) -> str:
    """Sinh TagCode ngan gon: <PREFIX>.<LINE>.<TAGNAME> - phai duy nhat toan nha may."""
    prefix = _prefix_for(machine["processId"])
    line_id = machine.get("lineId", "")
    line = "SHD" if line_id == "SHARED" else line_id.replace("LINE_", "L")
    return f"{prefix}.{line}.{tag['name'].upper()}"


def _prefix_for(process_id: str) -> str:
    return {
        "PREFORM_FEEDING": "PREF",
        "BLOW_MOULDING": "BLOW",
        "BOTTLE_CONVEYING": "ACONV",
        "RINSING": "RINSE",
        "FILLING": "FILL",
        "CAPPING": "CAPP",
        "LABELLING": "LABL",
        "CODING": "CODE",
        "CASE_PACKING": "CASE",
        "CAN_DEPALLETTIZING": "DEPL",
        "SEAMING": "SEAM",
        "INSPECTION": "INSP",
        "CIP": "CIP",
    }.get(process_id, process_id[:4].upper())


if __name__ == "__main__":
    main()