"""
Master Data API — nguon master data cho frontend (dong chay, SKU, work order, ke hoach).

Vai tro trong kien truc:
    PostgreSQL (master)  ──┐
                           ├──> master-api (:8001) ──> Frontend (Vite :5173)
    config/master_data.json┘

Master data la DU LIEU TINH, khong phai du lieu do pipeline ghi vao. No duoc
nhap tu ERP/MES. O giai doan hien tai, `config/master_data.json` la nguon su
that duoc SINH TU DONG tu `catalog.json` cua dong doi + DesignSpeed doc tu
`state-api` (xem `tools/gen_master_data.py`).

Hai che do:
  · `MASTER_DB_URL` duoc dat  -> doc tu PostgreSQL (uu tien).
  · khong dat / PG khong ket noi -> doc tu `config/master_data.json` (fallback),
    de he van chay duoc khi chua co PostgreSQL.

Endpoints:
    GET /health                 trang thai + nguon dang dung (postgres | json)
    GET /api/master             toan bo master data (1 lan, frontend cache)
    GET /api/lines              dong chay + SKU + ke hoach + WO dang chay
    GET /api/lines/{line_id}    chi tiet 1 dong chay
    GET /api/products           danh sach SKU
    GET /api/work-orders?lineId= danh sach work order
    GET /api/shifts             ca san xuat
    GET /api/machines            danh sach may + master cua may
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

log = logging.getLogger("master-api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = Path(os.getenv("MASTER_JSON", str(ROOT / "config" / "master_data.json")))
DB_URL = os.getenv("MASTER_DB_URL", "")          # postgres://user:pass@host:5432/db
CACHE_TTL_SEC = float(os.getenv("MASTER_CACHE_TTL_SEC", "60"))


# ────────────────────────────────────────────────────────────── JSON fallback
def _load_json() -> dict[str, Any]:
    if not JSON_PATH.exists():
        return {"plant_id": "PLANT_01", "shifts": [], "lines": [], "products": [],
                "machines": [], "work_orders": [], "production_plans": [], "id_mapping": {}}
    with JSON_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ────────────────────────────────────────────────────────────── PostgreSQL
class PostgresSource:
    """Doc master data tu PostgreSQL. Neu khong ket noi duoc -> báo loi, caller fallback."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._lock = threading.Lock()
        self._conn = None
        self._psycopg = None

    def _connect(self):
        if self._conn is not None:
            return self._conn
        import psycopg2  # noqa: PLC0415 - import lai de khong hard-dep khi dung JSON
        import psycopg2.extras  # noqa: PLC0415

        self._conn = psycopg2.connect(self.url, connect_timeout=5)
        self._conn.autocommit = True
        self._psycopg = psycopg2.extras.RealDictCursor
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None

    def _query(self, sql: str, args: tuple = ()) -> list[dict]:
        conn = self._connect()
        with conn.cursor(cursor_factory=self._psycopg) as cur:
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]

    def snapshot(self) -> dict[str, Any]:
        """Tra ve master data cung shape voi ban JSON — frontend khong phan biet nguon."""
        products = self._query(
            "SELECT product_id, product_name, ideal_cycle_time_sec FROM product ORDER BY product_id"
        )
        shifts = self._query(
            "SELECT shift_id, shift_name, start_time, end_time, planned_minutes, planned_break_minutes "
            "FROM shift ORDER BY shift_id"
        )
        lines = self._query(
            "SELECT line_id, line_name, channel, reference_process, product_id, unit FROM line ORDER BY line_id"
        )
        machines = self._query(
            "SELECT machine_id, machine_name, line AS line_id, machine_type, location, ideal_speed "
            "FROM machine ORDER BY machine_id"
        )
        work_orders = self._query(
            "SELECT wo_id, wo_code, line_id, product_id, shift_id, planned_qty, status, "
            "planned_start, planned_end, actual_start_time, actual_end_time, "
            "released_at, released_by, operator_id, note, seq, unit, paused_at "
            "FROM work_order ORDER BY wo_id"
        )
        # ⚠ Kế hoạch được seed theo `CURRENT_DATE` (ngày khởi tạo DB). Nếu
        #   chạy qua ngày mới, dòng đó không còn khớp → lấy kế hoạch GẦN NHẤT
        #   đã có (plan_date <= hôm nay), ưu tiên bản mới nhất.
        plans = self._query(
            "SELECT DISTINCT ON (line_id, shift_id) "
            "       line_id, shift_id, product_id, plan_date, planned_qty, theoretical_qty "
            "FROM production_plan "
            "WHERE plan_date <= CURRENT_DATE "
            "ORDER BY line_id, shift_id, plan_date DESC"
        )
        mapping = self._query(
            "SELECT source, source_id, machine_id FROM machine_id_mapping ORDER BY source, source_id"
        )

        by_source: dict[str, list[dict]] = {}
        for row in mapping:
            by_source.setdefault(row["source"], []).append(
                {"source_id": row["source_id"], "machine_id": row["machine_id"]}
            )

        def _ser(v):
            if isinstance(v, (datetime, date, time)):
                return v.isoformat()
            return v

        def _clean(rows: list[dict]) -> list[dict]:
            return [{k: _ser(v) for k, v in r.items()} for r in rows]

        return {
            "plant_id": "PLANT_01",
            "shifts": _clean(shifts),
            "lines": _clean(lines),
            "products": _clean(products),
            "machines": _clean(machines),
            "work_orders": _clean(work_orders),
            "production_plans": _clean(plans),
            "id_mapping": by_source,
        }


