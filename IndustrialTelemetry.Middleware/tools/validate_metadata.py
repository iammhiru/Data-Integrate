# -*- coding: utf-8 -*-
"""
Kiem tra metadata truoc khi nop vao Kepware.

Kiem tra:
  1. CSV co dung 18 cot chuan Kepware + cot bo sung
  2. Cot "Data Type" dung TEN KIEU KEPWARE (khong phai ten OPC UA)
  3. "TagCode" duy nhat toan nha may
  4. "Tag Name" duy nhat trong tung file
  5. Moi may co entry tuong ung trong equipment_map.json
  6. NodeId ton tai: ns=2;s={channel}.{device}.{tagName}
  7. Counter khong dung kieu 16/32 bit (can 64 bit)
  8. Tag co "Eng Units" cho gia tri do
  9. Cot "Address" dung quy tac tag simulator: <B|K|S><4 chu so>,
     ordinal dem chung trong device, bat dau tu 0001

Usage:
    python tools/validate_metadata.py
Exit code: 0 = OK, 1 = co loi
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from address_rules import (  # noqa: E402
    address_prefix,
    make_address,
    expected_channel_addresses,
    ADDRESS_DIGITS,
    ADDRESS_STRIDE,
)

ROOT = Path(__file__).resolve().parent.parent
TAG_FOLDER = ROOT / "metadata" / "TAG_FOLDER"
EQUIPMENT_MAP = ROOT / "metadata" / "equipment_map.json"

KEPWARE_COLUMNS = [
    "Tag Name", "Address", "Data Type", "Respect Data Type", "Client Access",
    "Scan Rate", "Scaling", "Raw Low", "Raw High", "Scaled Low",
    "Scaled High", "Scaled Data Type", "Clamp Low", "Clamp High",
    "Eng Units", "Description", "Negate Value", "TagType",
]
EXTRA_COLUMNS = ["TagCode", "Acquisition Class"]

# TEN KIEU KEPWARE - khong phai ten OPC UA
KEPWARE_TYPES = {
    "Boolean", "Byte", "Char", "Short", "Word", "Int", "DWord",
    "Long", "LLong", "LWord", "Float", "Double", "String", "DateTime",
}

# Ten OPC UA - KHONG hop le trong cot "Data Type"
OPCUA_NAMES = {
    "Boolean", "SByte", "Byte", "Int16", "UInt16", "Int32", "UInt32",
    "Int64", "UInt64", "Float", "Double", "String", "DateTime", "Guid",
    "ByteString",
}

# Counter phai 64 bit
SMALL_INT_TYPES = {"Byte", "Char", "Short", "Word", "Int", "DWord"}

# Format Address: 1 chu cai (B/K/S) + 4 chu so
ADDRESS_RE = re.compile(rf"^([BKS])(\d{{{ADDRESS_DIGITS}}})$")

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def main() -> int:
    if not TAG_FOLDER.exists():
        err(f"Khong tim thay {TAG_FOLDER}")
        return report()

    csv_files = sorted(TAG_FOLDER.rglob("*.csv"))
    if not csv_files:
        err(f"Khong co file CSV nao trong {TAG_FOLDER}")
        return report()

    # --- equipment_map ---
    eq_map = {}
    if EQUIPMENT_MAP.exists():
        eq_map = json.loads(EQUIPMENT_MAP.read_text(encoding="utf-8"))
        eq_machines = eq_map.get("machines", {})
    else:
        warn(f"Khong tim thay {EQUIPMENT_MAP}")

    seen_tagcodes: dict[str, str] = {}
    seen_tagkeys: dict[str, str] = {}
    total_tags = 0
    machines = 0

    # Pass 1: doc tat ca file, gom (channel -> device -> [(data_type, address)])
    channel_files: dict[str, dict[str, list[tuple[str, str]]]] = {}
    file_rows: dict[Path, list[dict]] = {}

    for path in csv_files:
        rel = path.relative_to(TAG_FOLDER)
        channel = rel.parts[0] if len(rel.parts) > 1 else ""
        device = path.stem

        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []

            missing = [c for c in KEPWARE_COLUMNS if c not in header]
            if missing:
                err(f"{rel}: thieu cot chuan Kepware: {missing}")

            extra_missing = [c for c in EXTRA_COLUMNS if c not in header]
            if extra_missing:
                warn(f"{rel}: thieu cot bo sung: {extra_missing}")

            rows = list(reader)

        if not rows:
            err(f"{rel}: file rong")
            continue

        file_rows[path] = rows
        devices = channel_files.setdefault(channel, {})
        devices[device] = [
            ((row.get("Data Type") or "").strip(),
             (row.get("Address") or "").strip())
            for row in rows
        ]

    # Expected address cho tung channel — ordinal dem lien tuc xuyen suot
    # channel (Kepware resolve Address theo pham vi channel, nen 2 device
    # khac nhau trong cung channel cung khong duoc trung Address).
    expected_addresses: dict[str, dict[str, list[str]]] = {}
    for channel, devices in channel_files.items():
        expected_addresses[channel] = expected_channel_addresses(
            {d: [dt for dt, _ in items] for d, items in devices.items()}
        )

    for path in csv_files:
        rel = path.relative_to(TAG_FOLDER)
        channel = rel.parts[0] if len(rel.parts) > 1 else ""
        device = path.stem
        rows = file_rows.get(path)
        if rows is None:
            continue

        machines += 1
        machine_key = f"{channel}.{device}"

        # --- kiem tra equipment_map ---
        if eq_map:
            entry = eq_machines.get(machine_key)
            if entry is None:
                err(f"{rel}: khong co entry '{machine_key}' trong equipment_map.json")
            elif not entry.get("machineType"):
                err(f"{rel}: entry '{machine_key}' thieu machineType")

        local_names: set[str] = set()
        local_addresses: set[str] = set()
        exp_list = expected_addresses.get(channel, {}).get(device, [])

        for i, row in enumerate(rows, start=2):  # start=2: dong 1 la header
            total_tags += 1
            where = f"{rel}:{i}"
            tag_name = (row.get("Tag Name") or "").strip()
            data_type = (row.get("Data Type") or "").strip()
            tag_code = (row.get("TagCode") or "").strip()
            eng_units = (row.get("Eng Units") or "").strip()
            tag_type = (row.get("TagType") or "").strip()
            address = (row.get("Address") or "").strip()
            idx = i - 2  # index trong device
            ordinal = idx + 1  # dem chung trong device
            channel_ordinal = ordinal + sum(
                len(v) for k, v in channel_files.get(channel, {}).items()
                if k < device
            )

            if not tag_name:
                err(f"{where}: thieu 'Tag Name'")
                continue

            # Ten tag duy nhat trong file
            if tag_name in local_names:
                err(f"{where}: 'Tag Name' trung trong file: {tag_name}")
            local_names.add(tag_name)

            # Kiem tra kieu du lieu
            if not data_type:
                err(f"{where} [{tag_name}]: thieu 'Data Type'")
            elif data_type in OPCUA_NAMES and data_type not in KEPWARE_TYPES:
                err(f"{where} [{tag_name}]: 'Data Type' = '{data_type}' la ten OPC UA, "
                    f"phai dung ten kieu Kepware (vi du 'Int' thay vì 'Int32')")
            elif data_type not in KEPWARE_TYPES:
                err(f"{where} [{tag_name}]: 'Data Type' khong hop le: '{data_type}'. "
                    f"Cho phep: {sorted(KEPWARE_TYPES)}")

            # TagCode
            if not tag_code:
                err(f"{where} [{tag_name}]: thieu 'TagCode'")
            else:
                if tag_code in seen_tagcodes:
                    err(f"{where} [{tag_name}]: 'TagCode' '{tag_code}' trung voi "
                        f"{seen_tagcodes[tag_code]}")
                else:
                    seen_tagcodes[tag_code] = f"{rel} [{tag_name}]"

            # Counter phai 64 bit
            if tag_type == "COUNTER" and data_type in SMALL_INT_TYPES:
                err(f"{where} [{tag_name}]: counter kieu '{data_type}' se tran. "
                    f"Phai dung 'Long' (64 bit) - xem §8.3.2")

            # NodeId ton tai
            nodeid = f"ns=2;s={channel}.{device}.{tag_name}"
            seen_tagkeys[nodeid] = f"{rel} [{tag_name}]"

            # Gia tri do phai co don vi (ANALOG + Float moi la gia tri do)
            if tag_type == "ANALOG" and data_type in ("Float", "Double") \
                    and eng_units in ("", "-"):
                warn(f"{where} [{tag_name}]: tag ANALOG chua co 'Eng Units'")

            # Cot Address theo quy tac tag simulator
            m = ADDRESS_RE.match(address)
            if not m:
                err(f"{where} [{tag_name}]: 'Address' '{address}' sai format. "
                    f"Phai la <B|K|S> + {ADDRESS_DIGITS} chu so (vd B0000, K0010)")
            else:
                prefix, number = m.group(1), int(m.group(2))
                # Dung chung ham sinh Address voi generator de tranh phan ky.
                expected_address = (
                    exp_list[idx] if idx < len(exp_list)
                    else make_address(data_type, channel_ordinal)
                )
                if address != expected_address:
                    err(f"{where} [{tag_name}]: 'Address' '{address}' — phai la "
                        f"'{expected_address}' (ordinal dem lien tuc trong CHANNEL, "
                        f"gian cach {ADDRESS_STRIDE} don vi; device '{device}' "
                        f"bat dau o ordinal {channel_ordinal})")
                try:
                    expected_prefix = address_prefix(data_type)
                except ValueError:
                    expected_prefix = None
                if expected_prefix and prefix != expected_prefix:
                    err(f"{where} [{tag_name}]: 'Address' '{address}' sai tien do. "
                        f"Data Type '{data_type}' phai dung tien do '{expected_prefix}'")
                if address in local_addresses:
                    err(f"{where} [{tag_name}]: 'Address' '{address}' trung trong file")
                local_addresses.add(address)

    # --- NodeId duy nhat ---
    dupes = {}
    for nodeid, where in seen_tagkeys.items():
        dupes.setdefault(nodeid, []).append(where)
    for nodeid, wheres in dupes.items():
        if len(wheres) > 1:
            err(f"NodeId trung: {nodeid} ({len(wheres)} noi)")

    # --- Address duy nhat TRONG CHANNEL (khong chi trong 1 device) ---
    # Kepware resolve Address theo pham vi channel: 2 device khac nhau trong
    # cung channel ma trung Address se bi ghi de len nhau.
    for channel, devices in channel_files.items():
        seen: dict[str, str] = {}
        for device in sorted(devices):
            for dt, address in devices[device]:
                if address in seen:
                    err(f"{channel}/{device}: 'Address' '{address}' trung trong CHANNEL "
                        f"voi {seen[address]} — se bi ghi de khi import Kepware")
                else:
                    seen[address] = f"{channel}/{device}"

    print(f"Da kiem tra {machines} file CSV, {total_tags} tag, "
          f"{len(seen_tagcodes)} TagCode, {len(seen_tagkeys)} NodeId")
    return report()


def report() -> int:
    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[ERROR] {e}")
    if errors:
        print(f"\nFAIL: {len(errors)} loi, {len(warnings)} canh bao")
        return 1
    print(f"\nOK: khong co loi. ({len(warnings)} canh bao)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
