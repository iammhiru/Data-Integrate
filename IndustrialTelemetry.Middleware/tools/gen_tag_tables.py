"""
tools/gen_tag_tables.py
───────────────────────
Sinh bảng Markdown danh mục tag từ ``metadata/catalog.json``.

Dùng để cập nhật phần "Catalog tag đầy đủ" trong tài liệu bàn giao
(``kafka_data_contract_and_storage_guide.md``) mà không phải gõ tay 404 dòng.

Cách chạy (từ thư mục IndustrialTelemetry.Middleware/):
    python tools/gen_tag_tables.py --out tag_tables.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.value_types import opcua_type_for  # noqa: E402

#: Thứ tự ưu tiên hiển thị máy theo line rồi process.
PROCESS_ORDER = [
    "PREFORM_FEEDING",
    "BLOW_MOULDING",
    "BOTTLE_CONVEYING",
    "RINSING",
    "FILLING",
    "CAPPING",
    "LABELLING",
    "CODING",
    "CASE_PACKING",
    "CAN_DEPALLETTIZING",
    "SEAMING",
    "INSPECTION",
    "CIP",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="metadata/catalog.json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    if not catalog_path.is_absolute():
        catalog_path = (Path(__file__).resolve().parent.parent / catalog_path).resolve()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    machines = catalog["machines"]

    def sort_key(machine: dict) -> tuple:
        try:
            proc_idx = PROCESS_ORDER.index(machine.get("processId", ""))
        except ValueError:
            proc_idx = len(PROCESS_ORDER)
        return (machine.get("lineId", ""), proc_idx, machine.get("machineId", ""))

    lines: list[str] = []
    total_tags = 0

    lines.append("| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |")
    lines.append("|---|---|---|---|---|---|")

    for machine in sorted(machines, key=sort_key):
        machine_id = machine["machineId"]
        header = (
            f"### {machine_id} — {machine['machineType']}\n\n"
            f"- **Channel / Line:** `{machine['channel']}` / `{machine['lineId']}`  \n"
            f"- **Process:** `{machine['processId']}`  \n"
            f"- **Equipment code:** `{machine['equipmentCode']}`  \n"
            f"- **Số tag:** {len(machine['tags'])}\n"
        )
        lines.append("")
        lines.append(header)
        lines.append("| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |")
        lines.append("|---|---|---|---|---|---|")
        for tag in machine["tags"]:
            value_type = opcua_type_for(tag.get("dataType"))
            unit = tag.get("unit") or "-"
            if unit == "-":
                unit = "—"
            lines.append(
                f"| `{tag['tagCode']}` | `{tag['name']}` | `{value_type}` | {unit} "
                f"| {tag.get('tagType','')} | {tag.get('meaning','')} |"
            )
            total_tags += 1

    output = "\n".join(lines)
    print(f"Generated {total_tags} tag rows for {len(machines)} machines")

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(output, encoding="utf-8")
        print(f"Written to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
