r"""
Kiem tra ket noi toi PostgreSQL master + do bang master data.

Dung (may Windows, sau khi da cai PG tren may server):
    .\.venv\Scripts\python.exe scripts\check_master_db.py
    .\.venv\Scripts\python.exe scripts\check_master_db.py --url "postgres://sf_user:sf_password@192.168.179.176:5432/smart_factory"

Exit code: 0 = OK, 1 = loi (ket noi / thieu bang / thieu du lieu).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

# Bang master + so luoc ban ghi mong doi (khop voi 02_seed_master_data.sql).
EXPECTED = [
    ("machine", 26),
    ("product", 3),
    ("line", 3),
    ("shift", 3),
    ("work_order", 9),
    ("production_plan", 9),
]


def load_env() -> None:
    """Nap bien tu .env o goc repo (neu co) — giong run-master-api.ps1."""
    if not ENV_FILE.exists():
        return
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, val = line.partition("=")
        name = name.strip()
        val = val.strip().strip('"').strip("'")
        if name and not os.environ.get(name):
            os.environ[name] = val


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=None, help="MASTER_DB_URL (mac dinh lay tu .env)")
    args = ap.parse_args()

    load_env()
    url = args.url or os.getenv("MASTER_DB_URL", "")
    if not url:
        print("[!] Chua co MASTER_DB_URL. Dat trong .env o goc repo hoac dung --url.")
        print("    Vi du: --url postgres://sf_user:sf_password@192.168.179.176:5432/smart_factory")
        return 1

    # Che do an thong tin mat khau khi in ra log.
    safe = url.split("@")[-1]
    print(f"[*] Thu ket noi toi PostgreSQL: ...@{safe}")

    try:
        import psycopg2
    except ImportError:
        print("[!] Chua cai psycopg2. Chay: .\\.venv\\Scripts\\python.exe -m pip install psycopg2-binary")
        return 1

    try:
        conn = psycopg2.connect(url, connect_timeout=8)
        conn.autocommit = True
    except Exception as exc:  # noqa: BLE001
        print(f"[X] KHONG KET NOI DUOC: {exc}")
        print()
        print("    Kiem tra:")
        print("      1. Postgres da chay tren server?      docker compose ps")
        print("      2. Firewall da mo 5432?               sudo ufw allow 5432/tcp")
        print("      3. User/db dung?                     xem .env tren server")
        print("      4. Port bi chiem?                    doi sang 15432")
        return 1

    print("[OK] Ket noi thanh cong.\n")
    ok = True
    with conn.cursor() as cur:
        for table, expected in EXPECTED:
            try:
                cur.execute(f"SELECT count(*) FROM {table}")
                n = cur.fetchone()[0]
            except Exception as exc:  # noqa: BLE001
                print(f"  [X] {table:<20} loi: {exc}")
                ok = False
                continue
            mark = "OK " if n == expected else "!! "
            note = "" if n == expected else f"  (mong doi {expected})"
            print(f"  [{mark}] {table:<20} {n:>5} dong{note}")
            if n != expected:
                ok = False

        # Xem mau du lieu de kiem tra dung hinh thuc
        try:
            cur.execute(
                "SELECT product_id, product_name, ideal_cycle_time_sec "
                "FROM product ORDER BY product_id"
            )
            print("\n  SKU:")
            for row in cur.fetchall():
                print(f"    {row[0]:<16} {row[1]:<28} ICT={row[2]}")
        except Exception:  # noqa: BLE001
            pass

        try:
            cur.execute(
                "SELECT line_id, shift_id, planned_qty FROM production_plan "
                "ORDER BY line_id, shift_id"
            )
            print("\n  Ke hoach san luong:")
            for row in cur.fetchall():
                print(f"    {row[0]:<10} ca {row[1]}  planned_qty={row[2]}")
        except Exception:  # noqa: BLE001
            pass

    conn.close()
    print()
    print("[OK] Master data PostgreSQL san sang." if ok else
          "[!] Co bang/so lieu chua khop — xem lai seed (docs/deploy-remote-infra.md muc 5.3).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
