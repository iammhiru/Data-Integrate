#!/bin/bash
# Tao cac topic theo docs/architecture.txt (muc 4.1). Idempotent: --if-not-exists.
set -euo pipefail
BS=kafka:9092
K=/opt/kafka/bin/kafka-topics.sh
DAY=86400000

create() {  # name partitions retention_ms
  $K --bootstrap-server $BS --create --if-not-exists --topic "$1" \
     --partitions "$2" --replication-factor 1 --config retention.ms="$3"
}

create machine-telemetry 6 $((3 * DAY))
create production-events 3 $((7 * DAY))
create quality-events    3 $((7 * DAY))
create realtime-metrics  3 $((1 * DAY))
create dead-letter       1 $((7 * DAY))

$K --bootstrap-server $BS --list
