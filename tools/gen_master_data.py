#!/usr/bin/env python
"""
Sinh `config/master_data.json` — NGUỒN SỰ THẬT DUY NHẤT cho master data.

Dữ liệu lấy từ:
  · `IndustrialTelemetry.Middleware/metadata/catalog.json`  → 26 máy (machineId,
    equipmentCode, line, process, tag list). Đây là file ĐỒNG ĐỘI đẩy lên,
    dùng chung với middleware → không tự bịa danh sách máy.
  · `config/design_speed.json`                              → DesignSpeed thực
    tế đọc từ `state-api` (đơn vị pcs/min) dùng để suy ra Ideal Cycle Time.

Phần ĐỊNH NGHĨA NGHIỆP VỤ (SKU, ca, work order) khai báo ngay trong file này —
cố ý TÁCH khỏi dữ liệu máy để sau này nhập từ ERP/MES thật chỉ cần sửa 1 chỗ.

Output: config/master_data.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "IndustrialTelemetry.Middleware" / "metadata" / "catalog.json"
DESIGN_SPEED = ROOT / "config" / "design_speed.json"
OUT = ROOT / "config" / "master_data.json"

PLANT_ID = "PLANT_01"

# ---------------------------------------------------------------------------
# Định nghĩa nghiệp vụ (thay bằng ERP/MES thật sau)
# ---------------------------------------------------------------------------

# Ca sản xuất — khớp với `shift` trong PostgreSQL (docs/architecture.txt §4.3)
SHIFTS = [
    {"shift_id": "A", "shift_name": "Ca A", "start_time": "06:00", "end_time": "14:00",
     "planned_minutes": 480, "planned_break_minutes": 30},
    {"shift_id": "B", "shift_name": "Ca B", "start_time": "14:00", "end_time": "22:00",
     "planned_minutes": 480, "planned_break_minutes": 30},
    {"shift_id": "C", "shift_name": "Ca C", "start_time": "22:00", "end_time": "06:00",
     "planned_minutes": 480, "planned_break_minutes": 30},
]

# Line sản xuất. `reference_process` = công đoạn CHIẾT (ra sản phẩm chính,
# đơn vị pcs) → dùng bộ đếm của máy này cho Performance/Quality.
LINES = [
    {
        "line_id": "LINE_01",
        "display_name": "Chai PET — có ga",
        "channel": "LINE_01",
        "reference_process": "FILLING",
        "product_id": "PET-500-COKE",
        "product_name": "Nước có ga 500ml",
        "unit": "bottles",
    },
    {
        "line_id": "LINE_02",
        "display_name": "Chai PET — không ga",
        "channel": "LINE_02",
        "reference_process": "FILLING",
        "product_id": "PET-500-WATER",
        "product_name": "Nước khoáng 500ml",
        "unit": "bottles",
    },
    {
        "line_id": "LINE_03",
        "display_name": "Lon nhôm",
        "channel": "LINE_03",
        "reference_process": "FILLING",
        "product_id": "CAN-330-SUGAR",
        "product_name": "Nước giải khát lon 330ml",
        "unit": "cans",
    },
]

# Sản phẩm (SKU). `ideal_cycle_time_sec` được SUY RA từ DesignSpeed của máy
# tham chiếu — nếu không có DesignSpeed thì để null và ghi chú thủ công.
PRODUCTS = [
    {"product_id": "PET-500-COKE", "product_name": "Nước có ga 500ml", "line_id": "LINE_01"},
    {"product_id": "PET-500-WATER", "product_name": "Nước khoáng 500ml", "line_id": "LINE_02"},
    {"product_id": "CAN-330-SUGAR", "product_name": "Nước giải khát lon 330ml", "line_id": "LINE_03"},
]

# Work order mẫu (trạng thái RUNNING → dùng ngay cho tính OEE).
# `planned_qty` = planned production time × công suất × OEE mục tiêu (90%).
# Mỗi ca một WO — để khi đổi ca thì kế hoạch và work order đi theo ca.
WORK_ORDER_TEMPLATE = {
    "LINE_01": {"wo_code": "WO-2611-1301", "product_id": "PET-500-COKE", "planned_qty": 57400},
    "LINE_02": {"wo_code": "WO-2611-1302", "product_id": "PET-500-WATER", "planned_qty": 52600},
    "LINE_03": {"wo_code": "WO-2611-1303", "product_id": "CAN-330-SUGAR", "planned_qty": 44000},
}

# Thiết bị dùng chung (không thuộc line nào) — CIP.
SHARED_EQUIPMENT = ["CIP_SKID_01"]

# Nguồn ID khác nhau → machineId (bảng `machine_id_mapping`).
# `source` = tên nguồn trong middleware (`source.system`).
ID_MAPPING_SOURCE = "kepware"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    catalog = load_json(CATALOG)
    speeds = load_json(DESIGN_SPEED) if DESIGN_SPEED.exists() else {}

    machines = []
    for m in catalog["machines"]:
        mid = m["machineId"]
        line_id = m.get("lineId") or "SHARED"
        machines.append(
            {
                "machine_id": mid,
                "machine_name": mid,
                "machine_type": m.get("machineType"),
                "line_id": line_id,
                "channel": m.get("channel"),
                "process_id": m.get("processId"),
                "equipment_code": m.get("equipmentCode"),
                "location": PLANT_ID,
                "design_speed": speeds.get(mid, {}).get("design_speed"),
                "design_speed_unit": speeds.get(mid, {}).get("unit"),
                "is_producer": line_id != "SHARED",
            }
        )

    # Ideal Cycle Time của SKU ← DesignSpeed máy tham chiếu của line.
    ref_speed: dict[str, float] = {}
    for line in LINES:
        cand = [
            mm for mm in machines
            if mm["line_id"] == line["line_id"] and mm["process_id"] == line["reference_process"]
        ]
        for mm in cand:
            if mm["design_speed"]:
                ref_speed[line["line_id"]] = float(mm["design_speed"])
                break

    products = []
    for p in PRODUCTS:
        speed = ref_speed.get(p["line_id"])
        products.append(
            {
                **p,
                "ideal_cycle_time_sec": round(60.0 / speed, 4) if speed else None,
                "design_speed": speed,
            }
        )

    # Kế hoạch sản lượng cho MỌI ca (frontend luôn lấy ca hiện tại).
    # planned production time = (480 − 30 nghỉ) × 60 = 27.000 giây
    planned_seconds = (480 - 30) * 60
    plans = []
    work_orders = []
    for line in LINES:
        prod = next(p for p in products if p["product_id"] == line["product_id"])
        ict = prod["ideal_cycle_time_sec"]
        tpl = WORK_ORDER_TEMPLATE[line["line_id"]]
        theoretical = round(planned_seconds / ict) if ict else None
        for shift in SHIFTS:
            plans.append(
                {
                    "line_id": line["line_id"],
                    "product_id": line["product_id"],
                    "shift_id": shift["shift_id"],
                    "planned_qty": tpl["planned_qty"],
                    "theoretical_qty": theoretical,
                    "unit": line["unit"],
                }
            )
            work_orders.append(
                {
                    "wo_id": f"WO-2026-11-13-{line['line_id']}-{shift['shift_id']}",
                    "wo_code": f"{tpl['wo_code']}-{shift['shift_id']}",
                    "line_id": line["line_id"],
                    "product_id": tpl["product_id"],
                    "planned_qty": tpl["planned_qty"],
                    "shift_id": shift["shift_id"],
                    "status": "RUNNING",
                }
            )

    out = {
        "plant_id": PLANT_ID,
        "shifts": SHIFTS,
        "lines": LINES,
        "products": products,
        "machines": machines,
        "work_orders": work_orders,
        "production_plans": plans,
        "id_mapping": {
            ID_MAPPING_SOURCE: [
                {"source_id": mm["equipment_code"], "machine_id": mm["machine_id"]}
                for mm in machines
                if mm["equipment_code"]
            ]
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"OK -> {OUT}  ({len(machines)} máy, {len(products)} SKU, {len(work_orders)} WO)")


if __name__ == "__main__":
    main()
