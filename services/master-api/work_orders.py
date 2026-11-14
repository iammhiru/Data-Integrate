"""
Nghiep vu vong doi Work Order (MES) — theo chuan Vinamilk FillingWorkOrderStatus.

    DRAFT ──release──▶ RELEASED ──start──▶ IN_PROGRESS ⇄ PAUSED
                                                │
                                            complete
                                                ▼
                                           COMPLETED
    DRAFT/RELEASED ──cancel──▶ CANCELLED

Quyet dinh da chot (14/11/2026):
  · PlannedTime cua OEE theo WO = actual_start_time -> (actual_end_time ?? now)
  · San luong/Good/NG theo WO = BASELINE chuan Vinamilk:
        WO_VALUE = max(0, raw_counter_now - baseline_luc_bam_dau_WO)
    baseline luu trong bang `counter_baseline` (chiu duoc restart), co reset guard.
  · Service so huu nghiep vu ghi WO: master-api (nay).
  · NG tay (nhap thu cong): CHUA can -> Q chi tinh tu counter may.

Luong chay cua 1 lenh:
    POST /api/work-orders              -> tao phieu (DRAFT)
    POST /api/work-orders/{id}/release -> phat hanh (RELEASED)
    POST /api/work-orders/{id}/start   -> bat dau (IN_PROGRESS) + chup baseline counter
    POST /api/work-orders/{id}/pause   -> tam dung (PAUSED)
    POST /api/work-orders/{id}/resume  -> tiep tuc (IN_PROGRESS)
    POST /api/work-orders/{id}/complete-> hoan thanh (COMPLETED) + dong baseline
    POST /api/work-orders/{id}/cancel  -> huy (CANCELLED)
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("master-api.work_order")

router = APIRouter(prefix="/api/work-orders", tags=["work order (MES)"])

# ───────────────────────────────────────────────────────────── trạng thái & action
DRAFT = "DRAFT"
RELEASED = "RELEASED"
IN_PROGRESS = "IN_PROGRESS"
PAUSED = "PAUSED"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"

ALL_STATUS = (DRAFT, RELEASED, IN_PROGRESS, PAUSED, COMPLETED, CANCELLED)

#: Chuyen sang trang thai nao sau khi thuc hien action.
TRANSITIONS: dict[str, str] = {
    "RELEASE": RELEASED,
    "START": IN_PROGRESS,
    "PAUSE": PAUSED,
    "RESUME": IN_PROGRESS,
    "COMPLETE": COMPLETED,
    "CANCEL": CANCELLED,
}

#: Trang thai duoc phep thuc hien action tuong ung.
ALLOWED_FROM: dict[str, set[str]] = {
    "RELEASE": {DRAFT},
    "START": {RELEASED},
    "PAUSE": {IN_PROGRESS},
    "RESUME": {PAUSED},
    "COMPLETE": {IN_PROGRESS, PAUSED},
    # Cho phep huy ca lenh DANG CHAY: can thiet khi phai dung gap san xuat
    # va mo chuyen cho lenh moi (van cach duy nhat theo quy tac 1 chuyen = 1 lenh).
    "CANCEL": {DRAFT, RELEASED, IN_PROGRESS, PAUSED},
}

#: Cac counter can chup baseline khi bat dau WO.
#: (tag_code, ten tag trong raw) — khop voi COUNTERS trong spark/apps/batch_kpi.py
BASELINE_TAGS = ("TotalCounter", "GoodCounter", "DefectCounter")


# ───────────────────────────────────────────────────────────── model
class WorkOrderIn(BaseModel):
    """Du lieu tao/sua phieu lenh san xuat."""

    line_id: str = Field(..., description="Chuyen chay (VD: LINE_01)")
    product_id: str = Field(..., description="SKU (VD: PET-500-COKE)")
    planned_qty: int | None = Field(None, ge=0, description="SL ke hoach")
    shift_id: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    wo_code: str | None = Field(None, description="Ma WO (tu sinh neu de trong)")
    unit: str | None = None
    note: str | None = None
    operator_id: str | None = None


class ActionIn(BaseModel):
    """Tham so cho action vong doi (release/start/pause/...)."""

    operator_id: str | None = Field(None, description="Nguoi thuc hien")
    note: str | None = None


class ActionOut(BaseModel):
    wo: dict[str, Any]
    log_id: int | None = None


# ───────────────────────────────────────────────────────────── DB helpers
class WoStore:
    """Truy cap truc tiep PostgreSQL cho nghiep vu ghi WO.

    master-api hien doc master data qua `PostgresSource` (psycopg2, co cache).
    Phan ghi can ghi ngay va co transaction -> dung rieng connection psycopg3.
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._lock = threading.Lock()
        self._conn = None

    def _connect(self):
        if self._conn is not None:
            # ⚠ Kiểm tra connection còn sống TRƯỚC khi dùng.
            #   PostgreSQL đóng connection idle quá lâu (NAT/firewall/idle timeout)
            #   mà client không biết → query sau lỗi
            #   "server closed the connection unexpectedly" và treo tới timeout.
            #   `closed` là True khi server đã đóng → tự mở lại.
            if not self._conn.closed:
                return self._conn
            self._conn = None
        import psycopg  # noqa: PLC0415

        self._conn = psycopg.connect(self.dsn, autocommit=False, connect_timeout=5)
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None

    # ------------------------------------------------------------------ query
    def one(self, sql: str, args: tuple = ()) -> dict | None:
        import psycopg.rows  # noqa: PLC0415

        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                    cur.execute(sql, args)
                    row = cur.fetchone()
                conn.commit()
            except Exception:
                # Rollback + đóng connection: nếu không rollback, mọi query sau
                # sẽ fail với "current transaction is aborted".
                # ⚠ Nếu lỗi do connection chết (server đã đóng) thì phải BỎ
                #   hẳn connection cũ, không phải chỉ rollback — connection đó
                #   không tái sử dụng được nữa.
                try:
                    conn.rollback()
                    if conn.closed:
                        self._conn = None
                except Exception:  # noqa: BLE001
                    self.close()
                raise
        return dict(row) if row else None

    def all(self, sql: str, args: tuple = ()) -> list[dict]:
        import psycopg.rows  # noqa: PLC0415

        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                    cur.execute(sql, args)
                    rows = [dict(r) for r in cur.fetchall()]
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                    if conn.closed:
                        self._conn = None
                except Exception:  # noqa: BLE001
                    self.close()
                raise
        return rows

    def execute(self, sql: str, args: tuple = ()) -> int:
        """Chay 1 lenh, tra ve so dong bi anh huong. Commit neu thanh cong."""
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, args)
                    n = cur.rowcount
                conn.commit()
                return n
            except Exception:
                try:
                    conn.rollback()
                    if conn.closed:
                        self._conn = None
                except Exception:  # noqa: BLE001
                    self.close()
                raise


