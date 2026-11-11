#!/usr/bin/env python3
"""
Do latency luong realtime tu topic `realtime-metrics`.
latencyMs = emittedAt (Spark ghi ra Kafka) - maxIngestedAt (middleware nhan event moi nhat trong window).

  docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 \
      --topic realtime-metrics --from-beginning --max-messages 5000 --timeout-ms 10000 \
    | python3 scripts/measure_latency.py
"""
import argparse
import json
import statistics
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--since", help="chi tinh message co emittedAt >= gia tri nay (ISO, UTC), vd 2026-11-11T13:30:00")
ap.add_argument("--skip-seconds", type=int, default=0,
                help="bo qua N giay dau ke tu message dau tien (warm-up JVM)")
args = ap.parse_args()

msgs = []
for line in sys.stdin:
    line = line.strip()
    if line.startswith("{"):
        m = json.loads(line)
        if m.get("latencyMs") is not None and (not args.since or m["emittedAt"] >= args.since):
            msgs.append(m)
if args.skip_seconds and msgs:
    from datetime import datetime, timedelta
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    cutoff = min(parse(m["emittedAt"]) for m in msgs) + timedelta(seconds=args.skip_seconds)
    msgs = [m for m in msgs if parse(m["emittedAt"]) >= cutoff]

by_type = {}
for m in msgs:
    by_type.setdefault(m["metricType"], []).append(m["latencyMs"])

if not by_type:
    sys.exit("khong co message nao")

print(f"{'metricType':<22}{'n':>7}{'avg ms':>10}{'p50 ms':>10}{'p95 ms':>10}{'max ms':>10}")
for t, v in sorted(by_type.items()):
    v.sort()
    pct = lambda q: v[min(len(v) - 1, int(q * len(v)))]  # noqa: E731
    print(f"{t:<22}{len(v):>7}{statistics.mean(v):>10.0f}{pct(0.5):>10.0f}{pct(0.95):>10.0f}{v[-1]:>10.0f}")
