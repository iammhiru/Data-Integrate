# -*- coding: utf-8 -*-
"""
Kiem tra ban CSV "sach" (metadata/KEPWARE_IMPORT/) truoc khi import vao Kepware.

Kiem tra:
  1. Dung 17 cot chuan cua Kepware, dung thu tu.
  2. Khong con cot phu (TagType, TagCode, Acquisition Class).
  3. "Data Type" la ten kieu cua Kepware.
  4. Cot "Address" dung quy tac tag simulator: <B|K|S><4 chu so>,
     ordinal dem chung trong device, bat dau tu 0001.
  5. Tag Name khong rong, khong trung trong 1 file.
  6. So dong khop voi metadata/TAG_FOLDER/ (404 tag) — khong mat/duong tag.

Usage:
    python tools/validate_kepware_import_csv.py
"""
from __future__ import annotations

import argparse
import csv
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

KEPWARE_COLUMNS = [
    "Tag Name", "Address", "Data Type", "Respect Data Type", "Client Access",
    "Scan Rate", "Scaling", "Raw Low", "Raw High", "Scaled Low",
    "Scaled High", "Scaled Data Type", "Clamp Low", "Clamp High",
    "Eng Units", "Description", "Negate Value",
]

KEPWARE_TYPES = {
    "Boolean", "Byte", "Short", "Word", "Int", "DWord", "Long", "LWord",
    "Float", "Double", "String",
}

BANNED_COLUMNS = ["TagType", "TagCode", "Acquisition Class"]

#: Thu goc project (IndustrialTelemetry.Middleware/) — dung de resolve duong dan
#: tuong doi trong CLI (vi du "metadata/KEPWARE_IMPORT").
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(raw: str) -> Path:
    """Chuyen duong dan tuong doi (theo PROJECT_ROOT) thanh Path tuyet doi."""
    path = Path(raw)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


#: Format Address: 1 chu cai (B/K/S) + 4 chu so
ADDRESS_RE = re.compile(rf"^([BKS])(\d{{{ADDRESS_DIGITS}}})$")

