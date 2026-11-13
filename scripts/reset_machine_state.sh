#!/usr/bin/env bash
# Reset luong trang thai may: xoa checkpoint Spark + tao lai topic industrial.telemetry, machine-state.
# CANH BAO: mat toan bo du lieu trong 2 topic tren.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose --profile telemetry stop middleware-sim stream-machine-state state-api
docker compose run --rm --no-deps -T --entrypoint rm spark-master -rf /opt/spark-checkpoints/machine-state
for t in industrial.telemetry machine-state; do
  docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --delete --topic "$t" 2>/dev/null || true
done
sleep 3
docker compose run --rm -T kafka-init >/dev/null
docker compose --profile telemetry up -d middleware-sim stream-machine-state state-api
