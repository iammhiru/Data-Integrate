"""
Analytics API (batch layer) - doc PostgreSQL (bang do spark/apps/batch_kpi.py ghi), tinh metric cho UI.

Nguyen tac: bang chi luu so CONG DUOC (giay, dem, delta) -> API SUM theo cua so bat ky roi MOI chia:
    planned  = (span - off - maint - nodata) * (planned_minutes - break) / planned_minutes   (theo ca)
    A = run / planned      P = ideal_time / run      Q = good / total      OEE = A * P * Q
Cua so: ?last=3h | ?preset=today|yesterday|current_shift|previous_shift | ?from=..&to=.. (ISO 8601).
Nhom:   ?groupBy=machine|line|plant|product|shift   (+ ?bucket=5m|15m|1h|1d|shift de lay trend).
OEE line/plant mac dinh chi tinh tren MAY THAM CHIEU (may chiet - REF_MACHINE_PATTERN), vi OEE line
khong phai tong cac may. ?referenceOnly=false de cong tat ca may.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

PG_DSN = os.getenv("PG_DSN", "")
TZ = ZoneInfo(os.getenv("PLANT_TZ", "Asia/Ho_Chi_Minh"))
REF_PATTERN = os.getenv("REF_MACHINE_PATTERN", "%FILLER%")   # may tham chieu OEE line (cong doan chiet)

#: Cac `machine_type` duoc coi la "may tham chieu" khi tinh OEE theo Work Order.
#: Line 01/02/03 deu chay cong doan CHIET (FILLING) — may nay ra san pham chinh,
#: nen bo dem cua no moi la "san luong cua lenh" va OEE phai do tren may nay.
REF_MACHINE_TYPES = [
    "CARBONATED_FILLER", "STILL_FILLER", "CAN_FILLER",
]
MAX_WINDOW_DAYS = 31
MINUTE_TABLE_MAX_DAYS = 2   # cua so dai hon -> doc bang 1h

router = APIRouter(prefix="/api/analytics", tags=["analytics (batch)"])
_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if not PG_DSN:
        raise HTTPException(503, "chua cau hinh PG_DSN cho analytics")
    if _pool is None:
        # ⚠ `check=ConnectionPool.check_connection` — BẮT BUỘC.
        #   PostgreSQL (đặc biệt qua NAT/firewall) có thể đóng connection đã
        #   idle quá lâu mà client không biết. Không có `check`, pool giữ lại
        #   connection chết → request treo cho tới timeout, hoặc lỗi
        #   "server closed the connection unexpectedly" làm sập API.
        #   `check` ping trước khi cấp connection → tự động loại connection
        #   chết và mở cái mới. `reconnect_timeout` cho phép thử lại.
        _pool = ConnectionPool(
            PG_DSN,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
            check=ConnectionPool.check_connection,
            reconnect_timeout=10,
        )
    return _pool


def q(sql: str, params: dict | None = None) -> list[dict]:
    with pool().connection() as c:
        return c.execute(sql, params or {}).fetchall()


# =============================================================== cua so thoi gian
_LAST = re.compile(r"^(\d+)([mhd])$")


def _shifts() -> list[dict]:
    return q("SELECT shift_id, shift_name, start_time, end_time, planned_minutes, planned_break_minutes "
             "FROM shift ORDER BY start_time")


def _shift_window(which: str, now_local: datetime) -> tuple[datetime, datetime, str]:
    spans = []
    for s in _shifts():
        for day_off in (-2, -1, 0):
            d = now_local.date() + timedelta(days=day_off)
            st = datetime.combine(d, s["start_time"], tzinfo=TZ)
            en = datetime.combine(d, s["end_time"], tzinfo=TZ)
            if en <= st:
                en += timedelta(days=1)
            spans.append((st, en, s["shift_id"]))
    spans.sort()
    cur = next(i for i, (st, en, _) in enumerate(spans) if st <= now_local < en)
    st, en, sid = spans[cur if which == "current_shift" else cur - 1]
    return st, en, sid


def resolve_window(last: str | None, preset: str | None, from_: datetime | None, to: datetime | None) -> dict:
    now = datetime.now(timezone.utc)
    label = None
    if from_ or to:
        start = from_ or (to - timedelta(hours=1))
        end = to or now
    elif preset:
        nl = now.astimezone(TZ)
        if preset == "today":
            start, end = datetime.combine(nl.date(), time(0), tzinfo=TZ), now
        elif preset == "yesterday":
            end = datetime.combine(nl.date(), time(0), tzinfo=TZ)
            start = end - timedelta(days=1)
        elif preset in ("current_shift", "previous_shift"):
            start, end, label = _shift_window(preset, nl)
            end = min(end, now)
        else:
            raise HTTPException(400, "preset: today | yesterday | current_shift | previous_shift")
    else:
        m = _LAST.match(last or "1h")
        if not m:
            raise HTTPException(400, "last dang <so><m|h|d>, vd 15m, 3h, 7d")
        n, unit = int(m.group(1)), m.group(2)
        start = now - {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
        end = now
    for v in (start, end):
        if v.tzinfo is None:
            raise HTTPException(400, "from/to phai co mui gio, vd 2026-11-14T08:00:00+07:00")
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if end <= start:
        raise HTTPException(400, "to phai lon hon from")
    if end - start > timedelta(days=MAX_WINDOW_DAYS):
        raise HTTPException(400, f"cua so toi da {MAX_WINDOW_DAYS} ngay")
    fresh = q("SELECT data_until FROM batch_freshness")[0]["data_until"]
    return {"from": start, "to": end, "shiftId": label, "tz": str(TZ), "dataUntil": fresh,
            "partial": fresh is None or end > fresh}


def _window_doc(w: dict) -> dict:
    return {"from": w["from"], "to": w["to"], "tz": w["tz"], "shiftId": w["shiftId"],
            "dataUntil": w["dataUntil"], "partial": w["partial"]}


# =============================================================== nhom / bucket
GROUP_COLS = {
    "machine": ["k.machine_id", "k.line_id"],
    "line": ["k.line_id"],
    "plant": [],
    "product": ["k.product_id"],
    "shift": ["k.shift_date", "k.shift_id"],
}
GroupBy = Literal["machine", "line", "plant", "product", "shift"]
Bucket = Literal["1m", "5m", "15m", "30m", "1h", "1d", "shift"]


def bucket_expr(bucket: str | None, ts: str) -> list[str]:
    if not bucket:
        return []
    if bucket in ("1m", "5m", "15m", "30m"):
        return [f"date_bin(interval '{bucket[:-1]} minutes', {ts}, timestamptz '2000-01-01') AS bucket"]
    if bucket == "1h":
        return [f"date_trunc('hour', {ts}) AS bucket"]
    if bucket == "1d":
        return [f"(date_trunc('day', {ts} AT TIME ZONE '{TZ}') AT TIME ZONE '{TZ}') AS bucket"]
    if bucket == "shift":
        return ["k.shift_date AS bucket_shift_date", "k.shift_id AS bucket_shift_id"]
    raise HTTPException(400, "bucket khong hop le")


def _csv(v: str | None) -> list[str] | None:
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


def _ratio(a, b):
    return round(a / b, 4) if a is not None and b else None


def _ratio_c(a, b):
    """Tỉ lệ CÓ CHẶN trên [0, 1] — dùng cho A/P/Q.

    ⚠ VÌ SAO CẦN:
        A/P/Q là tỉ lệ, giá trị > 1 là VÔ NGHĨA và phải do lỗi dữ liệu
        (counter lệch, thiết kế tốc độ sai) chứ không phải thực tế.
        Để lộ ra sẽ làm người dùng mất niềm tin vào con số.

        Quan sát thực tế trong PG (14/11/2026):
          · 1921/1962 phút có defect_count == total_count (counter NG của
            simulator bị lặp theo TotalCounter) → good phải tính lại.
          · Có 25 phút good_count > total_count.
          · P = 2.14 do ideal_time_sec (thiết kế tốc độ) vượt run_sec.
        → Ta CHẶN tại 1.0 và gắn cờ `clamped` để UI hiển thị cảnh báo
        chất lượng dữ liệu, thay vì hiện con số > 100%.
    """
    r = _ratio(a, b)
    if r is None:
        return None
    return min(max(r, 0.0), 1.0)


# =============================================================== KPI may (OEE / san luong)
def kpi_rows(w: dict, group_by: str, bucket: str | None, machine_ids, line_ids, reference_only: bool,
             wo_id: str | None = None) -> list[dict]:
    span_days = (w["to"] - w["from"]).total_seconds() / 86400
    hourly = span_days > MINUTE_TABLE_MAX_DAYS or bucket in ("1d",) and span_days > 1
    if hourly:
        table, ts, span = "machine_kpi_1h", "k.ts_hour", "k.minutes * 60"
        frm = w["from"].replace(minute=0, second=0, microsecond=0)
        to = w["to"]
    else:
        table, ts, span = "machine_kpi_1m", "k.ts_minute", "60"
        frm, to = w["from"], w["to"]
    if bucket in ("1m", "5m", "15m", "30m") and hourly:
        raise HTTPException(400, f"bucket {bucket} chi dung cho cua so <= {MINUTE_TABLE_MAX_DAYS} ngay")

    dims = GROUP_COLS[group_by] + [e for e in bucket_expr(bucket, ts)]
    dim_select = ", ".join(dims) + ", " if dims else ""
    group_keys = [d.split(" AS ")[-1] if " AS " in d else d for d in dims]
    where = [f"{ts} >= %(frm)s", f"{ts} < %(to)s"]
    params: dict[str, Any] = {"frm": frm, "to": to}
    if machine_ids:
        where.append("k.machine_id = ANY(%(mids)s)"); params["mids"] = machine_ids
    if line_ids:
        where.append("k.line_id = ANY(%(lids)s)"); params["lids"] = line_ids
    if reference_only:
        where.append("k.machine_id LIKE %(ref)s"); params["ref"] = REF_PATTERN

    # ---- OEE theo Work Order: dung "actual window" chuan Vinamilk
    # PlannedTime = actual_start_time -> (actual_end_time ?? now) cua lenh,
    # KHONG dung cong thuc theo ca. Chi ap dung khi truy van theo WO.
    wo_planned = None
    wo_meta = None
    if wo_id:
        wrow = q("SELECT w.wo_id, w.wo_code, w.line_id, w.product_id, w.status, "
                 "w.planned_qty, w.actual_start_time, w.actual_end_time, "
                 "EXTRACT(EPOCH FROM (COALESCE(w.actual_end_time, now()) - w.actual_start_time)) AS planned_sec "
                 "FROM work_order w WHERE w.wo_id = %(wo)s", {"wo": wo_id})
        if not wrow:
            raise HTTPException(404, f"khong tim thay work order {wo_id}")
        wo_meta = wrow[0]
        # CHI lay may thuoc chuyen cua lenh (1 chuyen = 1 lenh)
        where.append("k.wo_id = %(wo)s"); params["wo"] = wo_id
        where.append("k.line_id = %(wo_line)s"); params["wo_line"] = wo_meta["line_id"]
        # planned_sec cua lenh = thoi gian chay thuc te
        wo_planned = float(wo_meta.get("planned_sec") or 0)
        # Cua so du lieu = dung khoang chay cua lenh (khong phai cua so tuy bien)
        frm = wo_meta["actual_start_time"]
        to = wo_meta["actual_end_time"] or datetime.now(timezone.utc)
        params["frm"] = frm
        params["to"] = to

    planned_expr = (
        f"least(sum({span})::float8, %(wo_planned)s)" if wo_planned is not None
        else (f"sum(({span} - k.off_sec - k.maint_sec - k.nodata_sec)"
              f" * coalesce((s.planned_minutes - s.planned_break_minutes)::float8"
              f" / nullif(s.planned_minutes, 0), 1))::float8")
    )
    if wo_planned is not None:
        params["wo_planned"] = wo_planned

    sql = f"""
        SELECT {dim_select}
          count(DISTINCT k.machine_id)::int                          AS machines,
          sum({span})::float8                                        AS span_sec,
          sum(k.run_sec)::float8 AS run_sec, sum(k.starting_sec)::float8 AS starting_sec,
          sum(k.stopped_sec)::float8 AS stopped_sec, sum(k.faulted_sec)::float8 AS faulted_sec,
          sum(k.maint_sec)::float8 AS maint_sec, sum(k.off_sec)::float8 AS off_sec,
          sum(k.nodata_sec)::float8 AS nodata_sec,
          {planned_expr}                                             AS planned_sec,
          sum(k.stop_events)::bigint AS stop_events,
          sum(k.total_count)::bigint AS total_count, sum(k.good_count)::bigint AS good_count,
          sum(k.defect_count)::bigint AS defect_count, sum(k.ideal_time_sec)::float8 AS ideal_time_sec
        FROM {table} k LEFT JOIN shift s ON s.shift_id = k.shift_id
        WHERE {' AND '.join(where)}
        {('GROUP BY ' + ', '.join(group_keys)) if group_keys else ''}
        {('ORDER BY ' + ', '.join(group_keys)) if group_keys else ''}"""
    rows = q(sql, params)
    out = []
    for r in rows:
        if not r["span_sec"]:
            continue
        a = _ratio(r["run_sec"], r["planned_sec"])
        p = _ratio(r["ideal_time_sec"], r["run_sec"]) if r["ideal_time_sec"] else None
        qq = _ratio(r["good_count"], r["total_count"])
        item = {k: v for k, v in r.items() if k in ("machine_id", "line_id", "product_id", "shift_date",
                                                     "shift_id", "bucket")}
        if "bucket_shift_id" in r:
            item["bucket"] = f"{r['bucket_shift_date']}:{r['bucket_shift_id']}"
        run_h = r["run_sec"] / 3600 if r["run_sec"] else 0
        item.update({
            "machines": r["machines"],
            "oee": round(a * p * qq, 4) if None not in (a, p, qq) else None,
            "availability": a, "performance": p, "quality": qq,
            "time": {k: round(r[k], 1) for k in ("span_sec", "planned_sec", "run_sec", "starting_sec",
                                                 "stopped_sec", "faulted_sec", "maint_sec", "off_sec",
                                                 "nodata_sec", "ideal_time_sec")},
            "counts": {"total": r["total_count"], "good": r["good_count"], "defect": r["defect_count"],
                       "reject": max(r["total_count"] - r["good_count"], 0)},
            "rejectRate": _ratio(max(r["total_count"] - r["good_count"], 0), r["total_count"]),
            "productionRatePerRunHour": round(r["total_count"] / run_h, 1) if run_h else None,
            "stopEvents": r["stop_events"],
            "mtbfSec": round(r["run_sec"] / r["stop_events"], 1) if r["stop_events"] else None,
            "dataCoverage": _ratio(r["span_sec"] - r["nodata_sec"], r["span_sec"]),
        })
        out.append(item)
    return out


@router.get("/oee", summary="OEE = A x P x Q theo may / line / plant / san pham / ca / work order, co trend")
def oee(groupBy: GroupBy = "machine", bucket: Bucket | None = None,
        last: str | None = Query(None, description="vd 15m, 3h, 7d (mac dinh 1h)"),
        preset: Literal["today", "yesterday", "current_shift", "previous_shift"] | None = None,
        from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
        machineId: str | None = Query(None, description="danh sach, cach nhau dau phay"),
        lineId: str | None = Query(None, description="danh sach, cach nhau dau phay"),
        woId: str | None = Query(None, description="tinh OEE cho 1 work order (planned = actual window)"),
        referenceOnly: bool | None = Query(None, description="mac dinh: true khi groupBy=line|plant")):
    w = resolve_window(last, preset, from_, to)
    ref = referenceOnly if referenceOnly is not None else groupBy in ("line", "plant")
    if woId:
        # Truy van theo WO -> dung chinh xac khoang chay cua lenh, khong dung preset
        ref = False
    items = kpi_rows(w, groupBy, bucket, _csv(machineId), _csv(lineId), ref, woId)
    out = {"window": _window_doc(w), "groupBy": groupBy, "bucket": bucket, "referenceOnly": ref,
           "formula": "A=run/planned, P=ideal/run, Q=good/total, OEE=A*P*Q", "items": items}
    if woId:
        wo = q("SELECT wo_id, wo_code, line_id, product_id, status, planned_qty, "
               "actual_start_time, actual_end_time FROM work_order WHERE wo_id = %(wo)s", {"wo": woId})
        out["workOrder"] = wo[0] if wo else None
        out["plannedTimeRule"] = "actual_start_time -> (actual_end_time ?? now) (chuẩn Vinamilk)"
    return out


@router.get("/production", summary="San luong / dat / loi / toc do theo may / line / san pham / ca / work order")
def production(groupBy: GroupBy = "line", bucket: Bucket | None = None, last: str | None = None,
               preset: Literal["today", "yesterday", "current_shift", "previous_shift"] | None = None,
               from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
               machineId: str | None = None, lineId: str | None = None,
               woId: str | None = Query(None, description="san luong cua 1 work order"),
               referenceOnly: bool | None = Query(None, description="mac dinh: true khi groupBy=line|plant")):
    w = resolve_window(last, preset, from_, to)
    ref = referenceOnly if referenceOnly is not None else groupBy in ("line", "plant")
    if woId:
        ref = False
    keep = ("machine_id", "line_id", "product_id", "shift_date", "shift_id", "bucket", "machines", "counts",
            "rejectRate", "productionRatePerRunHour", "quality")
    items = [{k: v for k, v in it.items() if k in keep}
             for it in kpi_rows(w, groupBy, bucket, _csv(machineId), _csv(lineId), ref, woId)]
    out = {"window": _window_doc(w), "groupBy": groupBy, "bucket": bucket, "referenceOnly": ref, "items": items}
    if woId:
        wo = q("SELECT wo_id, wo_code, line_id, product_id, status, planned_qty, "
               "actual_start_time, actual_end_time FROM work_order WHERE wo_id = %(wo)s", {"wo": woId})
        out["workOrder"] = wo[0] if wo else None
    return out


@router.get("/wo/{wo_id}", summary="OEE + san luong cua 1 work order (planned = actual window)")
def work_order_kpi(wo_id: str, groupBy: Literal["machine", "line"] = "machine"):
    """Bao cao OEE cua mot lenh san xuat.

    PlannedTime = actual_start_time -> (actual_end_time ?? now)  (chuẩn Vinamilk).
    A = run_sec / planned_sec, P = ideal_time_sec / run_sec, Q = good / total.
    """
    wo = q("SELECT w.wo_id, w.wo_code, w.line_id, w.product_id, w.status, w.planned_qty, w.unit, "
           "w.actual_start_time, w.actual_end_time, p.product_name, "
           "EXTRACT(EPOCH FROM (COALESCE(w.actual_end_time, now()) - w.actual_start_time)) AS elapsed_sec "
           "FROM work_order w LEFT JOIN product p ON p.product_id = w.product_id "
           "WHERE w.wo_id = %(wo)s", {"wo": wo_id})
    if not wo:
        raise HTTPException(404, f"khong tim thay work order {wo_id}")
    meta = wo[0]
    if not meta["actual_start_time"]:
        # Van tra du cung khop cau truc nhu khi da bat dau de frontend khong
        # phai null-check tung field (tranh crash React khi render).
        return {"workOrder": meta, "started": False, "items": [],
                "oee": None, "availability": None, "performance": None, "quality": None,
                "plannedSec": None, "progressRatio": None,
                "counts": {"total": 0, "good": 0, "defect": 0, "reject": 0},
                "time": {"runSec": 0.0, "stoppedSec": 0.0, "faultedSec": 0.0, "maintSec": 0.0},
                "plannedTimeRule": "actual_start_time -> (actual_end_time ?? now) (chuan Vinamilk)",
                "message": "lenh chua bat dau -> chua co OEE"}

    w = {"from": meta["actual_start_time"], "to": meta["actual_end_time"] or datetime.now(timezone.utc)}
    items = kpi_rows(w, groupBy, None, None, None, False, wo_id)

    # ⚠ TOT HOP THEO MÁY THAM CHIẾU (công đoạn CHIẾT của chuyền).
    #
    # VÌ SAO:
    #   OEE là chỉ số của 1 MÁY, không phải của cả chuyền. Nếu cộng
    #   run_sec của cả 9 máy rồi chia planned_sec của 1 máy → Availability
    #   = 9 x (run/planned) > 1 (quan sát: 4.515). Sai hoàn toàn.
    #
    #   Cách tính đúng (chuẩn Vinamilk):
    #     A = run_sec(MÁY THAM CHIẾU) / planned_sec(của lệnh)
    #     P = ideal_time_sec(MÁY THAM CHIẾU) / run_sec(MÁY THAM CHIẾU)
    #     Q = good_count(MÁY THAM CHIẾU) / total_count(MÁY THAM CHIẾU)
    #
    #   MÁY THAM CHIẾU = công đoạn `reference_process` trong bảng `line`
    #   (LINE_01/02/03 đều là FILLING → máy chiết).
    ref_row = q("SELECT m.machine_id FROM machine m JOIN line l ON l.line_id = m.line "
                "WHERE m.line = %(line)s AND m.machine_type = ANY(%(types)s) "
                "ORDER BY CASE WHEN m.machine_id LIKE %(ref)s THEN 0 ELSE 1 END, m.machine_id LIMIT 1",
                {"line": meta["line_id"], "types": REF_MACHINE_TYPES, "ref": REF_PATTERN})
    ref_machine = ref_row[0]["machine_id"] if ref_row else None

    totals = q("SELECT sum(total_count)::bigint AS total, sum(good_count)::bigint AS good, "
               "sum(defect_count)::bigint AS defect, sum(run_sec)::float8 AS run_sec, "
               "sum(stopped_sec)::float8 AS stopped_sec, sum(faulted_sec)::float8 AS faulted_sec, "
               "sum(maint_sec)::float8 AS maint_sec, sum(ideal_time_sec)::float8 AS ideal_sec "
               "FROM machine_kpi_1m WHERE wo_id = %(wo)s AND machine_id = %(ref)s",
               {"wo": wo_id, "ref": ref_machine})
    t = totals[0] if totals else {}
    planned_sec = float(meta.get("elapsed_sec") or 0)
    run = float(t.get("run_sec") or 0)
    total = int(t.get("total") or 0)
    good = int(t.get("good") or 0)
    # ⚠ good > total là dữ liệu lỗi (counter lệch) → chặn, không hiện Q > 100%.
    good = min(good, total) if total > 0 else good
    a = _ratio_c(run, planned_sec)
    p = _ratio_c(float(t.get("ideal_sec") or 0), run) if run else None
    qq = _ratio_c(good, total)
    return {
        "workOrder": meta,
        "started": True,
        "items": items,
        "referenceMachine": ref_machine,
        "oee": round(a * p * qq, 4) if None not in (a, p, qq) else None,
        "availability": a, "performance": p, "quality": qq,
        "plannedTimeRule": "actual_start_time -> (actual_end_time ?? now) (chuẩn Vinamilk)",
        "plannedSec": round(planned_sec, 1),
        "counts": {"total": total, "good": good, "defect": int(t.get("defect") or 0),
                   "reject": max(total - good, 0)},
        "progressRatio": _ratio(total, meta.get("planned_qty")),
        "time": {"runSec": round(run, 1),
                 "stoppedSec": round(float(t.get("stopped_sec") or 0), 1),
                 "faultedSec": round(float(t.get("faulted_sec") or 0), 1),
                 "maintSec": round(float(t.get("maint_sec") or 0), 1)},
    }
STATES = ["NO_DATA", "OFF", "STARTING", "RUNNING", "STOPPED", "FAULTED", "MAINTENANCE"]


@router.get("/downtime", summary="Tong hop downtime theo may/line: thoi gian, so lan, MTTR, top N")
def downtime(groupBy: Literal["machine", "line"] = "machine",
             states: str = Query("STOPPED,FAULTED", description=f"tap con cua {','.join(STATES)}"),
             top: int = Query(10, ge=1, le=100), last: str | None = None,
             preset: Literal["today", "yesterday", "current_shift", "previous_shift"] | None = None,
             from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
             machineId: str | None = None, lineId: str | None = None):
    w = resolve_window(last, preset, from_, to)
    st = [s.upper() for s in _csv(states) or []]
    if not st or any(s not in STATES for s in st):
        raise HTTPException(400, f"states hop le: {STATES}")
    key = "i.machine_id, i.line_id" if groupBy == "machine" else "i.line_id"
    params = {"frm": w["from"], "to": w["to"], "st": st, "mids": _csv(machineId), "lids": _csv(lineId)}
    rows = q(f"""
        SELECT {key}, i.state_name,
          count(*) FILTER (WHERE i.start_ts >= %(frm)s)::int AS events,
          sum(EXTRACT(EPOCH FROM LEAST(i.end_ts, %(to)s) - GREATEST(i.start_ts, %(frm)s)))::float8 AS seconds,
          avg(i.duration_sec) FILTER (WHERE NOT i.is_open)::float8 AS avg_duration_sec,
          max(i.duration_sec)::float8 AS max_duration_sec
        FROM machine_state_interval i
        WHERE i.end_ts > %(frm)s AND i.start_ts < %(to)s AND i.state_name = ANY(%(st)s)
          AND (%(mids)s::text[] IS NULL OR i.machine_id = ANY(%(mids)s))
          AND (%(lids)s::text[] IS NULL OR i.line_id = ANY(%(lids)s))
        GROUP BY {key}, i.state_name""", params)
    agg: dict[tuple, dict] = {}
    for r in rows:
        k = (r.get("machine_id"), r["line_id"])
        a = agg.setdefault(k, {"machine_id": r.get("machine_id"), "line_id": r["line_id"], "seconds": 0.0,
                               "events": 0, "byState": {}})
        a["seconds"] += r["seconds"]; a["events"] += r["events"]
        a["byState"][r["state_name"]] = {"seconds": round(r["seconds"], 1), "events": r["events"],
                                         "avgDurationSec": round(r["avg_duration_sec"] or 0, 1),
                                         "maxDurationSec": round(r["max_duration_sec"] or 0, 1)}
    items = sorted(agg.values(), key=lambda x: -x["seconds"])
    for it in items:
        it["seconds"] = round(it["seconds"], 1)
        it["mttrSec"] = round(it["seconds"] / it["events"], 1) if it["events"] else None
        if groupBy == "line":
            it.pop("machine_id")
    return {"window": _window_doc(w), "groupBy": groupBy, "states": st,
            "totalSeconds": round(sum(i["seconds"] for i in items), 1),
            "totalEvents": sum(i["events"] for i in items), "items": items[:top]}


@router.get("/downtime/events", summary="Danh sach khoang trang thai (su kien dung may) trong cua so")
def downtime_events(states: str = "STOPPED,FAULTED", minDurationSec: float = 0,
                    order: Literal["start_desc", "duration_desc"] = "start_desc",
                    limit: int = Query(100, ge=1, le=1000), last: str | None = None,
                    preset: Literal["today", "yesterday", "current_shift", "previous_shift"] | None = None,
                    from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                    machineId: str | None = None, lineId: str | None = None):
    w = resolve_window(last, preset, from_, to)
    st = [s.upper() for s in _csv(states) or []]
    rows = q(f"""
        SELECT machine_id, line_id, state_name, start_ts, end_ts, duration_sec, is_open, shift_id, shift_date
        FROM machine_state_interval
        WHERE end_ts > %(frm)s AND start_ts < %(to)s AND state_name = ANY(%(st)s)
          AND duration_sec >= %(mind)s
          AND (%(mids)s::text[] IS NULL OR machine_id = ANY(%(mids)s))
          AND (%(lids)s::text[] IS NULL OR line_id = ANY(%(lids)s))
        ORDER BY {'start_ts DESC' if order == 'start_desc' else 'duration_sec DESC'}
        LIMIT %(lim)s""", {"frm": w["from"], "to": w["to"], "st": st, "mind": minDurationSec,
                           "mids": _csv(machineId), "lids": _csv(lineId), "lim": limit})
    return {"window": _window_doc(w), "count": len(rows), "items": rows}


# =============================================================== trend tag
@router.get("/tags/trend", summary="Trend tag so (avg/min/max/last) theo bucket - nhiet do, toc do, ap suat ...")
def tag_trend(machineId: str, tagName: str = Query(..., description="danh sach, cach nhau dau phay"),
              bucket: Literal["1m", "5m", "15m", "30m", "1h", "1d"] = "5m", last: str | None = None,
              preset: Literal["today", "yesterday", "current_shift", "previous_shift"] | None = None,
              from_: datetime | None = Query(None, alias="from"), to: datetime | None = None):
    w = resolve_window(last, preset, from_, to)
    b = bucket_expr(bucket, "t.ts_minute")[0]
    rows = q(f"""
        SELECT t.tag_name, {b},
          (sum(t.sum) / nullif(sum(t.n), 0))::float8 AS avg, min(t.min)::float8 AS min,
          max(t.max)::float8 AS max, (array_agg(t.last ORDER BY t.ts_minute DESC))[1]::float8 AS last,
          sum(t.n)::int AS samples
        FROM tag_metric_1m t
        WHERE t.machine_id = %(mid)s AND t.tag_name = ANY(%(tags)s)
          AND t.ts_minute >= %(frm)s AND t.ts_minute < %(to)s
        GROUP BY t.tag_name, bucket ORDER BY t.tag_name, bucket""",
             {"mid": machineId, "tags": _csv(tagName), "frm": w["from"], "to": w["to"]})
    series: dict[str, list] = {}
    for r in rows:
        series.setdefault(r.pop("tag_name"), []).append(r)
    return {"window": _window_doc(w), "machineId": machineId, "bucket": bucket, "series": series}


@router.get("/tags", summary="Danh sach tag so co du lieu cua 1 may (de chon trend)")
def tag_list(machineId: str, last: str | None = "1h"):
    w = resolve_window(last, None, None, None)
    rows = q("SELECT tag_name, sum(n)::int AS samples FROM tag_metric_1m WHERE machine_id = %(mid)s "
             "AND ts_minute >= %(frm)s AND ts_minute < %(to)s GROUP BY tag_name ORDER BY tag_name",
             {"mid": machineId, "frm": w["from"], "to": w["to"]})
    return {"machineId": machineId, "tags": rows}


# =============================================================== chat luong du lieu
@router.get("/data-quality", summary="Chat luong du lieu pipeline: valid / invalid / duplicate / missing / late")
def data_quality(groupBy: Literal["plant", "machine"] = "plant", bucket: Bucket | None = None,
                 last: str | None = None,
                 preset: Literal["today", "yesterday", "current_shift", "previous_shift"] | None = None,
                 from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                 machineId: str | None = None):
    w = resolve_window(last, preset, from_, to)
    if bucket == "shift":
        raise HTTPException(400, "data-quality khong ho tro bucket=shift")
    dims = (["d.machine_id"] if groupBy == "machine" else []) + bucket_expr(bucket, "d.ts_minute")
    keys = [x.split(" AS ")[-1] for x in dims]
    rows = q(f"""
        SELECT {', '.join(dims) + ',' if dims else ''}
          sum(received)::bigint AS received, sum(invalid)::bigint AS invalid, sum(duplicate)::bigint AS duplicate,
          sum(missing_value)::bigint AS missing_value, sum(late)::bigint AS late,
          sum(bad_quality)::bigint AS bad_quality, sum(valid)::bigint AS valid
        FROM data_quality_1m d
        WHERE d.ts_minute >= %(frm)s AND d.ts_minute < %(to)s
          AND (%(mids)s::text[] IS NULL OR d.machine_id = ANY(%(mids)s))
        {('GROUP BY ' + ', '.join(keys) + ' ORDER BY ' + ', '.join(keys)) if keys else ''}""",
             {"frm": w["from"], "to": w["to"], "mids": _csv(machineId)})
    for r in rows:
        r["dataQualityRate"] = _ratio(r["valid"], r["received"])
    return {"window": _window_doc(w), "groupBy": groupBy, "bucket": bucket,
            "formula": "dataQualityRate = valid / received", "items": rows}


# =============================================================== tong quan + do tuoi
@router.get("/overview", summary="The KPI man Overview: OEE nha may, san luong, loi, downtime, top may dung")
def overview(last: str | None = None,
             preset: Literal["today", "yesterday", "current_shift", "previous_shift"] | None = "current_shift",
             from_: datetime | None = Query(None, alias="from"), to: datetime | None = None):
    if last or from_ or to:
        preset = None
    w = resolve_window(last, preset, from_, to)
    plant = kpi_rows(w, "plant", None, None, None, True)
    lines = kpi_rows(w, "line", None, None, None, True)
    allm = kpi_rows(w, "plant", None, None, None, False)
    dt = downtime(groupBy="machine", states="STOPPED,FAULTED", top=5, last=None, preset=None,
                  from_=w["from"], to=w["to"], machineId=None, lineId=None)
    dq = data_quality(groupBy="plant", bucket=None, last=None, preset=None, from_=w["from"], to=w["to"],
                      machineId=None)
    p = plant[0] if plant else {}
    return {
        "window": _window_doc(w),
        "plant": {"oee": p.get("oee"), "availability": p.get("availability"), "performance": p.get("performance"),
                  "quality": p.get("quality"), "production": p.get("counts"), "rejectRate": p.get("rejectRate")},
        "lines": [{"line_id": x["line_id"], "oee": x["oee"], "availability": x["availability"],
                   "performance": x["performance"], "quality": x["quality"], "production": x["counts"]}
                  for x in lines],
        "allMachines": ({"machines": allm[0]["machines"], "stopEvents": allm[0]["stopEvents"],
                         "downtimeSec": round(allm[0]["time"]["stopped_sec"] + allm[0]["time"]["faulted_sec"], 1),
                         "dataCoverage": allm[0]["dataCoverage"]} if allm else None),
        "topDowntime": dt["items"],
        "dataQualityRate": dq["items"][0]["dataQualityRate"] if dq["items"] else None,
    }


@router.get("/freshness", summary="Du lieu batch da tinh den dau + cac lan chay gan nhat")
def freshness(limit: int = Query(10, ge=1, le=100)):
    f = q("SELECT data_until, last_success_at FROM batch_freshness")[0]
    runs = q("SELECT run_id, job, range_start, range_end, status, stats, error, started_at, finished_at "
             "FROM batch_run ORDER BY run_id DESC LIMIT %(n)s", {"n": limit})
    lag = (datetime.now(timezone.utc) - f["data_until"]).total_seconds() if f["data_until"] else None
    return {"dataUntil": f["data_until"], "lagSec": round(lag, 1) if lag is not None else None,
            "lastSuccessAt": f["last_success_at"], "runs": runs}


# =============================================================== dashboard (nguon chinh cho UI)
def _reference_machine(line_id: str) -> str | None:
    """Máy tham chiếu của 1 chuyền (công đoạn CHIẾT)."""
    rows = q("SELECT m.machine_id FROM machine m JOIN line l ON l.line_id = m.line "
             "WHERE m.line = %(line)s AND m.machine_type = ANY(%(types)s) "
             "ORDER BY CASE WHEN m.machine_id LIKE %(ref)s THEN 0 ELSE 1 END, m.machine_id LIMIT 1",
             {"line": line_id, "types": REF_MACHINE_TYPES, "ref": REF_PATTERN})
    return rows[0]["machine_id"] if rows else None


def _wo_kpi_for(wo: dict, ref_machine: str | None) -> dict:
    """Tính A/P/Q/OEE của 1 work order trên MÁY THAM CHIẾU.

    PlannedTime = actual_start_time -> (actual_end_time ?? now)  (chuẩn Vinamilk)
        A = run_sec(ref) / planned_sec(lenh)
        P = ideal_time_sec(ref) / run_sec(ref)
        Q = good_count(ref) / total_count(ref)
    """
    wo_id = wo["wo_id"]
    planned_sec = float(wo.get("elapsed_sec") or 0)
    params = {"wo": wo_id, "ref": ref_machine}
    rows = q("SELECT sum(total_count)::bigint AS total, sum(good_count)::bigint AS good, "
             "sum(defect_count)::bigint AS defect, sum(run_sec)::float8 AS run_sec, "
             "sum(stopped_sec)::float8 AS stopped_sec, sum(faulted_sec)::float8 AS faulted_sec, "
             "sum(maint_sec)::float8 AS maint_sec, sum(ideal_time_sec)::float8 AS ideal_sec "
             "FROM machine_kpi_1m WHERE wo_id = %(wo)s AND machine_id = %(ref)s", params)
    t = rows[0] if rows else {}
    run = float(t.get("run_sec") or 0)
    total = int(t.get("total") or 0)
    good = int(t.get("good") or 0)
    # ⚠ good > total là dữ liệu lỗi (counter lệch) → chặn, không hiện Q > 100%.
    good = min(good, total) if total > 0 else good
    a = _ratio_c(run, planned_sec) if planned_sec else None
    p = _ratio_c(float(t.get("ideal_sec") or 0), run) if run else None
    qq = _ratio_c(good, total)
    return {
        "oee": round(a * p * qq, 4) if None not in (a, p, qq) else None,
        "availability": a, "performance": p, "quality": qq,
        "plannedSec": round(planned_sec, 1),
        "counts": {"total": total, "good": good, "defect": int(t.get("defect") or 0),
                   "reject": max(total - good, 0)},
        "progressRatio": _ratio(total, wo.get("planned_qty")),
        "time": {"runSec": round(run, 1),
                 "stoppedSec": round(float(t.get("stopped_sec") or 0), 1),
                 "faultedSec": round(float(t.get("faulted_sec") or 0), 1),
                 "maintSec": round(float(t.get("maint_sec") or 0), 1)},
    }


@router.get("/dashboard",
            summary="KPI dashboard theo WORK ORDER dang chay (OEE/A/P/Q + san luong) — nguon chinh cho UI")
def dashboard():
    """KPI cho màn Plant Overview + Line View, TÍCH THEO WORK ORDER ĐANG CHẠY.

    ⚠ VÌ SAO GẮN THEO WORK ORDER (không theo ca):
        Yêu cầu nghiệp vụ: "đang chạy line A với WO B, đổi sang WO C thì OEE
        phải là của WO C — không liên quan gì tới WO B".
        Batch (`batch_kpi.py`) đã gán `wo_id` cho từng phút theo khoảng
        [actual_start_time, actual_end_time) và khoá theo chuyền → dữ liệu
        trong PG ĐÃ TÁCH BẠCH theo WO. Endpoint này chỉ đọc lại.

    CỬA SỔ TÍNH:
        · Có WO đang chạy (IN_PROGRESS/PAUSED) → khoảng thực tế của LỆNH.
        · Không có WO                     → ca hiện tại (fallback).
    """
    # ── 1. Work order đang chạy của mỗi chuyền ────────────────────────
    running = q("SELECT DISTINCT ON (line_id) wo_id, wo_code, line_id, product_id, status, "
                "planned_qty, actual_start_time, actual_end_time, "
                "EXTRACT(EPOCH FROM (COALESCE(actual_end_time, now()) - actual_start_time)) AS elapsed_sec "
                "FROM work_order WHERE status IN ('IN_PROGRESS','PAUSED') "
                "AND actual_start_time IS NOT NULL "
                "ORDER BY line_id, actual_start_time DESC NULLS LAST")

    # ── 2. Chuyền nào không có WO → dùng ca hiện tại ───────────────────
    covered = {r["line_id"] for r in running}
    all_lines = q("SELECT line_id, line_name, unit FROM line ORDER BY line_id")
    fallback_lines = [r["line_id"] for r in all_lines if r["line_id"] not in covered]

    shift_rows: list[dict] = []
    if fallback_lines:
        w = resolve_window(None, "current_shift", None, None)
        shift_rows = kpi_rows(w, "line", None, None, _csv(",".join(fallback_lines)), True)

    out_lines: list[dict] = []
    for ln in all_lines:
        line_id = ln["line_id"]
        wo = next((r for r in running if r["line_id"] == line_id), None)
        ref = _reference_machine(line_id)
        if wo:
            kpi = _wo_kpi_for(wo, ref)
            out_lines.append({
                "line_id": line_id,
                "line_name": ln["line_name"],
                "unit": ln["unit"],
                "referenceMachine": ref,
                "scope": "work_order",
                "workOrder": {
                    "woId": wo["wo_id"], "woCode": wo["wo_code"], "lineId": line_id,
                    "productId": wo["product_id"], "status": wo["status"],
                    "plannedQty": wo["planned_qty"],
                    "actualStartTime": wo["actual_start_time"],
                    "actualEndTime": wo["actual_end_time"],
                },
                **kpi,
            })
        else:
            s = next((x for x in shift_rows if x.get("line_id") == line_id), None)
            out_lines.append({
                "line_id": line_id,
                "line_name": ln["line_name"],
                "unit": ln["unit"],
                "referenceMachine": ref,
                "scope": "shift",
                "workOrder": None,
                "oee": s.get("oee") if s else None,
                "availability": s.get("availability") if s else None,
                "performance": s.get("performance") if s else None,
                "quality": s.get("quality") if s else None,
                "plannedSec": s.get("time", {}).get("planned_sec") if s else None,
                "counts": s.get("counts") if s else None,
                "progressRatio": None,
                "time": s.get("time") if s else None,
            })

    # ── 3. Tổng nhà máy = trung bình GIA QUYỀN theo sản lượng ─────────
    wts = [l for l in out_lines if l.get("counts") and l["counts"].get("total")]
    tot = sum(l["counts"]["total"] for l in wts)
    plant: dict = {"oee": None, "availability": None, "performance": None, "quality": None}
    if tot > 0:
        agg = {"availability": 0.0, "performance": 0.0, "quality": 0.0}
        for l in wts:
            w = l["counts"]["total"]
            for k in agg:
                agg[k] += (l.get(k) or 0) * w
        plant = {k: round(v / tot, 4) for k, v in agg.items()}
        plant["oee"] = round(plant["availability"] * plant["performance"] * plant["quality"], 4)
    plant["production"] = {
        "total": sum(l["counts"]["total"] for l in wts),
        "good": sum(l["counts"]["good"] for l in wts),
        "defect": sum(l["counts"]["defect"] for l in wts),
        "reject": sum(l["counts"]["reject"] for l in wts),
    }
    plant["linesWithWorkOrder"] = len(covered)

    fresh = q("SELECT data_until, last_success_at FROM batch_freshness")[0]
    lag = (datetime.now(timezone.utc) - fresh["data_until"]).total_seconds() if fresh["data_until"] else None
    return {
        "plant": plant,
        "lines": out_lines,
        "dataUntil": fresh["data_until"],
        "lagSec": round(lag, 1) if lag is not None else None,
        "lastSuccessAt": fresh["last_success_at"],
        "formula": "A=run/planned(lenh), P=ideal/run, Q=good/total, OEE=A*P*Q — theo WORK ORDER",
    }
