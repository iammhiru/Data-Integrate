# -*- coding: utf-8 -*-
"""
Kiem tra phan boi partition cua Kafka cho 26 machineId.

Kafka gan partition bang: (murmur2(key) & 0x7FFFFFFF) % numPartitions
Key = machineId (UTF-8).

Usage:
    python tools/check_partitioning.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "metadata" / "catalog.json"

NUM_PARTITIONS = 8


def murmur2(data: bytes) -> int:
    """Murmur2 cua Kafka (org.apache.kafka.common.utils.Utils.murmur2)."""
    length = len(data)
    seed = 0x9747B28C
    m = 0x5BD1E995
    r = 24

    h = seed ^ length
    length4 = length // 4

    for i in range(length4):
        i4 = i * 4
        k = ((data[i4] & 0xFF) | ((data[i4 + 1] & 0xFF) << 8) |
             ((data[i4 + 2] & 0xFF) << 16) | ((data[i4 + 3] & 0xFF) << 24))
        k = (k * m) & 0xFFFFFFFF
        k ^= k >> r
        k = (k * m) & 0xFFFFFFFF
        h = (h * m) & 0xFFFFFFFF
        h ^= k

    extra = length % 4
    if extra >= 3:
        h ^= (data[(length & ~3) + 2] & 0xFF) << 16
    if extra >= 2:
        h ^= (data[(length & ~3) + 1] & 0xFF) << 8
    if extra >= 1:
        h ^= (data[length & ~3] & 0xFF)
        h = (h * m) & 0xFFFFFFFF

    h ^= h >> 13
    h = (h * m) & 0xFFFFFFFF
    h ^= h >> 15
    return h


def partition_of(key: str, num_partitions: int) -> int:
    return (murmur2(key.encode("utf-8")) & 0x7FFFFFFF) % num_partitions


def main() -> int:
    if not CATALOG.exists():
        print(f"Khong tim thay {CATALOG}")
        return 1

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    machines = [m["machineId"] for m in catalog["machines"]]

    for n in (4, 6, 8, 12, 16):
        buckets: dict[int, list[str]] = defaultdict(list)
        for mid in machines:
            buckets[partition_of(mid, n)].append(mid)
        sizes = [len(v) for v in buckets.values()]
        empty = sum(1 for v in buckets.values() if not v)
        print(f"\n=== {n} partition ===")
        print(f"  dung={len(buckets)}/{n}  min={min(sizes)}  max={max(sizes)}  "
              f"lech={max(sizes) - min(sizes)}  rong={empty}")
        for p in sorted(buckets):
            print(f"  P{p}: {len(buckets[p]):>2}  {', '.join(buckets[p])}")

    print(f"\n=== Baseline: {NUM_PARTITIONS} partition ===")
    buckets = defaultdict(list)
    for mid in machines:
        buckets[partition_of(mid, NUM_PARTITIONS)].append(mid)
    sizes = [len(v) for v in buckets.values()]
    ideal = len(machines) / NUM_PARTITIONS
    print(f"  may/partition: min={min(sizes)} max={max(sizes)} "
          f"ideal={ideal:.2f} max/ideal={max(sizes) / ideal:.2f}")
    print(f"  partition rong: {sum(1 for v in buckets.values() if not v)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