# ───────────────────────────────────────────────────────────── helper
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _next_seq(store: WoStore, line_id: str) -> int:
    row = store.one("SELECT COALESCE(max(seq), 0) + 1 AS n FROM work_order WHERE line_id = %s", (line_id,))
    return int(row["n"]) if row else 1


def _gen_wo_code(store: WoStore, line_id: str) -> str:
    """Sinh ma WO dang WO-YYMMDD-NNNN theo ma chuyen."""
    # NOTE: psycopg3 dung %s lam placeholder -> '%' trong SQL phai truyen qua tham so.
    row = store.one(
        "SELECT count(*) AS n FROM work_order WHERE wo_code LIKE %s",
        (f"WO-{_utcnow():%y%m%d}-%",),
    )
    seq = int(row["n"]) + 1 if row else 1
    return f"WO-{_utcnow():%y%m%d}-{seq:04d}"


def _gen_wo_id(store: WoStore, line_id: str, wo_code: str) -> str:
    """Khoa chinh: line + ma WO -> duy nhat va tra loi duoc ve sau."""
    base = f"{line_id}-{wo_code}"
    if store.one("SELECT 1 AS x FROM work_order WHERE wo_id = %s", (base,)):
        return base
    return f"{base}-{_utcnow():%H%M%S%f}"


