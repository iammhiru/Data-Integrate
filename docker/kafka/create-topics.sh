#!/bin/bash
# Tao cac topic. Idempotent: --if-not-exists.
set -euo pipefail
BS=kafka:9092
K=/opt/kafka/bin/kafka-topics.sh
DAY=86400000

create() {  # name partitions retention_ms [--config k=v ...]
  local name=$1 parts=$2 ret=$3; shift 3
  $K --bootstrap-server $BS --create --if-not-exists --topic "$name" \
     --partitions "$parts" --replication-factor 1 --config retention.ms="$ret" "$@"
}

# realtime-metrics: dau vao cua dashboard (.NET) - giu de dashboard khoi dong duoc
create realtime-metrics  3 $((1 * DAY))
create dead-letter       1 $((7 * DAY))

# Contract cua middleware (IndustrialTelemetry.Middleware): 1 message = 1 tag doi gia tri
create industrial.telemetry 8 $((7 * DAY))
# Trang thai moi nhat moi (machineId|tagName) - compacted: Kafka giu it nhat ban cuoi cung cua moi key.
#   segment.ms 10 phut  -> segment dong som de log cleaner don duoc
#   min.cleanable.dirty.ratio 0.1 -> don khi >=10% log la ban cu
create machine-state 3 -1 \
  --config cleanup.policy=compact \
  --config segment.ms=600000 \
  --config min.cleanable.dirty.ratio=0.1 \
  --config delete.retention.ms=86400000

$K --bootstrap-server $BS --list
