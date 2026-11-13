"""Liệt kê topic của Kafka cluster thật + đọc vài message để kiểm tra."""
import sys
from confluent_kafka.admin import AdminClient, ConfigResource

BOOT = "192.168.179.176:29092"

admin = AdminClient({"bootstrap.servers": BOOT})
md = admin.list_topics(timeout=15)
print("=== CLUSTER ===")
print("brokers:", sorted(md.brokers.keys()))
print("=== TOPICS ===")
for t in sorted(md.topics):
    if t.startswith("__"):
        continue
    print(f"  {t:35s} partitions={len(md.topics[t].partitions)}")

print("\n=== CONFIG CUA TUNG TOPIC (compact?) ===")
for t in sorted(md.topics):
    if t.startswith("__"):
        continue
    try:
        res = ConfigResource(ConfigResource.Type.TOPIC, t)
        fut = admin.describe_configs([res])[res]
        cfg = fut.result(timeout=10)
        for k in ("cleanup.policy", "retention.ms", "max.message.bytes"):
            if k in cfg:
                print(f"  {t:35s} {k} = {cfg[k].value}")
    except Exception as e:
        print(f"  {t}: lỗi {e}")
