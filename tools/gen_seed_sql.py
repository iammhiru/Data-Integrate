#!/usr/bin/env python
"""
Sinh `postgres/init/02_seed_master_data.sql` tu `config/master_data.json`.

Muc dich: SQL seed luôn KHỚP với master data JSON (va JSON sinh tu
`catalog.json` cua dong doi) — khong con so "100 may gia lap" nao lao.

Chay:  python tools/gen_seed_sql.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "config" / "master_data.json"
OUT = ROOT / "postgres" / "init" / "02_seed_master_data.sql"

HEADER = """-- ============================================================================
--  MASTER DATA — seed tu `config/master_data.json`.
--  SINH TU DONG: `python tools/gen_seed_sql.py` (KHONG sua tay file nay).
--
--  Nguon du lieu:
--    · 26 may  <- IndustrialTelemetry.Middleware/metadata/catalog.json
--                 (dung voi middleware, dong doi day len)
--    · SKU     <- khai bao trong tools/gen_master_data.py
--    · Ideal Cycle Time <- DesignSpeed thuc te doc tu state-api
--  Moi truong: CHAY LAI khi doi master data:
--    docker compose -f docker-compose.server.yml exec -T postgres \\
--        psql -U sf_user -d smart_factory \\
--        -f /docker-entrypoint-initdb.d/02_seed_master_data.sql
-- ============================================================================

