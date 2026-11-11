#!/usr/bin/env bash
# Kiem tra end-to-end: Kafka -> Spark Streaming -> MinIO -> Spark Batch -> PostgreSQL
#
#   ./scripts/smoke_test.sh            # dung du lieu test moi (RESET toan bo topic/bucket/bang metric)
#   MACHINES=50 SECONDS_=300 ./scripts/smoke_test.sh
#
# CANH BAO: script xoa du lieu trong Kafka topic, bucket MinIO va cac bang *_metric.
set -euo pipefail
cd "$(dirname "$0")/.."

MACHINES=${MACHINES:-10}
SECONDS_=${SECONDS_:-120}
set -a; source .env; set +a
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

dc()   { docker compose "$@"; }
s3()   { dc run --rm -T --entrypoint aws minio-init --endpoint-url http://minio:9000 s3 "$@" 2>/dev/null; }
psql() { dc exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"; }
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "0. Khoi dong stack"
dc up -d --quiet-pull >/dev/null 2>&1 || true
for svc in kafka minio postgres spark-master; do
  until [ "$(docker inspect -f '{{.State.Health.Status}}' "$svc")" = healthy ]; do sleep 2; done
done
dc ps --format 'table {{.Name}}\t{{.Status}}'

step "1. Reset du lieu test"
# streaming service dung chung topic/checkpoint -> dung lai truoc khi reset
dc --profile streaming stop stream-raw-ingest stream-realtime >/dev/null 2>&1 || true
dc run --rm --no-deps -T --entrypoint rm spark-master -rf /opt/spark-checkpoints/realtime >/dev/null 2>&1 || true
for t in machine-telemetry production-events quality-events; do
  dc exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --delete --topic "$t" 2>/dev/null || true
done
sleep 3
dc run --rm -T kafka-init >/dev/null
s3 rm "s3://$MINIO_BUCKET" --recursive --quiet || true
psql -q -c "TRUNCATE production_metric, quality_metric, data_quality_metric, machine_status_current, machine_metric_1m"

step "2. Sinh event va gui vao Kafka ($MACHINES may, $SECONDS_ giay)"
for pair in telemetry:machine-telemetry:1 production:production-events:0.2 quality:quality-events:0.2; do
  IFS=: read -r type topic rate <<<"$pair"
  python3 scripts/generate_test_events.py --type "$type" --machines "$MACHINES" --seconds "$SECONDS_" --rate "$rate" > "$TMP/$type.txt"
  dc exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:9092 --topic "$topic" \
     --property parse.key=true --property key.separator='|' < "$TMP/$type.txt"
  echo "  $topic: $(wc -l < "$TMP/$type.txt" | tr -d ' ') events"
done

step "3. Spark Streaming: Kafka -> MinIO (available-now)"
dc exec -T spark-master /opt/spark/bin/spark-submit /opt/spark-apps/kafka_to_minio.py --available-now 2>&1 \
  | grep -E '^batch|Error|Exception' || true
s3 ls "s3://$MINIO_BUCKET" --recursive | grep -v checkpoints | awk '{print $4}' \
  | sed -E 's#/part-[^/]*##' | grep -v _SUCCESS | sort | uniq -c | sed 's/^/  /'

step "4. Spark Batch: MinIO -> PostgreSQL"
dc exec -T spark-master /opt/spark/bin/spark-submit /opt/spark-apps/minio_to_postgres.py 2>&1 \
  | grep -E '^upsert|^skip|Error|Exception' || true

step "5. Ket qua trong PostgreSQL"
psql -c "SELECT event_type, total_events, valid_events, invalid_events, duplicate_events,
                missing_field_events, late_events, round(data_quality_rate::numeric, 2) AS dq_rate
         FROM data_quality_metric ORDER BY event_type, date, hour"

step "6. Doi chieu: tong san luong (Spark) vs tinh doc lap bang Python tu file input"
SPARK_TOTAL=$(psql -tA -c "SELECT COALESCE(sum(total_qty), 0) FROM production_metric")
REF_TOTAL=$(python3 - "$TMP/production.txt" <<'EOF'
import json, sys
seen, total = set(), 0
for line in open(sys.argv[1]):
    e = json.loads(line.split("|", 1)[1])
    if "eventId" not in e or e["timestamp"] == "not-a-timestamp" or e["eventId"] in seen:
        continue
    seen.add(e["eventId"])
    p = e["payload"]
    if p.get("productId") is not None and p.get("quantity") is not None:
        total += p["quantity"]
print(total)
EOF
)
echo "  Spark = $SPARK_TOTAL | Reference = $REF_TOTAL"
if [ "$SPARK_TOTAL" = "$REF_TOTAL" ]; then echo "  PASS"; else echo "  FAIL"; exit 1; fi
echo
echo "Streaming service da bi dung. Chay lai: docker compose --profile streaming up -d"