# ────────────────────────────────────────────────────────────── Cache
class Cache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] | None = None
        self._at = 0.0
        self._source = "json"

    def get(self) -> tuple[dict[str, Any], str]:
        import time as _t

        with self._lock:
            fresh = self._data is not None and (_t.time() - self._at) < CACHE_TTL_SEC
            if fresh:
                return self._data, self._source

            data: dict[str, Any] | None = None
            source = "json"
            if DB_URL:
                try:
                    data = pg_source.snapshot()
                    source = "postgres"
                except Exception as exc:  # noqa: BLE001 - PG khong chay -> fallback JSON
                    log.warning("PostgreSQL khong doc duoc (%s) — dung JSON fallback", exc)
                    try:
                        pg_source.close()
                    except Exception:  # noqa: BLE001
                        pass
                    data = None
            if data is None:
                data = _load_json()
                source = "json"

            self._data = data
            self._at = _t.time()
            self._source = source
            return data, source

    def invalidate(self) -> None:
        """Xoa cache -> lan doc sau lay du lieu moi tu PostgreSQL.

        Dung sau khi co thao tac ghi Work Order (tao/phat hanh/bat dau/...).
        """
        with self._lock:
            self._data = None
            self._at = 0.0


pg_source = PostgresSource(DB_URL) if DB_URL else None
cache = Cache()

app = FastAPI(title="Master Data API", version="1.0")

# ────────────────────────────────────────────────────────────── Work Order (MES)
# Nghiep vu vong doi WO (tao phieu -> phat hanh -> chay -> hoan thanh).
# Chi khi co PostgreSQL: ghi WO bat buoc can DB.
_wo_store = None
if DB_URL:
    try:
        from work_orders import WoStore, build_router  # noqa: PLC0415

        _wo_store = WoStore(DB_URL)
        app.include_router(build_router(_wo_store, on_change=cache.invalidate))
        log.info("da dang ky API vong doi Work Order (POST/PUT + action)")
    except Exception as exc:  # noqa: BLE001 - thiếu schema -> chi read API chạy
        log.warning("khong khoi dong duoc API Work Order: %s", exc)
        _wo_store = None


def _master() -> dict[str, Any]:
    data, _ = cache.get()
    return data


def _shift_now(shifts: list[dict], now: datetime | None = None) -> dict | None:
    """Ca dang chay theo gio hien tai."""
    now = now or datetime.now()
    cur = now.hour * 60 + now.minute
    for s in shifts:
        st = s.get("start_time")
        et = s.get("end_time")
        if not st or not et:
            continue
        sh, sm = (int(x) for x in str(st).split(":")[:2])
        eh, em = (int(x) for x in str(et).split(":")[:2])
        start = sh * 60 + sm
        end = eh * 60 + em
        if start < end:
            if start <= cur < end:
                return s
        elif cur >= start or cur < end:
            return s
    return None


def _line_view(line: dict, data: dict, shift: dict | None) -> dict:
    product = next((p for p in data["products"] if p["product_id"] == line.get("product_id")), None)
    shift_id = shift.get("shift_id") if shift else None
    wo = next(
        (w for w in data["work_orders"]
         if w.get("line_id") == line.get("line_id")
         and w.get("status") in ("IN_PROGRESS", "PAUSED", "RUNNING")
         and (shift_id is None or w.get("shift_id") in (None, shift_id))),
        None,
    )
    plan = None
    if shift:
        plan = next(
            (p for p in data["production_plans"]
             if p.get("line_id") == line.get("line_id") and p.get("shift_id") == shift.get("shift_id")),
            None,
        )
    if plan is None:
        # Không có kế hoạch riêng cho ca này → dùng kế hoạch đầu tiên của line.
        plan = next(
            (p for p in data["production_plans"] if p.get("line_id") == line.get("line_id")),
            None,
        )
    return {
        "line_id": line.get("line_id"),
        # ⚠ Tên field khác nhau giữa JSON (`display_name`) và PostgreSQL
        #   (`line_name`) → đọc cả hai để nguồn nào cũng ra cùng shape.
        "display_name": line.get("display_name") or line.get("line_name"),
        "channel": line.get("channel"),
        "reference_process": line.get("reference_process"),
        "sku": product.get("product_id") if product else None,
        "productName": product.get("product_name") if product else None,
        "idealCycleTimeSec": product.get("ideal_cycle_time_sec") if product else None,
        "plannedQty": (plan or {}).get("planned_qty"),
        "theoreticalQty": (plan or {}).get("theoretical_qty"),
        "unit": line.get("unit"),
        "workOrder": (
            {
                "woId": wo.get("wo_id"),
                "woCode": wo.get("wo_code"),
                "plannedQty": wo.get("planned_qty"),
                "status": wo.get("status"),
                "actualStartTime": wo.get("actual_start_time"),
            }
            if wo
            else None
        ),
    }