"""


def q(v) -> str:
    """Escape chuoi cho Postgres (dong keo len)."""
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def main() -> None:
    with SRC.open("r", encoding="utf-8") as fh:
        d = json.load(fh)

    L: list[str] = [HEADER]

    # ── product ───────────────────────────────────────────────────────────
    L.append("-- San pham (SKU) + Ideal Cycle Time (giay/san pham).\n")
    L.append("INSERT INTO product (product_id, product_name, ideal_cycle_time_sec) VALUES")
    rows = []
    for p in d["products"]:
        ict = p["ideal_cycle_time_sec"]
        rows.append(f"    ({q(p['product_id'])}, {q(p['product_name'])}, {q(ict)})")
    L.append(",\n".join(rows) + "\nON CONFLICT (product_id) DO UPDATE SET\n"
             "    product_name = EXCLUDED.product_name,\n"
             "    ideal_cycle_time_sec = EXCLUDED.ideal_cycle_time_sec;\n")

    # ── shift ─────────────────────────────────────────────────────────────
    L.append("\n-- Ca san xuat. Planned Production Time = planned_minutes - planned_break_minutes.\n")
    L.append("INSERT INTO shift (shift_id, shift_name, start_time, end_time, planned_minutes, planned_break_minutes) VALUES")
    rows = []
    for s in d["shifts"]:
        rows.append(
            f"    ({q(s['shift_id'])}, {q(s['shift_name'])}, {q(s['start_time'])}, "
            f"{q(s['end_time'])}, {q(s['planned_minutes'])}, {q(s['planned_break_minutes'])})"
        )
    L.append(",\n".join(rows) + "\nON CONFLICT (shift_id) DO UPDATE SET\n"
             "    shift_name = EXCLUDED.shift_name,\n"
             "    start_time = EXCLUDED.start_time,\n"
             "    end_time = EXCLUDED.end_time,\n"
             "    planned_minutes = EXCLUDED.planned_minutes,\n"
             "    planned_break_minutes = EXCLUDED.planned_break_minutes;\n")

    # ── line ──────────────────────────────────────────────────────────────
    L.append("\n-- Dong chay san xuat. `reference_process` = cong doan CHIET (ra san pham chinh).\n")
    L.append("INSERT INTO line (line_id, line_name, channel, reference_process, product_id, unit) VALUES")
    rows = []
    for ln in d["lines"]:
        rows.append(
            f"    ({q(ln['line_id'])}, {q(ln['display_name'])}, {q(ln['channel'])}, "
            f"{q(ln['reference_process'])}, {q(ln['product_id'])}, {q(ln['unit'])})"
        )
    L.append(",\n".join(rows) + "\nON CONFLICT (line_id) DO UPDATE SET\n"
             "    line_name = EXCLUDED.line_name,\n"
             "    channel = EXCLUDED.channel,\n"
             "    reference_process = EXCLUDED.reference_process,\n"
             "    product_id = EXCLUDED.product_id,\n"
             "    unit = EXCLUDED.unit;\n")

    # ── machine ───────────────────────────────────────────────────────────
    L.append("\n-- 26 may that (catalog.json). `ideal_speed` = DesignSpeed thuc te.\n")
    L.append("INSERT INTO machine (machine_id, machine_name, line, machine_type, location, ideal_speed, installed_at) VALUES")
    rows = []
    for m in d["machines"]:
        rows.append(
            f"    ({q(m['machine_id'])}, {q(m['machine_name'])}, {q(m['line_id'])}, "
            f"{q(m['machine_type'])}, {q(m['location'])}, {q(m['design_speed'])}, DATE '2026-01-01')"
        )
    L.append(",\n".join(rows) + "\nON CONFLICT (machine_id) DO UPDATE SET\n"
             "    machine_name = EXCLUDED.machine_name,\n"
             "    line = EXCLUDED.line,\n"
             "    machine_type = EXCLUDED.machine_type,\n"
             "    location = EXCLUDED.location,\n"
             "    ideal_speed = EXCLUDED.ideal_speed;\n")

    # ── machine_id_mapping ────────────────────────────────────────────────
    L.append("\n-- Chu hoa ID tu cac nguon khac nhau -> machineId.\n")
    L.append("INSERT INTO machine_id_mapping (source, source_id, machine_id) VALUES")
    rows = []
    for source, items in d["id_mapping"].items():
        for it in items:
            rows.append(f"    ({q(source)}, {q(it['source_id'])}, {q(it['machine_id'])})")
    L.append(",\n".join(rows) + "\nON CONFLICT (source, source_id) DO UPDATE SET\n"
             "    machine_id = EXCLUDED.machine_id;\n")

    # ── work_order ────────────────────────────────────────────────────────
    L.append("\n-- Work order (don hang san xuat). Trang thai RUNNING = dang chay.\n")
    L.append("INSERT INTO work_order (wo_id, wo_code, line_id, product_id, shift_id, planned_qty, status, actual_start_time) VALUES")
    rows = []
    for w in d["work_orders"]:
        rows.append(
            f"    ({q(w['wo_id'])}, {q(w['wo_code'])}, {q(w['line_id'])}, {q(w['product_id'])}, "
            f"{q(w.get('shift_id'))}, {q(w['planned_qty'])}, {q(w['status'])}, now())"
        )
    L.append(",\n".join(rows) + "\nON CONFLICT (wo_id) DO UPDATE SET\n"
             "    wo_code = EXCLUDED.wo_code,\n"
             "    line_id = EXCLUDED.line_id,\n"
             "    product_id = EXCLUDED.product_id,\n"
             "    shift_id = EXCLUDED.shift_id,\n"
             "    planned_qty = EXCLUDED.planned_qty,\n"
             "    status = EXCLUDED.status;\n")

    # ── production_plan ───────────────────────────────────────────────────
    L.append("\n-- Ke hoach san luong theo line + ca.\n")
    L.append("INSERT INTO production_plan (line_id, shift_id, product_id, plan_date, planned_qty, theoretical_qty) VALUES")
    rows = []
    for pl in d["production_plans"]:
        rows.append(
            f"    ({q(pl['line_id'])}, {q(pl['shift_id'])}, {q(pl['product_id'])}, CURRENT_DATE, "
            f"{q(pl['planned_qty'])}, {q(pl['theoretical_qty'])})"
        )
    L.append(",\n".join(rows) + "\nON CONFLICT (line_id, shift_id, plan_date) DO UPDATE SET\n"
             "    product_id = EXCLUDED.product_id,\n"
             "    planned_qty = EXCLUDED.planned_qty,\n"
             "    theoretical_qty = EXCLUDED.theoretical_qty;\n")

    L.append(
        "\n-- GHI CHU:\n"
        "--   counter_baseline KHONG seed — no duoc GHI RUNTIME khi work order bat dau\n"
        "--   (bo dem may tich luy tu lan bat nguon, khong reset theo ca/WO).\n"
        "--   Phase 2 se chen moc nay tu dong khi nhan su kien WO_START.\n"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"OK -> {OUT}")


if __name__ == "__main__":
    main()
