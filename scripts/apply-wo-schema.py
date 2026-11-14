"""Apply 04_work_order_schema.sql vao PostgreSQL tren may server.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\apply-wo-schema.py
"""
from __future__ import annotations

import os
import sys

import psycopg

DSN = os.getenv(
    "SF_PG_DSN",
    "postgresql://sf_user:sf_password@192.168.179.176:5432/smart_factory",
)
SQL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "postgres", "init", "04_work_order_schema.sql",
)

with psycopg.connect(DSN, autocommit=True) as c:
    sql = open(SQL, encoding="utf-8").read()
    with c.cursor() as cur:
        cur.execute(sql)
    print("OK: da chay 04_work_order_schema.sql")

    with c.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='work_order' ORDER BY ordinal_position")
        print("\n--- work_order ---")
        for r in cur.fetchall():
            print("  ", r[0], r[1])

        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename IN ('work_order_log','counter_baseline',"
                    "'work_order_progress','work_order_running') ORDER BY 1")
        print("\n--- doi tuong moi ---")
        for r in cur.fetchall():
            print("  ", r[0])

        cur.execute("SELECT wo_id, line_id, status, seq FROM work_order ORDER BY line_id, seq")
        print("\n--- work_order sau migrate ---")
        for r in cur.fetchall():
            print("  ", r)
