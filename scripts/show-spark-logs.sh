#!/bin/bash
# Xem log 3 job Spark tren server (dung khi can theo doi nhanh).
# Upload: scp scripts\show-spark-logs.sh dev@192.168.179.176:/home/dev/smart-factory/
set -uo pipefail
cd /home/dev/smart-factory
for s in spark-raw-ingest spark-machine-state spark-batch-kpi; do
  echo "===== $s ====="
  docker logs "$s" 2>&1 | tail -"${1:-12}"
  echo
done
