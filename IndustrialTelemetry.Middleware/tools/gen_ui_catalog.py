"""
tools/gen_ui_catalog.py
───────────────────────
Sinh file TypeScript cho UI từ ``metadata/catalog.json`` của middleware.

Mục đích: UI **không** copy tay danh sách máy/tag. File sinh ra là build
artifact, commit cùng repo để frontend không cần chạy Python, nhưng luôn
bám sát catalog gốc.

Usage:
    python tools/gen_ui_catalog.py [--check]

``--check`` chỉ so sánh và trả exit code 1 nếu file đã lệch (dùng cho CI).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "metadata" / "catalog.json"
OUT = ROOT.parent / "dashboard" / "frontend" / "src" / "mock" / "catalog.gen.ts"

HEADER = """// ============================================================================
//  AUTO-GENERATED — DO NOT EDIT
//  Nguồn: IndustrialTelemetry.Middleware/metadata/catalog.json
//  Sinh bởi: tools/gen_ui_catalog.py
//  Regenerate: python tools/gen_ui_catalog.py
// ============================================================================

export type TagDef = {
  name: string;
  dataType: string;
  unit: string | null;
  tagType: string;
  tagCode: string;
  meaning: string;
};

export type MachineDef = {
  machineId: string;
  machineType: string;
  equipmentCode: string;
  channel: string;
  lineId: string;
  processId: string;
  tags: TagDef[];
};

export const PLANT_ID = "%(plantId)s";
export const TOTAL_TAGS = %(totalTags)d;
export const TOTAL_MACHINES = %(totalMachines)d;
export const MACHINES: MachineDef[] = %(machines)s;
"""


def ts(value: object) -> str:
    """Chuyển giá trị Python sang literal TypeScript (JSON gần như tương đương)."""
    return json.dumps(value, ensure_ascii=False, indent=2)


def build() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    machines = []
    for m in data["machines"]:
        machines.append(
            {
                "machineId": m["machineId"],
                "machineType": m["machineType"],
                "equipmentCode": m["equipmentCode"],
                "channel": m["channel"],
                "lineId": m["lineId"],
                "processId": m["processId"],
                "tags": [
                    {
                        "name": t["name"],
                        "dataType": t["dataType"],
                        "unit": None if t.get("unit") in (None, "-") else t.get("unit"),
                        "tagType": t.get("tagType", ""),
                        "tagCode": t["tagCode"],
                        "meaning": t.get("meaning", ""),
                    }
                    for t in m["tags"]
                ],
            }
        )
    body = HEADER % {
        "plantId": data["plantId"],
        "totalTags": data["totalTags"],
        "totalMachines": data["totalMachines"],
        "machines": ts(machines),
    }
    # Gộp "machines: [ ... ]" vào một dòng để file gọn.
    return body.replace(": [", ": [").rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    content = build()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != content:
            print("FAIL: catalog.gen.ts lệch với catalog.json — cần regenerate")
            return 1
        print("OK: catalog.gen.ts khớp catalog.json")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