def _get_wo(store: WoStore, wo_id: str) -> dict:
    row = store.one("SELECT * FROM work_order WHERE wo_id = %s", (wo_id,))
    if not row:
        raise HTTPException(404, f"khong tim thay work order {wo_id}")
    return row


def _log(store: WoStore, wo_id: str, action: str, old: str | None, new: str | None,
         operator: str | None, note: str | None, message: str | None = None) -> int | None:
    row = store.one(
        "INSERT INTO work_order_log "
        "  (wo_id, action, old_status, new_status, action_by, category, message, note) "
        "VALUES (%s, %s, %s, %s, %s, 'VAN_HANH', %s, %s) RETURNING log_id",
        (wo_id, action, old, new, operator, message, note),
    )
    return row["log_id"] if row else None


# ───────────────────────────────────────────────────────────── baseline counter
#: Map cot trong `machine_kpi_1m` -> tag counter tuong ung.
BASELINE_SOURCES = (
    ("TotalCounter", "total_end"),
    ("GoodCounter", "good_end"),
    ("DefectCounter", "defect_end"),
)


def _capture_baseline(store: WoStore, wo: dict, operator: str | None) -> dict[str, int]:
    """Chup gia tri bo dem hien tai lam moc cho WO (chuan Vinamilk).

    Baseline = gia tri counter tai thoi diem WO bat dau. Sau do:
        WO_VALUE = max(0, raw_now - baseline)
    Neu may reset bo dem (raw < baseline) -> ha baseline xuong raw (reset guard).

    Nguon gia tri counter: `machine_kpi_1m` — cot snapshot cuoi phut
    (`total_end` / `good_end` / `defect_end`) la bo dem TICH LUY cua may.
    Lay dong moi nhat <= thoi diem bat dau WO cho tung may thuoc chuyen.

    Fallback: neu may chua co fact (moi bat dau chay), dung `tag_metric_1m`
    (cot `last` = gia tri cuoi phut cua tag).
    """
    line_id = wo["line_id"]
    captured: dict[str, int] = {}

    # --- 1) uu tien snapshot counter tu machine_kpi_1m
    rows = store.all(
        "SELECT DISTINCT ON (k.machine_id) k.machine_id, k.total_end, k.good_end, k.defect_end "
        "FROM machine_kpi_1m k JOIN machine m ON m.machine_id = k.machine_id "
        "WHERE m.line = %s AND k.ts_minute <= %s "
        "ORDER BY k.machine_id, k.ts_minute DESC",
        (line_id, wo.get("actual_start_time") or _utcnow()),
    )
    latest: dict[tuple[str, str], float] = {}
    for r in rows:
        for tag, col in BASELINE_SOURCES:
            v = r.get(col)
            if v is not None:
                latest[(r["machine_id"], tag)] = float(v)

    # --- 2) fallback: tag_metric_1m cho may chua co fact
    if not latest:
        trows = store.all(
            "SELECT k.machine_id, k.tag_name, k.last "
            "FROM tag_metric_1m k JOIN machine m ON m.machine_id = k.machine_id "
            "WHERE m.line = %s AND k.tag_name = ANY(%s) "
            "  AND k.ts_minute = (SELECT max(ts_minute) FROM tag_metric_1m)",
            (line_id, list(BASELINE_TAGS)),
        )
        for r in trows:
            if r["last"] is not None:
                latest[(r["machine_id"], r["tag_name"])] = float(r["last"])

    for (machine_id, tag_name), value in latest.items():
        store.execute(
            "INSERT INTO counter_baseline "
            "  (node_id, machine_id, tag_code, work_order_id, baseline_value, last_raw_value, recorded_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (machine_id, tag_code, work_order_id) DO UPDATE SET "
            "  baseline_value = EXCLUDED.baseline_value, "
            "  last_raw_value = EXCLUDED.last_raw_value, recorded_at = now()",
            (f"{line_id}.{machine_id}.{tag_name}", machine_id, tag_name, wo["wo_id"], value, value),
        )
        captured[f"{machine_id}.{tag_name}"] = int(value)
    log.info("[WO] chup baseline cho %s: %d counter", wo["wo_id"], len(captured))
    return captured


