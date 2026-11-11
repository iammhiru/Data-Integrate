#!/usr/bin/env python3
"""
Sinh event envelope mau (da chuan hoa nhu output cua Middleware) de test pipeline.
Khong can thu vien ngoai. In ra stdout moi dong dang "<machineId>|<json>"
de pipe vao kafka-console-producer (parse.key=true, key.separator=|).

Co chu dich chen loi de kiem tra data quality:
  --dup-rate      event gui lai voi cung eventId (duplicate)
  --missing-rate  thieu 1 truong bat buoc trong payload (null)
  --invalid-rate  envelope loi (thieu eventId / timestamp sai)
  --late-rate     event time lui ve qua khu 2-5 phut (late / out-of-order)

Vi du:
  python3 scripts/generate_test_events.py --type telemetry --machines 10 --seconds 60 \
    | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
        --bootstrap-server kafka:9092 --topic machine-telemetry \
        --property parse.key=true --property key.separator='|'
"""
import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

PRODUCTS = ["P01", "P02", "P03", "P04", "P05"]
DEFECTS = ["SCRATCH", "DENT", "DIMENSION", "COLOR"]
SHIFTS = [("A", 6, 14), ("B", 14, 22), ("C", 22, 6)]

EVENT_TYPES = {
    "telemetry": ("machine.telemetry", "kepware-opcua"),
    "production": ("production.event", "production-sim"),
    "quality": ("quality.event", "quality-sim"),
}


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def shift_of(ts: datetime) -> str:
    h = ts.hour
    for sid, s, e in SHIFTS:
        if (s < e and s <= h < e) or (s > e and (h >= s or h < e)):
            return sid
    return "A"


def telemetry_payload(rng, state):
    if rng.random() < 0.02:  # thinh thoang doi trang thai
        state["status"] = rng.choices(["RUNNING", "IDLE", "STOPPED"], [0.8, 0.12, 0.08])[0]
    running = state["status"] == "RUNNING"
    return {
        "temperature": round(rng.gauss(72, 3) if running else rng.gauss(40, 2), 2),
        "pressure": round(rng.gauss(5.5, 0.3), 3),
        "speed": round(rng.gauss(1450, 40), 1) if running else 0.0,
        "energy": round(rng.uniform(0.8, 1.4) if running else rng.uniform(0.05, 0.2), 4),
        "vibration": round(abs(rng.gauss(2.1, 0.4)), 3),
        "status": state["status"],
        "operatingMode": "AUTO",
    }


def production_payload(rng, ts):
    qty = rng.randint(5, 20)
    reject = sum(rng.random() < 0.03 for _ in range(qty))
    return {
        "productId": rng.choice(PRODUCTS),
        "productionOrder": f"PO-{ts:%Y%m%d}-{rng.randint(1, 50):03d}",
        "quantity": qty,
        "goodQuantity": qty - reject,
        "rejectQuantity": reject,
        "shift": shift_of(ts),
        "idealCycleTime": 2.5,
    }


def quality_payload(rng):
    qty = rng.randint(5, 20)
    reject = sum(rng.random() < 0.04 for _ in range(qty))
    return {
        "productId": rng.choice(PRODUCTS),
        "inspectionId": f"INS-{uuid.uuid4().hex[:10]}",
        "result": "FAIL" if reject else "PASS",
        "defectType": rng.choice(DEFECTS) if reject else None,
        "quantity": qty,
        "rejectQuantity": reject,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=EVENT_TYPES, required=True)
    p.add_argument("--machines", type=int, default=10)
    p.add_argument("--seconds", type=int, default=60,
                   help="khoang thoi gian mo phong (lui ve tu hien tai); voi --live: so giay chay, 0 = mai mai")
    p.add_argument("--live", action="store_true",
                   help="phat event theo thoi gian thuc (event time = hien tai), flush tung giay")
    p.add_argument("--rate", type=float, default=1.0, help="event / giay / may")
    p.add_argument("--dup-rate", type=float, default=0.02)
    p.add_argument("--missing-rate", type=float, default=0.02)
    p.add_argument("--invalid-rate", type=float, default=0.01)
    p.add_argument("--late-rate", type=float, default=0.02)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    rng = random.Random(f"{args.seed}-{args.type}")
    event_type, source = EVENT_TYPES[args.type]
    states = {m: {"status": "RUNNING"} for m in range(1, args.machines + 1)}

    if args.live:
        t0 = time.time()
        def ticks():
            i = 0
            while args.seconds == 0 or i < args.seconds * args.rate:
                time.sleep(max(0.0, t0 + i / args.rate - time.time()))
                yield datetime.now(timezone.utc)
                i += 1
    else:
        start = datetime.now(timezone.utc) - timedelta(seconds=args.seconds)
        def ticks():
            for i in range(int(args.seconds * args.rate)):
                yield start + timedelta(seconds=i / args.rate)

    for base_ts in ticks():
        for m in range(1, args.machines + 1):
            machine_id = f"M{m:03d}"
            if args.live:   # event vua phat sinh, middleware nhan sau vai chuc ms
                ingested = datetime.now(timezone.utc)
                ts = ingested - timedelta(milliseconds=rng.randint(5, 80))
            else:
                ts = base_ts + timedelta(milliseconds=rng.randint(0, 900))
                ingested = ts + timedelta(milliseconds=rng.randint(5, 80))
            if rng.random() < args.late_rate:
                ts -= timedelta(seconds=rng.randint(120, 300))

            if args.type == "telemetry":
                payload = telemetry_payload(rng, states[m])
            elif args.type == "production":
                payload = production_payload(rng, ts)
            else:
                payload = quality_payload(rng)

            if rng.random() < args.missing_rate:
                payload[rng.choice([k for k in payload if k not in ("operatingMode", "inspectionId")])] = None

            event = {
                "eventId": str(uuid.uuid4()),
                "eventType": event_type,
                "source": source,
                "machineId": machine_id,
                "timestamp": iso(ts),
                "ingestedAt": iso(ingested),
                "schemaVersion": 1,
                "payload": payload,
            }
            if rng.random() < args.invalid_rate:
                if rng.random() < 0.5:
                    event.pop("eventId")
                else:
                    event["timestamp"] = "not-a-timestamp"

            line = f"{machine_id}|{json.dumps(event, separators=(',', ':'))}"
            print(line)
            if rng.random() < args.dup_rate:
                print(line)
        if args.live:
            sys.stdout.flush()


if __name__ == "__main__":
    main()
