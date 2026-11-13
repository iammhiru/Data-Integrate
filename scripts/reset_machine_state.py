"""
RESET luong trang thai may tren may Windows (khong dung Docker).

Xoa sach de pipeline bat dau tu dau:
  · topic `machine-state` (trang thai compacted) — xoa va tao lai
  · checkpoint cua Spark Structured Streaming (offset + state store)
  · KHONG xoa `industrial.telemetry` (de giu lich su telemetry)

CANH BAO: xoa toan bo trang thai may hien tai tren UI. Ve lai UI sau khi chay.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\reset_machine_state.py
    .\\.venv\\Scripts\\python.exe scripts\\reset_machine_state.py --keep-topic
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from confluent_kafka.admin import AdminClient, NewTopic

ROOT = Path(__file__).resolve().parents[1]
BOOT = "192.168.179.176:29092"
TOPIC = "machine-state"
CHECKPOINT = ROOT / ".spark-checkpoints" / "machine-state"

# Config phai khop voi scripts/kafka_create_topics.py
TOPIC_CONFIG = {
    "cleanup.policy": "compact",
    "segment.ms": "600000",
    "min.cleanable.dirty.ratio": "0.1",
    "delete.retention.ms": "86400000",
}


def delete_topic(admin: AdminClient, topic: str) -> bool:
    """Xoa topic. Tra True neu thanh cong (hoac topic khong ton tai)."""
    md = admin.list_topics(timeout=15)
    if topic not in md.topics:
        print(f"[OK] Topic '{topic}' khong ton tai — bo qua")
        return True
    for name, fut in admin.delete_topics([topic], operation_timeout=30).items():
        try:
            fut.result(timeout=60)
            print(f"[OK] Da xoa topic '{name}'")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[X] Xoa topic '{name}' that bai: {exc}")
            return False


def create_topic(admin: AdminClient, topic: str) -> bool:
    """Tao topic moi (compacted, 3 partitions)."""
    t = NewTopic(topic, num_partitions=3, replication_factor=1, config=TOPIC_CONFIG)
    for name, fut in admin.create_topics([t]).items():
        try:
            fut.result(timeout=60)
            print(f"[OK] Da tao topic '{name}' (3 partitions, cleanup.policy=compact)")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[X] Tao topic '{name}' that bai: {exc}")
            return False


def clear_checkpoint() -> None:
    """Xoa checkpoint Spark de job doc tu dau (starting-offsets = latest)."""
    if CHECKPOINT.exists():
        shutil.rmtree(CHECKPOINT, ignore_errors=True)
        print(f"[OK] Da xoa checkpoint: {CHECKPOINT}")
    else:
        print(f"[--] Khong co checkpoint tai {CHECKPOINT}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-topic", action="store_true",
                    help="Giu nguyen topic, chi xoa checkpoint Spark")
    ap.add_argument("--keep-checkpoint", action="store_true",
                    help="Giu nguyen checkpoint Spark")
    args = ap.parse_args()

    print(f"[*] Kafka: {BOOT}")
    admin = AdminClient({"bootstrap.servers": BOOT})

    if args.keep_checkpoint:
        print("[--] Giu checkpoint (theo yeu cau)")
    else:
        clear_checkpoint()

    if args.keep_topic:
        print("[--] Giu topic (theo yeu cau)")
    else:
        if not delete_topic(admin, TOPIC):
            return 1
        # Kafka can mot chút thoi gian de topic bi xoa hoan toan truoc khi tao lai.
        time.sleep(5)
        if not create_topic(admin, TOPIC):
            return 1

    print()
    print("[OK] Reset xong.")
    print("     Bay gi chay lai pipeline:")
    print("       .\\scripts\\run-all.ps1 -RealKepware")
    print("     (dung -RealKepware de middleware doc Kepware that; bo switch de mo simulation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