errors: list[str] = []
warnings: list[str] = []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="metadata/KEPWARE_IMPORT")
    ap.add_argument("--source", default="metadata/TAG_FOLDER")
    args = ap.parse_args()

    root = _resolve(args.dir)
    src_root = _resolve(args.source)

    if not root.exists():
        raise SystemExit(f"Khong tim thay: {root}")

    files = sorted(p for p in root.rglob("*.csv"))
    if not files:
        raise SystemExit(f"Khong co file CSV trong {root}")

    total_tags = 0
    all_names: set[str] = set()
    # channel -> device -> [(data_type, address)]
    channel_files: dict[str, dict[str, list[tuple[str, str]]]] = {}

    print(f"Kiem tra {len(files)} file CSV trong {root}\n")

    # Pre-pass: gom (channel -> device -> [(data_type, address)]) de tinh
    # expected address cho ca channel. Ordinal dem lien tuc xuyen suot channel
    # — Kepware resolve Address theo pham vi channel, nen 2 device khac nhau
    # trong cung channel cung khong duoc trung Address.
    for csv_path in files:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        rel = csv_path.relative_to(root)
        channel = rel.parts[0] if len(rel.parts) > 1 else ""
        channel_files.setdefault(channel, {})[csv_path.stem] = [
            ((row.get("Data Type") or "").strip(),
             (row.get("Address") or "").strip())
            for row in rows
        ]

    expected_addresses: dict[str, dict[str, list[str]]] = {}
    for channel, devices in channel_files.items():
        expected_addresses[channel] = expected_channel_addresses(
            {d: [dt for dt, _ in items] for d, items in devices.items()}
        )

    for csv_path in files:
        rel = csv_path.relative_to(root)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or [])
            rows = list(reader)

        # 1. Cột
        if fields != KEPWARE_COLUMNS:
            errors.append(
                f"{rel}: sai cot/thu tu.\n"
                f"    expected: {KEPWARE_COLUMNS}\n"
                f"    actual  : {fields}"
            )
            continue

        # 2. Không còn cột phụ
        leftover = [c for c in BANNED_COLUMNS if c in fields]
        if leftover:
            errors.append(f"{rel}: van con cot phu {leftover}")

        device = csv_path.stem
        channel = rel.parts[0] if len(rel.parts) > 1 else ""
        seen_local: set[str] = set()
        seen_addresses: set[str] = set()

        for i, row in enumerate(rows, start=2):
            total_tags += 1
            tag_name = (row.get("Tag Name") or "").strip()
            data_type = (row.get("Data Type") or "").strip()
            address = (row.get("Address") or "").strip()
            # ordinal keo tu dong dau tien cua file (dem chung trong device)
            ordinal = i - 1

            if not tag_name:
                errors.append(f"{rel}:{i}: Tag Name rong")
                continue
            if tag_name in seen_local:
                errors.append(f"{rel}:{i}: trung Tag Name '{tag_name}' trong file")
            seen_local.add(tag_name)

            if data_type not in KEPWARE_TYPES:
                errors.append(
                    f"{rel}:{i}: Data Type '{data_type}' khong phai ten kieu Kepware"
                )

            # 4. Address theo quy tac tag simulator
            m = ADDRESS_RE.match(address)
            if not m:
                errors.append(
                    f"{rel}:{i}: Address '{address}' sai format. "
                    f"Phai la <B|K|S> + {ADDRESS_DIGITS} chu so (vd B0000, K0010)"
                )
            else:
                prefix, number = m.group(1), int(m.group(2))
                # Dung chung ham sinh Address voi generator de tranh phan ky.
                exp_list = expected_addresses.get(channel, {}).get(device, [])
                try:
                    expected_address = (
                        exp_list[i - 2] if i - 2 < len(exp_list)
                        else make_address(data_type, ordinal)
                    )
                except ValueError:
                    expected_address = None
                if expected_address and address != expected_address:
                    errors.append(
                        f"{rel}:{i}: Address '{address}' — phai la "
                        f"'{expected_address}' (ordinal dem lien tuc trong CHANNEL, "
                        f"gian cach {ADDRESS_STRIDE} don vi)"
                    )
                try:
                    expected_prefix = address_prefix(data_type)
                except ValueError:
                    expected_prefix = None
                if expected_prefix and prefix != expected_prefix:
                    errors.append(
                        f"{rel}:{i}: Address '{address}' sai tien do. "
                        f"Data Type '{data_type}' phai dung tien do "
                        f"'{expected_prefix}'"
                    )
                if address in seen_addresses:
                    errors.append(f"{rel}:{i}: Address '{address}' trung trong file")
                seen_addresses.add(address)

        # 5. Khớp với file nguồn
        src = src_root / rel
        if not src.exists():
            errors.append(f"{rel}: khong tim thay file nguon {src}")
        else:
            with src.open("r", encoding="utf-8-sig", newline="") as f:
                src_rows = list(csv.DictReader(f))
            if len(src_rows) != len(rows):
                errors.append(
                    f"{rel}: so dong khong khop voi nguon "
                    f"({len(rows)} vs {len(src_rows)})"
                )
            src_names = {(r.get("Tag Name") or "").strip() for r in src_rows}
            if src_names != seen_local:
                errors.append(
                    f"{rel}: tap Tag Name khong khop voi nguon "
                    f"(thieu {sorted(src_names - seen_local)[:3]}, "
                    f"thua {sorted(seen_local - src_names)[:3]})"
                )

    # Address duy nhat TRONG CHANNEL (khong chi trong 1 device)
    for channel, devices in channel_files.items():
        seen: dict[str, str] = {}
        for device in sorted(devices):
            for _dt, address in devices[device]:
                if address in seen:
                    errors.append(
                        f"{channel}/{device}: Address '{address}' trung trong CHANNEL "
                        f"voi {seen[address]} — se bi ghi de khi import Kepware"
                    )
                else:
                    seen[address] = f"{channel}/{device}"

    # Tổng kết
    print(f"Tong so file : {len(files)}")
    print(f"Tong so tag  : {total_tags}")

    if errors:
        print(f"\nLOI ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nOK: khong co loi.")

    if warnings:
        print(f"\nCanh bao ({len(warnings)}):")
        for w in warnings[:20]:
            print(f"  - {w}")
        if len(warnings) > 20:
            print(f"  ... va {len(warnings) - 20} canh bao khac")
    else:
        print("Canh bao: 0")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
