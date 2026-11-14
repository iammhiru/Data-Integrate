#!/bin/bash
# Lap lich batch don gian: moi BATCH_INTERVAL_SEC chay batch_kpi.py --mode auto
#   (incremental + tu chay daily cho hom qua sau DAILY_AT gio dia phuong).
# Chay tay: docker compose run --rm batch-scheduler /opt/batch/submit.sh --mode backfill --from 2026-11-01 --to 2026-11-13
set -uo pipefail
INTERVAL=${BATCH_INTERVAL_SEC:-300}
echo "batch-scheduler: moi ${INTERVAL}s, daily luc ${DAILY_AT:-00:30} (${PLANT_TZ:-Asia/Ho_Chi_Minh})"
while true; do
  start=$(date +%s)
  /opt/batch/submit.sh --mode auto --daily-at "${DAILY_AT:-00:30}" || echo "batch that bai (thu lai o chu ky sau)"
  elapsed=$(( $(date +%s) - start ))
  sleep $(( INTERVAL > elapsed ? INTERVAL - elapsed : 5 ))
done
