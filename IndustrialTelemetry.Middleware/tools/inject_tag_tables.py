"""
tools/inject_tag_tables.py
──────────────────────────
Chèn bảng tag đã sinh (từ ``gen_tag_tables.py``) vào tài liệu bàn giao,
thay khối:

    <!-- BEGIN GENERATED TAG TABLES -->
    ...
    <!-- END GENERATED TAG TABLES -->

Cách chạy (từ thư mục IndustrialTelemetry.Middleware/):
    python tools/gen_tag_tables.py --out _tag_tables.md
    python tools/inject_tag_tables.py --tables _tag_tables.md \
        --doc ../kafka_data_contract_and_storage_guide.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BEGIN = "<!-- BEGIN GENERATED TAG TABLES -->"
END = "<!-- END GENERATED TAG TABLES -->"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", default="_tag_tables.md")
    parser.add_argument("--doc", default="../kafka_data_contract_and_storage_guide.md")
    args = parser.parse_args()

    tables = Path(args.tables).read_text(encoding="utf-8").strip()
    doc_path = Path(args.doc).resolve()
    doc = doc_path.read_text(encoding="utf-8")

    if BEGIN not in doc or END not in doc:
        print("Không tìm thấy marker trong doc.", file=sys.stderr)
        return 1

    head, rest = doc.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    new_doc = f"{head}{BEGIN}\n\n{tables}\n\n{END}{tail}"

    doc_path.write_text(new_doc, encoding="utf-8")
    print(f"Đã chèn bảng tag vào {doc_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
