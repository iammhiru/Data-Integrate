"""
Doi chieu luong trang thai may voi mot phep tinh doc lap.

1. Doc TOAN BO topic nguon `industrial.telemetry` tu dau, tu tinh gia tri moi nhat cua moi
   (machineId, tagName) theo eventTime (giong logic contract: eventTime la nguon su that).
2. Goi API GET /api/machines/{id} cho tung may, so sanh tung tag (value, statusCode, eventTime).
3. Doc topic `machine-state`: dem message, do do tre emittedAt - eventTime.

Nen DUNG middleware truoc khi chay (de du lieu khong doi trong luc so sanh):
    docker compose stop middleware-sim && sleep 5
    docker compose exec -T state-api python - < scripts/verify_machine_state.py
Chay trong container state-api vi da co san confluent_kafka va mang docker.
"""
import json
import statistics
import sys
import urllib.request
from datetime import datetime

from confluent_kafka import Consumer, TopicPartition, OFFSET_BEGINNING

BOOTSTRAP, API = "kafka:9092", "http://localhost:8000"


def read_all(topic):
    c = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": "verify", "enable.auto.commit": False})
    parts = sorted(c.list_topics(topic, timeout=10).topics[topic].partitions)
    hw = {p: c.get_watermark_offsets(TopicPartition(topic, p), timeout=10) for p in parts}
    c.assign([TopicPartition(topic, p, OFFSET_BEGINNING) for p in parts])
    left = {p for p, (lo, hi) in hw.items() if hi > lo}
    while left:
        m = c.poll(5)
        if m is None:
            break
        if m.error():
            continue
        yield m
        if m.offset() + 1 >= hw[m.partition()][1]:
            left.discard(m.partition())
    c.close()


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---- 1. ket qua mong doi tu topic nguon
expected, n_src, n_bad = {}, 0, 0
for m in read_all("industrial.telemetry"):
    n_src += 1
    try:
        e = json.loads(m.value())
        key = (e["machine"]["machineId"], e["tag"]["tagName"])
        t = e["eventTime"]
    except (ValueError, KeyError, TypeError):
        n_bad += 1
        continue
    if key not in expected or t >= expected[key]["eventTime"]:
        expected[key] = {"value": e["measurement"]["value"], "statusCode": e["quality"]["statusCode"],
                         "eventTime": t}
print(f"nguon industrial.telemetry: {n_src} message, {n_bad} hong, {len(expected)} cap (may, tag)")

# ---- 2. so voi API
machines = {k[0] for k in expected}
mismatch, checked = [], 0
for mid in sorted(machines):
    with urllib.request.urlopen(f"{API}/api/machines/{mid}") as r:
        tags = json.load(r)["tags"]
    for (m_id, tag), exp in expected.items():
        if m_id != mid:
            continue
        checked += 1
        got = tags.get(tag)
        if got is None:
            mismatch.append((mid, tag, "missing", exp))
            continue
        same_val = (got["value"] == exp["value"]) or (
            isinstance(exp["value"], float) and got["value"] is not None
            and abs(got["value"] - exp["value"]) < 1e-9)
        if not same_val or got["statusCode"] != exp["statusCode"] or got["eventTime"] != exp["eventTime"]:
            mismatch.append((mid, tag, got, exp))
print(f"API: {len(machines)} may, {checked} tag doi chieu, {len(mismatch)} lech")
for x in mismatch[:10]:
    print("  LECH", x)

# ---- 3. topic compacted + do tre
n_out, keys, lat = 0, set(), []
for m in read_all("machine-state"):
    n_out += 1
    keys.add(m.key())
    r = json.loads(m.value())
    lat.append((ts(r["emittedAt"]) - ts(r["eventTime"])).total_seconds() * 1000)
lat.sort()
print(f"machine-state: {n_out} message, {len(keys)} key "
      f"(giam {100 * (1 - n_out / max(1, n_src)):.0f}% so voi nguon)")
if lat:
    print(f"do tre eventTime -> Spark ghi (ms): p50={lat[len(lat) // 2]:.0f} "
          f"p95={lat[int(len(lat) * .95)]:.0f} max={lat[-1]:.0f} avg={statistics.mean(lat):.0f}")

ok = not mismatch and len(keys) == len(expected)
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
