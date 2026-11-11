# -*- coding: utf-8 -*-
"""
Sinh ban CSV "sach" de import thang vao Kepware.

Bo 3 cot phu cua project:
    - TagType
    - TagCode
    - Acquisition Class

Giu nguyen 17 cot chuan cua Kepware (export/import):
    Tag Name, Address, Data Type, Respect Data Type, Client Access,
    Scan Rate, Scaling, Raw Low, Raw High, Scaled Low, Scaled High,
    Scaled Data Type, Clamp Low, Clamp High, Eng Units, Description,
    Negate Value

Nguon: doc truc tiep tu metadata/TAG_FOLDER/ (de khong lech phai cai da
validate) va chi bo cot. Cach nay bao dam file import co dung du lieu
da duyet, chi khac phan tieu chuong duoc rut gon.

Usage:
    python tools/generate_kepware_import_csv.py
    python tools/generate_kepware_import_csv.py --out metadata/KEPWARE_IMPORT
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

# 17 cot chuan cua Kepware (khong con "TagType")
KEPWARE_COLUMNS: list[str] = [
    "Tag Name", "Address", "Data Type", "Respect Data Type", "Client Access",
    "Scan Rate", "Scaling", "Raw Low", "Raw High", "Scaled Low",
    "Scaled High", "Scaled Data Type", "Clamp Low", "Clamp High",
    "Eng Units", "Description", "Negate Value",
]

# 3 cot phu cua project - loai bo khi xuat ban import
DROP_COLUMNS: list[str] = ["TagType", "TagCode", "Acquisition Class"]

#: Thu goc project (IndustrialTelemetry.Middleware/) — dung de resolve duong dan
#: tuong doi trong CLI (vi du "metadata/TAG_FOLDER").
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(raw: str) -> Path:
    """Chuyen duong dan tuong doi (theo PROJECT_ROOT) thanh Path tuyet doi."""
    path = Path(raw)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()



def strip_columns(src: Path, dst: Path) -> int:
    """Doc CSV nguon, bo cot phu, ghi CSV dich. Tra ve so dong du lieu."""
    with src.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    missing = [c for c in KEPWARE_COLUMNS if c not in fieldnames]
    if missing:
        raise SystemExit(
            f"{src.name}: thieu cot chuan cua Kepware: {missing}"
        )

    # Chi giu 17 cot chuan, dung thu tu cua Kepware.
    out_rows = []
    for row in rows:
        out_rows.append({col: row.get(col, "") for col in KEPWARE_COLUMNS})

    dst.parent.mkdir(parents=True, exist_ok=True)
    # Ghi BOM UTF-8: Kepware export CSV luôn có BOM, Excel/Kepware doc BOM
    # thi "utf-8-sig" -> khop voi file export goc.
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=KEPWARE_COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)

    return len(out_rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="metadata/TAG_FOLDER")
    ap.add_argument("--out", default="metadata/KEPWARE_IMPORT")
    args = ap.parse_args()


    src_root = _resolve(args.src)
    out_root = _resolve(args.out)

    if not src_root.exists():
        raise SystemExit(f"Khong tim thay: {src_root}")

    total_tags = 0
    total_files = 0

    for channel_dir in sorted(p for p in src_root.iterdir() if p.is_dir()):
        for csv_path in sorted(channel_dir.glob("*.csv")):
            rel = csv_path.relative_to(src_root)
            dst = out_root / rel
            n = strip_columns(csv_path, dst)
            total_tags += n
            total_files += 1
            print(f"  {rel}  ({n} tag)")

    print()
    print(f"Da sinh {total_files} file CSV, {total_tags} tag -> {out_root}")
    print(f"Da bo cot: {', '.join(DROP_COLUMNS)}")
    print(f"Cot giu lai ({len(KEPWARE_COLUMNS)}): {', '.join(KEPWARE_COLUMNS)}")


if __name__ == "__main__":
    main()
