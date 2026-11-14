#!/bin/bash
# Chay backfill batch_kpi cho 1 ngay (verify du lieu THAT tu MinIO raw).
# Usage: bash run-backfill.sh 2026-11-11
set -uo pipefail
DAY="${1:-2026-11-11}"
cd /home/dev/smart-factory
docker exec spark-batch-kpi /opt/spark/bin/spark-submit \
  --conf spark.ui.port=4042 \
  --conf spark.app.name=batch-backfill \
  --conf spark.cores.max=2 \
  --conf spark.executor.memory=1g \
  --conf spark.driver.memory=1g \
  /opt/spark-apps/batch_kpi.py \
  --mode backfill \
  --from "$DAY" \
  --to "$DAY" \
  --bucket smart-factory \
  --pg-url jdbc:postgresql://192.168.179.176:5432/smart_factory \
  --pg-user sf_user \
  --pg-password sf_password \
  --tz Asia/Ho_Chi_Minh