def _close_baseline(store: WoStore, wo_id: str) -> None:
    """Dong baseline khi WO ket thuc (gia tri cuoi duoc luu lai de tra cuoc)."""
    store.execute(
        "UPDATE counter_baseline SET recorded_at = now() WHERE work_order_id = %s", (wo_id,)
    )


# ───────────────────────────────────────────────────────────── endpoints
def build_router(store: WoStore, on_change=None) -> APIRouter:
    """Tao router. `on_change` duoc goi sau moi thay doi de xoa cache master."""

    def _touch() -> None:
        if on_change is not None:
            try:
                on_change()
            except Exception as exc:  # noqa: BLE001 - xoa cache khong duoc lam fail request
                log.warning("khong xoa duoc cache master: %s", exc)

    # ---------------------------------------------------------------- tao phieu
    @router.post("", status_code=201, summary="Tao phieu lenh san xuat (DRAFT)")
    def create_wo(body: WorkOrderIn) -> dict[str, Any]:
        if store.one("SELECT 1 AS x FROM line WHERE line_id = %s", (body.line_id,)) is None:
            raise HTTPException(400, f"khong ton tai chuyen {body.line_id}")
        if store.one("SELECT 1 AS x FROM product WHERE product_id = %s", (body.product_id,)) is None:
            raise HTTPException(400, f"khong ton tai SKU {body.product_id}")

        wo_code = body.wo_code or _gen_wo_code(store, body.line_id)
        wo_id = _gen_wo_id(store, body.line_id, wo_code)
        seq = _next_seq(store, body.line_id)

        row = store.one(
            "INSERT INTO work_order "
            "  (wo_id, wo_code, line_id, product_id, shift_id, planned_qty, status, "
            "   planned_start, planned_end, unit, note, operator_id, seq) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (wo_id, wo_code, body.line_id, body.product_id, body.shift_id, body.planned_qty,
             DRAFT, body.planned_start, body.planned_end, body.unit, body.note,
             body.operator_id, seq),
        )
        _log(store, wo_id, "CREATE", None, DRAFT, body.operator_id, body.note,
             f"Tao phieu {wo_code} cho {body.line_id}")
        _touch()
        return {"workOrder": row}

    # ---------------------------------------------------------------- sua phieu
    @router.put("/{wo_id}", summary="Sua phieu lenh (chi khi DRAFT/RELEASED)")
    def update_wo(wo_id: str, body: WorkOrderIn) -> dict[str, Any]:
        wo = _get_wo(store, wo_id)
        if wo["status"] not in (DRAFT, RELEASED):
            raise HTTPException(400, f"khong sua duoc lenh dang {wo['status']}")
        row = store.one(
            "UPDATE work_order SET product_id = %s, shift_id = %s, planned_qty = %s, "
            "  planned_start = %s, planned_end = %s, unit = %s, note = %s, operator_id = %s "
            "WHERE wo_id = %s RETURNING *",
            (body.product_id, body.shift_id, body.planned_qty, body.planned_start,
             body.planned_end, body.unit, body.note, body.operator_id, wo_id),
        )
        _log(store, wo_id, "UPDATE", wo["status"], wo["status"], body.operator_id, body.note,
             "Sua phieu lenh")
        _touch()
        return {"workOrder": row}

    # ---------------------------------------------------------------- action
    def _transition(wo_id: str, action: str, body: ActionIn) -> dict[str, Any]:
        wo = _get_wo(store, wo_id)
        old = wo["status"]
        new = TRANSITIONS[action]
        allowed = ALLOWED_FROM[action]
        if old not in allowed:
            raise HTTPException(
                400,
                f"khong the {action} khi lenh dang {old} (cho phep: {', '.join(sorted(allowed))})",
            )

        # 1 chuyen chi chay 1 lenh -> khoi dong lenh dang chay truoc
        if action == "START":
            running = store.one(
                "SELECT wo_id, wo_code FROM work_order "
                "WHERE line_id = %s AND status IN ('IN_PROGRESS','PAUSED') AND wo_id <> %s",
                (wo["line_id"], wo_id),
            )
            if running:
                raise HTTPException(
                    409,
                    f"chuyen {wo['line_id']} dang chay lenh {running['wo_code']} "
                    f"({running['wo_id']}) — phai hoan thanh/huy truoc khi bat dau lenh moi",
                )

        sets: list[str] = ["status = %s"]
        args: list[Any] = [new]

        if action == "RELEASE":
            sets += ["released_at = now()", "released_by = %s"]
            args.append(body.operator_id)
        elif action == "START":
            sets += ["actual_start_time = now()", "actual_end_time = NULL", "paused_at = NULL"]
        elif action == "PAUSE":
            sets += ["paused_at = now()"]
        elif action == "RESUME":
            # Thoi gian tam dung khong tinh vao planned time cua lenh
            sets += ["paused_at = NULL"]
        elif action == "COMPLETE":
            sets += ["actual_end_time = now()"]
        elif action == "CANCEL":
            sets += ["actual_end_time = now()"]

        args.append(wo_id)
        row = store.one(
            f"UPDATE work_order SET {', '.join(sets)} WHERE wo_id = %s RETURNING *",
            tuple(args),
        )

        # Baseline: chup khi bat dau, dong khi ket thuc
        baseline = None
        if action == "START":
            baseline = _capture_baseline(store, wo, body.operator_id)
        elif action in ("COMPLETE", "CANCEL"):
            _close_baseline(store, wo_id)

        log_id = _log(store, wo_id, action, old, new, body.operator_id, body.note,
                     f"{action}: {old} -> {new}")
        _touch()
        return {"workOrder": row, "logId": log_id, "baseline": baseline}

    @router.post("/{wo_id}/release", summary="Phat hanh lenh (DRAFT -> RELEASED)")
    def release(wo_id: str, body: ActionIn = ActionIn()) -> dict[str, Any]:
        return _transition(wo_id, "RELEASE", body)

    @router.post("/{wo_id}/start", summary="Bat dau lenh (RELEASED -> IN_PROGRESS) + chup baseline")
    def start(wo_id: str, body: ActionIn = ActionIn()) -> dict[str, Any]:
        return _transition(wo_id, "START", body)

    @router.post("/{wo_id}/pause", summary="Tam dung lenh (IN_PROGRESS -> PAUSED)")
    def pause(wo_id: str, body: ActionIn = ActionIn()) -> dict[str, Any]:
        return _transition(wo_id, "PAUSE", body)

    @router.post("/{wo_id}/resume", summary="Tiep tuc lenh (PAUSED -> IN_PROGRESS)")
    def resume(wo_id: str, body: ActionIn = ActionIn()) -> dict[str, Any]:
        return _transition(wo_id, "RESUME", body)

    @router.post("/{wo_id}/complete", summary="Hoan thanh lenh (IN_PROGRESS -> COMPLETED)")
    def complete(wo_id: str, body: ActionIn = ActionIn()) -> dict[str, Any]:
        return _transition(wo_id, "COMPLETE", body)

    @router.post("/{wo_id}/cancel", summary="Huy lenh (DRAFT/RELEASED -> CANCELLED)")
    def cancel(wo_id: str, body: ActionIn = ActionIn()) -> dict[str, Any]:
        return _transition(wo_id, "CANCEL", body)

    # ---------------------------------------------------------------- doc
    @router.get("/{wo_id}/log", summary="Nhat ky hanh dong cua lenh")
    def wo_log(wo_id: str) -> dict[str, Any]:
        _get_wo(store, wo_id)
        rows = store.all(
            "SELECT log_id, action, old_status, new_status, action_at, action_by, message, note "
            "FROM work_order_log WHERE wo_id = %s ORDER BY log_id",
            (wo_id,),
        )
        return {"logs": rows}

    @router.get("/{wo_id}/baseline", summary="Baseline bo dem cua lenh")
    def wo_baseline(wo_id: str) -> dict[str, Any]:
        _get_wo(store, wo_id)
        rows = store.all(
            "SELECT machine_id, tag_code, baseline_value, last_raw_value, recorded_at "
            "FROM counter_baseline WHERE work_order_id = %s ORDER BY machine_id, tag_code",
            (wo_id,),
        )
        return {"baselines": rows}

    return router
