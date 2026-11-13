"""
Client WebSocket test cho state-api: nhan snapshot + patch, ghep thanh trang thai cuc bo
(dung cach frontend se lam), cuoi cung so voi REST de chung minh khong mat / khong lui ban.

Chay trong container state-api (da co thu vien websockets):
    docker compose exec -T state-api python - --duration 60 < scripts/ws_client.py
    docker compose exec -T state-api python - --machine L01_FILLER_01 --duration 20 --verbose < scripts/ws_client.py
Tham so:
    --machine A,B  / --line LINE_01   bo loc
    --duration N   so giay nghe
    --quiet N      sau duration, doi them den khi N giay khong co patch roi moi so voi REST
                   (nen dung middleware-sim de du lieu dung yen, neu khong se bo qua buoc so sanh)
"""
import argparse
import asyncio
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

import websockets

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="ws://localhost:8000/ws/machines")
ap.add_argument("--machine")
ap.add_argument("--line")
ap.add_argument("--duration", type=float, default=30)
ap.add_argument("--quiet", type=float, default=5)
ap.add_argument("--max-wait", type=float, default=90)
ap.add_argument("--verbose", action="store_true")
args = ap.parse_args()


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


state: dict[str, dict] = {}      # machineId -> {"summary":..., "tags": {...}}
stats = {"snapshot": 0, "patch": 0, "heartbeat": 0, "pong": 0, "tagUpdates": 0, "regress": 0}
lat = []


def apply_machine(m, replace):
    mid = m["machineId"]
    cur = state.get(mid) if not replace else None
    tags = dict(cur["tags"]) if cur else {}
    for name, t in m.get("tags", {}).items():
        old = tags.get(name)
        if old and not replace and (old["eventTime"] or "") > (t["eventTime"] or ""):
            stats["regress"] += 1       # nhan ban cu hon ban dang co -> loi thu tu
            continue
        tags[name] = t
    state[mid] = {"summary": {k: v for k, v in m.items() if k != "tags"}, "tags": tags}


async def main():
    q = {k: v for k, v in (("machineId", args.machine), ("lineId", args.line)) if v}
    url = args.url + ("?" + urllib.parse.urlencode(q) if q else "")
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({"action": "ping"}))
        t0 = time.time()
        last_patch = time.time()
        while True:
            el = time.time() - t0
            if el > args.duration and (time.time() - last_patch >= args.quiet or el > args.max_wait):
                break
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                continue
            msg = json.loads(raw)
            typ = msg["type"]
            stats[typ] = stats.get(typ, 0) + 1
            if typ == "snapshot":
                state.clear()
                for m in msg["machines"]:
                    apply_machine(m, replace=True)
                print(f"[{el:5.1f}s] snapshot ready={msg['ready']} machines={len(msg['machines'])} "
                      f"tags={sum(len(m['tags']) for m in msg['machines'])} bytes={len(raw)}")
            elif typ == "patch":
                last_patch = time.time()
                st = ts(msg["serverTime"])
                n = 0
                for m in msg["machines"]:
                    apply_machine(m, replace=False)
                    for t in m["tags"].values():
                        n += 1
                        lat.append((st - ts(t["eventTime"])).total_seconds() * 1000)
                stats["tagUpdates"] += n
                if args.verbose:
                    for m in msg["machines"]:
                        print(f"[{el:5.1f}s] patch {m['machineId']} state={m['state']} "
                              + ", ".join(f"{k}={v['value']}" for k, v in m["tags"].items()))
            elif args.verbose:
                print(f"[{el:5.1f}s] {msg}")

    lat.sort()
    print("thong ke:", json.dumps(stats))
    if lat:
        print(f"do tre eventTime -> server gui WS (ms): p50={lat[len(lat)//2]:.0f} "
              f"p95={lat[int(len(lat)*.95)]:.0f} max={lat[-1]:.0f} (n={len(lat)})")

    if time.time() - last_patch < args.quiet:
        print("du lieu van dang doi -> bo qua so sanh REST (dung middleware-sim de so)")
        return
    mism = 0
    for mid, s in state.items():
        with urllib.request.urlopen(f"http://localhost:8000/api/machines/{mid}") as r:
            rest = json.load(r)
        for name, t in rest["tags"].items():
            mine = s["tags"].get(name)
            if not mine or mine["value"] != t["value"] or mine["eventTime"] != t["eventTime"]:
                mism += 1
                if mism <= 5:
                    print("  LECH", mid, name, mine and mine["value"], t["value"])
        if rest["state"] != s["summary"].get("state"):
            mism += 1
            print("  LECH state", mid, s["summary"].get("state"), rest["state"])
    print(f"so voi REST: {len(state)} may, {mism} lech, {stats['regress']} lan lui ban")
    print("PASS" if mism == 0 and stats["regress"] == 0 and stats["snapshot"] >= 1 else "FAIL")


asyncio.run(main())
