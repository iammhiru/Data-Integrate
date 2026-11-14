"""Tao WO co thoi gian chay trong khoang du lieu thật (13/11) de test gan wo_id.

Script nay chen truc tiep vao DB (khong qua API) de mock 'lenh da chay
trong khoang co du lieu raw' -> chay backfill de kiem tra batch_kpi gan
dung wo_id vao machine_kpi_1m.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\seed_test_wo.py
"""
from __future__ import annotations

import os

import psycopg

DSN = os.getenv(
    "SF_PG_DSN",
    "postgresql://sf_user:sf_password@192.168.179.176:5432/smart_factory",
)

# Khoang co du lieu raw that: 13/11/2026 07:00 - 13:00 (UTC+7) -> 00:00 - 06:00 UTC
LINE = "LINE_01"
WO_ID = "WO-TEST-20261113-LINE_01"
START = "2026-11-13 00:00:00+00"
END = "2026-11-13 06:00:00+00"

with psycopg.connect(DSN, autocommit=True) as c:
    with c.cursor() as cur:
        cur.execute("DELETE FROM work_order WHERE wo_id = %s", (WO_ID,))
        cur.execute(
            "INSERT INTO work_order "
            "  (wo_id, wo_code, line_id, product_id, shift_id, planned_qty, status, "
            "   planned_start, planned_end, actual_start_time, actual_end_time, seq, unit, note) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'COMPLETED', %s, %s, %s, %s, 99, 'bottles', %s) "
            "RETURNING wo_id, wo_code, status, actual_start_time, actual_end_time",
            (WO_ID, "WO-TEST-2611-1301", LINE, "PET-500-COKE", "A", 57400,
             START, END, START, END, "WO test de kiem tra gan wo_id trong batch"),
        )
        print("da tao WO test:", cur.fetchone())
        cur.execute("DELETE FROM work_order_log WHERE wo_id = %s", (WO_ID,))
        cur.execute(
            "INSERT INTO work_order_log (wo_id, action, old_status, new_status, action_by, message) "
            "VALUES (%s, 'CREATE', NULL, 'DRAFT', 'seed', 'seed test')", (WO_ID,))
        print("OK")
