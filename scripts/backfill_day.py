"""Tao partition + chay backfill cho mot ngay (de verify du lieu THAT tu MinIO raw).

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\backfill_day.py 2026-11-11
"""
from __future__ import annotations

import os
import sys

import psycopg

DSN = os.getenv(
    "SF_PG_DSN",
    "postgresql://sf_user:sf_password@192.168.179.176:5432/smart_factory",
)

day = sys.argv[1] if len(sys.argv) > 1 else "2026-11-11"

with psycopg.connect(DSN, autocommit=True) as c:
    with c.cursor() as cur:
        cur.execute("SELECT batch_ensure_partitions(%s::date, %s::date)",
                    (day, day))
        print(f"OK: partition cho {day}")
        cur.execute(
            "select c.relname, pg_get_expr(c.relpartbound, c.oid) "
            "from pg_class c join pg_inherits i on i.inhrelid = c.oid "
            "where c.relname like 'machine_kpi_1m_2%' order by 1")
        for r in cur.fetchall():
            print("   ", r[0], "|", r[1])
