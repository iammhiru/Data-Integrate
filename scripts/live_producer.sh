#!/usr/bin/env bash
# Phat event theo thoi gian thuc vao Kafka (telemetry + production + quality) de demo luong realtime.
#
#   ./scripts/live_producer.sh                  # 20 may, chay mai mai (Ctrl+C de dung)
#   MACHINES=50 RATE=2 SECONDS_=120 ./scripts/live_producer.sh
#
# RATE = telemetry event / giay / may; production & quality = RATE / 10.
set -euo pipefail
cd "$(dirname "$0")/.."

MACHINES=${MACHINES:-20}
RATE=${RATE:-1}
SECONDS_=${SECONDS_:-0}
SLOW_RATE=$(python3 -c "print($RATE / 10)")

produce() {  # type topic rate
  python3 -u scripts/generate_test_events.py --type "$1" --machines "$MACHINES" --rate "$3" \
      --seconds "$SECONDS_" --live 2>/dev/null \
    | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
        --bootstrap-server kafka:9092 --topic "$2" \
        --property parse.key=true --property key.separator='|' \
        --producer-property linger.ms=50
}

echo "Live producer: $MACHINES may, telemetry $RATE ev/s/may, thoi gian ${SECONDS_}s (0 = mai mai)"
trap 'kill 0' INT TERM
produce telemetry machine-telemetry "$RATE" &
produce production production-events "$SLOW_RATE" &
produce quality quality-events "$SLOW_RATE" &
wait
