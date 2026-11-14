"""Kiem tra vong doi Work Order end-to-end tren master-api (:8001).

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\test_wo_flow.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001"


def call(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def step(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


step("0. Don lenh dang chay cu (mo chuyen cho lenh moi)")
st, r = call("GET", "/api/work-orders/current")
for w in r["workOrders"]:
    print(f"   dang chay: {w['wo_code']} ({w['line_id']}) -> huy/complete de mo chuyen")
    st2, r2 = call("POST", f"/api/work-orders/{w['wo_id']}/cancel", {"operator_id": "cleanup"})
    print(f"      cancel: HTTP {st2} -> {r2.get('workOrder', {}).get('status') if isinstance(r2, dict) else r2}")

step("1. Tao phieu moi (DRAFT)")
st, r = call("POST", "/api/work-orders", {
    "line_id": "LINE_01",
    "product_id": "PET-500-COKE",
    "planned_qty": 12000,
    "unit": "bottles",
    "note": "kiem tra vong doi WO",
    "operator_id": "tester",
})
print(f"   HTTP {st}")
if st != 201:
    print("   FAIL:", r)
    raise SystemExit(1)
wo = r["workOrder"]
wo_id = wo["wo_id"]
print(f"   wo_id   = {wo_id}")
print(f"   wo_code = {wo['wo_code']}")
print(f"   status  = {wo['status']}  seq={wo['seq']}")

step("2. Phat hanh (DRAFT -> RELEASED)")
st, r = call("POST", f"/api/work-orders/{wo_id}/release", {"operator_id": "tester"})
print(f"   HTTP {st}  status -> {r.get('workOrder', {}).get('status')}")

step("3. Bat dau (RELEASED -> IN_PROGRESS) + chup baseline")
st, r = call("POST", f"/api/work-orders/{wo_id}/start", {"operator_id": "tester"})
print(f"   HTTP {st}  status -> {r.get('workOrder', {}).get('status')}")
print(f"   baseline = {r.get('baseline')}")

step("4. Bat dau lenh thu 2 cung chuyen -> phai bi tu choi (409)")
st, r = call("POST", "/api/work-orders", {
    "line_id": "LINE_01", "product_id": "PET-500-COKE", "planned_qty": 500,
})
wo2_id = r["workOrder"]["wo_id"] if st == 201 else None
print(f"   tao lenh 2: HTTP {st} -> {wo2_id}")
if wo2_id:
    call("POST", f"/api/work-orders/{wo2_id}/release", {"operator_id": "tester"})
    st2, r2 = call("POST", f"/api/work-orders/{wo2_id}/start", {"operator_id": "tester"})
    print(f"   start lenh 2: HTTP {st2} (mong doi 409)")
    print(f"      {r2.get('detail') if isinstance(r2, dict) else r2}")

step("5. Tam dung / tiep tuc")
st, r = call("POST", f"/api/work-orders/{wo_id}/pause", {"operator_id": "tester"})
print(f"   pause : HTTP {st} -> {r.get('workOrder', {}).get('status')}")
st, r = call("POST", f"/api/work-orders/{wo_id}/resume", {"operator_id": "tester"})
print(f"   resume: HTTP {st} -> {r.get('workOrder', {}).get('status')}")

step("6. Hoan thanh")
st, r = call("POST", f"/api/work-orders/{wo_id}/complete", {"operator_id": "tester"})
wo_done = r.get("workOrder", {})
print(f"   HTTP {st} -> {wo_done.get('status')}")
print(f"   actual_start = {wo_done.get('actual_start_time')}")
print(f"   actual_end   = {wo_done.get('actual_end_time')}")

step("7. Nhat ky hanh dong")
st, r = call("GET", f"/api/work-orders/{wo_id}/log")
for e in r["logs"]:
    ts = e["action_at"]
    ts_s = ts[11:19] if isinstance(ts, str) else f"{ts:%H:%M:%S}"
    print(f"   {ts_s} {e['action']:<9} {e['old_status']} -> {e['new_status']}  by={e['action_by']}")

step("8. Danh sach + tien do")
st, r = call("GET", "/api/work-orders")
print(f"   tong so lenh = {len(r['workOrders'])}")
for w in r["workOrders"]:
    print(f"   {w['wo_code']:<18} {w['line_id']:<9} {w['status']:<12} "
          f"plan={w['planned_qty']} actual={w['actual_qty']} good={w['good_qty']} "
          f"defect={w['defect_qty']} quality={w['quality']}")

step("9. WO dang chay theo chuyen")
st, r = call("GET", "/api/work-orders/current")
for w in r["workOrders"]:
    print(f"   {w['line_id']:<9} {w['wo_code']:<18} {w['status']}")

print()
print("XONG - vong doi WO hoat dong tren master-api")
