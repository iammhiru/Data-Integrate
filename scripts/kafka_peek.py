"""Kiem tra offset + doc message cuoi tren topic."""
import sys
from confluent_kafka import Consumer, TopicPartition, OFFSET_BEGINNING

BOOT = "192.168.179.176:29092"

topic = sys.argv[1] if len(sys.argv) > 1 else "industrial.telemetry"

c = Consumer({"bootstrap.servers": BOOT, "group.id": f"probe-{topic}", "enable.auto.commit": False})
md = c.list_topics(topic, timeout=15).topics.get(topic)
if md is None:
    print(f"topic {topic} khong ton tai")
    sys.exit(1)

parts = sorted(md.partitions)
print(f"=== {topic} ({len(parts)} partitions) ===")
total = 0
for p in parts:
    lo, hi = c.get_watermark_offsets(TopicPartition(topic, p), timeout=10)
    total += hi - lo
    print(f"  p{p}: low={lo} high={hi} msgs={hi-lo}")
print(f"  TOTAL messages = {total}")

# Doc 2 message cuoi o partition dau tien co du lieu
for p in parts:
    lo, hi = c.get_watermark_offsets(TopicPartition(topic, p), timeout=10)
    if hi <= lo:
        continue
    c.assign([TopicPartition(topic, p, max(lo, hi - 2))])
    n = 0
    while n < 2:
        m = c.poll(3.0)
        if m is None:
            break
        if m.error():
            continue
        print(f"  --- p{p} off={m.offset()} key={m.key()} ---")
        print(f"      {m.value()[:400].decode('utf-8', 'replace')}")
        n += 1
    break
c.close()