@app.get("/health")
def health():
    data, source = cache.get()
    return {
        "status": "ok",
        "source": source,
        "postgresConfigured": bool(DB_URL),
        "jsonPath": str(JSON_PATH),
        "machines": len(data.get("machines", [])),
        "lines": len(data.get("lines", [])),
        "products": len(data.get("products", [])),
        "workOrders": len(data.get("work_orders", [])),
    }


@app.get("/api/master")
def get_master():
    data, source = cache.get()
    return {"source": source, **data}


@app.get("/api/lines")
def get_lines():
    data, _ = cache.get()
    shift = _shift_now(data.get("shifts", []))
    return {
        "shift": (
            {
                "shiftId": shift.get("shift_id"),
                "shiftName": shift.get("shift_name"),
                "startTime": shift.get("start_time"),
                "endTime": shift.get("end_time"),
                "plannedMinutes": shift.get("planned_minutes"),
                "plannedBreakMinutes": shift.get("planned_break_minutes"),
            }
            if shift
            else None
        ),
        "lines": [_line_view(ln, data, shift) for ln in data.get("lines", [])],
    }


@app.get("/api/lines/{line_id}")
def get_line(line_id: str):
    data, _ = cache.get()
    line = next((l for l in data.get("lines", []) if l.get("line_id") == line_id), None)
    if line is None:
        raise HTTPException(404, f"khong co dong chay '{line_id}'")
    shift = _shift_now(data.get("shifts", []))
    view = _line_view(line, data, shift)
    view["machines"] = [
        m for m in data.get("machines", []) if m.get("line_id") == line_id
    ]
    return view


@app.get("/api/products")
def get_products():
    data, _ = cache.get()
    return {"products": data.get("products", [])}


@app.get("/api/work-orders")
def get_work_orders(lineId: str | None = Query(None), status: str | None = Query(None),
                    from_: datetime | None = Query(None, alias="from"),
                    to: datetime | None = Query(None)):
    """Danh sach lenh san xuat.

    Uu tien doc truc tiep PostgreSQL (co tien do san luong + cot moi).
    Neu khong co DB -> fallback ve cache master data.
    """
    if _wo_store is not None:
        sql = ("SELECT * FROM work_order_progress WHERE 1=1")
        args: list[Any] = []
        if lineId:
            sql += " AND line_id = %s"
            args.append(lineId)
        if status:
            sql += " AND status = %s"
            args.append(status.upper())
        if from_:
            sql += " AND (actual_start_time >= %s OR actual_start_time IS NULL)"
            args.append(from_)
        if to:
            sql += " AND (actual_start_time < %s OR actual_start_time IS NULL)"
            args.append(to)
        sql += " ORDER BY line_id, seq"
        return {"workOrders": _wo_store.all(sql, tuple(args))}

    data, _ = cache.get()
    items = data.get("work_orders", [])
    if lineId:
        items = [w for w in items if w.get("line_id") == lineId]
    if status:
        items = [w for w in items if (w.get("status") or "").upper() == status.upper()]
    return {"workOrders": items}


@app.get("/api/work-orders/current")
def get_current_work_order(lineId: str | None = Query(None)):
    """Lenh san xuat DANG CHAY cua tung chuyen (1 chuyen = 1 lenh chay)."""
    if _wo_store is not None:
        sql = ("SELECT * FROM work_order_progress WHERE status IN ('IN_PROGRESS','PAUSED')")
        args: list[Any] = []
        if lineId:
            sql += " AND line_id = %s"
            args.append(lineId)
        sql += " ORDER BY line_id"
        return {"workOrders": _wo_store.all(sql, tuple(args))}

    data, _ = cache.get()
    items = [w for w in data.get("work_orders", [])
             if w.get("status") in ("IN_PROGRESS", "PAUSED", "RUNNING")]
    if lineId:
        items = [w for w in items if w.get("line_id") == lineId]
    return {"workOrders": items}


@app.get("/api/shifts")
def get_shifts():
    data, _ = cache.get()
    return {"shifts": data.get("shifts", [])}


@app.get("/api/machines")
def get_machines(lineId: str | None = Query(None)):
    data, _ = cache.get()
    items = data.get("machines", [])
    if lineId:
        items = [m for m in items if m.get("line_id") == lineId]
    return {"count": len(items), "machines": items}
