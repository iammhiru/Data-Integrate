#!/bin/bash
# Kiem tra trang thai 3 job Spark + Spark UI tren server.
set -uo pipefail
cd /home/dev/smart-factory
echo "=== containers ==="
docker compose -f docker-compose.spark-server.yml ps --format 'table {{.Name}}\t{{.Status}}'
echo
echo "=== spark UI ==="
for p in 4040 4041 4042; do
  echo -n "port $p: "
  curl -s "http://127.0.0.1:$p/api/v1/applications" 2>/dev/null | head -c 300
  echo
done
