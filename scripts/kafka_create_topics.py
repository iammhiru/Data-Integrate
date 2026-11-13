"""Tao topic `machine-state` (compacted) tren Kafka cluster that, dung config nhu docker/kafka/create-topics.sh."""
import sys
from confluent_kafka.admin import AdminClient, NewTopic, NewPartitions

BOOT = "192.168.179.176:29092"
TOPIC = "machine-state"

admin = AdminClient({"bootstrap.servers": BOOT})
md = admin.list_topics(timeout=15)

if TOPIC in md.topics:
    print(f"[OK] Topic '{TOPIC}' da ton tai (partitions={len(md.topics[TOPIC].partitions)})")
else:
    t = NewTopic(
        TOPIC,
        num_partitions=3,
        replication_factor=1,
        config={
            "cleanup.policy": "compact",
            "segment.ms": "600000",
            "min.cleanable.dirty.ratio": "0.1",
            "delete.retention.ms": "86400000",
        },
    )
    for name, fut in admin.create_topics([t]).items():
        try:
            fut.result(timeout=30)
            print(f"[OK] Da tao topic '{name}' (3 partitions, cleanup.policy=compact)")
        except Exception as e:
            print(f"[ERR] {name}: {e}")
            sys.exit(1)

# industrial.telemetry phai ton tai va du 8 partitions
if "industrial.telemetry" not in md.topics:
    print("[ERR] Thieu topic 'industrial.telemetry'")
    sys.exit(1)
print(f"[OK] Topic 'industrial.telemetry' partitions={len(md.topics['industrial.telemetry'].partitions)}")
