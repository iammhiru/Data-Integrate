"""
tools/integration_test.py
────────────────────────
Integration test end-to-end KHÔNG cần Kepware/Kafka thật.

Mô phỏng: callback OPC UA → value_queue → ValueWorker → Normalizer →
fake Kafka producer. Kiểm tra:
  - Message đúng contract (10 khóa, đúng giá trị).
  - Dedup: gửi lại cùng giá trị → không phát message thứ 2.
  - Baseline replay: giá trị đầu tiên sau subscribe bị loại.
  - Cổng STABLE: ở DEGRADED thì không gửi.
  - Key = machineId.
  - Bad → value null.

Cách chạy (từ thư mục IndustrialTelemetry.Middleware/):
    python tools/integration_test.py
"""

from __future__ import annotations

import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.equipment_map import EquipmentMap  # noqa: E402
from core.state_machine import ConnectionState, OpcConnectionState  # noqa: E402
from core.subscription import SubscriptionRegistry  # noqa: E402
from core.tag_loader import load_all_tags  # noqa: E402
from services.normalizer import Normalizer  # noqa: E402
from services.value_worker import ValueWorker  # noqa: E402

PASSED = 0
FAILED = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label} {detail}")


class FakePublisher:
    """Giả lập Kafka producer — thu message và ghi lại key."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.lock = threading.Lock()

    def send(self, message: dict) -> bool:
        with self.lock:
            self.sent.append(
                (message.get("machine", {}).get("machineId", ""), message)
            )
        return True

    @property
    def messages(self) -> list[dict]:
        with self.lock:
            return [m for _, m in self.sent]


def drain(worker: ValueWorker, q: queue.Queue, timeout: float = 2.0) -> None:
    """Chờ worker xử lý hết queue."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if q.empty():
            time.sleep(0.05)
            if q.empty():
                return
        time.sleep(0.02)


def main() -> int:
    print("\n=== Integration test (mock) ===\n")

    equipment_map = EquipmentMap.load()
    tags = load_all_tags()
    registry = SubscriptionRegistry()
    registry.register_tags(tags)

    normalizer = Normalizer(equipment_map)
    publisher = FakePublisher()
    connection_state = ConnectionState()
    q: queue.Queue = queue.Queue(maxsize=1000)

    worker = ValueWorker(
        value_queue=q,
        registry=registry,
        normalizer=normalizer,
        publisher=publisher,
        connection_state=connection_state,
    )
    worker.start()

    filler = next(t for t in tags if t.device == "L01_FILLER_01")
    fill_level = next(t for t in tags if t.device == "L01_FILLER_01"
                      and t.tag_name == "FillLevel")
    now = datetime.now(tz=timezone.utc)

    def payload(value, quality="Good", ts=None):
        return {
            "node_id": fill_level.node_id,
            "tag_def": fill_level,
            "value": value,
            "raw_value": value,
            "source_timestamp": ts or now,
            "server_timestamp": ts or now,
            "quality_raw": quality,
            "force": False,
        }

    # ── 1. Cổng STABLE ─────────────────────────────────────────────────────
    print("[1] Cổng trạng thái")
    connection_state.set_state(OpcConnectionState.DEGRADED)
    connection_state.set_active(True)
    worker.enqueue(payload(87.5))
    drain(worker, q)
    check("DEGRADED → không gửi", len(publisher.sent) == 0, f"sent={len(publisher.sent)}")

    connection_state.set_state(OpcConnectionState.STABLE)
    worker.enqueue(payload(87.5))
    drain(worker, q)
    check("STABLE → gửi", len(publisher.sent) == 1, f"sent={len(publisher.sent)}")

    # ── 2. Nội dung message ────────────────────────────────────────────────
    print("\n[2] Nội dung message")
    msg = publisher.messages[0]
    check("Đủ 10 khóa cấp cao",
          set(msg.keys()) == {"eventId", "eventType", "schemaVersion", "eventTime",
                              "source", "plant", "machine", "tag", "measurement",
                              "quality"},
          str(sorted(msg.keys())))
    check("eventType đúng", msg["eventType"] == "machine.telemetry")
    check("machineId đúng", msg["machine"]["machineId"] == "L01_FILLER_01")
    check("source.device == machineId",
          msg["source"]["device"] == msg["machine"]["machineId"])
    check("tagCode đúng", msg["tag"]["tagCode"] == fill_level.tag_code)
    check("value đúng", msg["measurement"]["value"] == 87.5)
    check("valueType đúng", msg["measurement"]["valueType"] == "Float")
    check("unit đúng", msg["measurement"]["unit"] == "%")
    check("quality Good", msg["quality"] == {"statusCode": "Good", "isGood": True})
    check("eventTime ISO UTC Z",
          msg["eventTime"].endswith("Z") and "T" in msg["eventTime"])

    # ── 3. Key = machineId ─────────────────────────────────────────────────
    print("\n[3] Kafka key")
    key, _ = publisher.sent[0]
    check("key == machineId", key == "L01_FILLER_01", f"got {key}")

    # ── 4. Dedup ───────────────────────────────────────────────────────────
    print("\n[4] Dedup (change-detection)")
    before = len(publisher.sent)
    worker.enqueue(payload(87.5, ts=datetime.now(tz=timezone.utc)))
    drain(worker, q)
    check("Giá trị không đổi → không gửi lại",
          len(publisher.sent) == before, f"sent {before}→{len(publisher.sent)}")

    worker.enqueue(payload(90.0, ts=datetime.now(tz=timezone.utc)))
    drain(worker, q)
    check("Giá trị đổi → gửi", len(publisher.sent) == before + 1)

    # ── 5. Baseline replay ─────────────────────────────────────────────────
    print("\n[5] Baseline replay")
    from core.dedup import build_dedup_key
    from utils.time_utils import to_epoch_seconds

    other_tag = next(t for t in tags if t.device == "L01_FILLER_01"
                     and t.tag_name == "CurrentSpeed")
    ts = datetime.now(tz=timezone.utc)
    key_b = build_dedup_key(50.0, to_epoch_seconds(ts))
    registry.baseline.capture(other_tag.node_id, key_b)

    before = len(publisher.sent)
    worker.enqueue({
        "node_id": other_tag.node_id,
        "tag_def": other_tag,
        "value": 50.0,
        "raw_value": 50.0,
        "source_timestamp": ts,
        "server_timestamp": ts,
        "quality_raw": "Good",
        "force": False,
    })
    drain(worker, q)
    check("Baseline replay bị loại", len(publisher.sent) == before,
          f"sent {before}→{len(publisher.sent)}")

    # ── 6. Chất lượng Bad ──────────────────────────────────────────────────
    print("\n[6] Chất lượng dữ liệu")
    before = len(publisher.sent)
    worker.enqueue(payload(0.0, quality="BadNoCommunication",
                           ts=datetime.now(tz=timezone.utc)))
    drain(worker, q)
    check("Bad → vẫn gửi message", len(publisher.sent) == before + 1)
    bad_msg = publisher.messages[-1]
    check("Bad → value null", bad_msg["measurement"]["value"] is None)
    check("Bad → isGood false", bad_msg["quality"]["isGood"] is False)
    check("Bad → statusCode Bad", bad_msg["quality"]["statusCode"] == "Bad")

    # ── 7. Uncertain ───────────────────────────────────────────────────────
    before = len(publisher.sent)
    worker.enqueue(payload(77.0, quality="UncertainLastUsableValue",
                           ts=datetime.now(tz=timezone.utc)))
    drain(worker, q)
    unc_msg = publisher.messages[-1]
    check("Uncertain → giữ giá trị", unc_msg["measurement"]["value"] == 77.0)
    check("Uncertain → isGood false", unc_msg["quality"]["isGood"] is False)

    # ── 8. Ép kiểu theo metadata ──────────────────────────────────────────
    print("\n[7] Ép kiểu theo metadata CSV")
    from core.value_types import coerce_value

    emergency = next(t for t in tags if t.device == "L01_FILLER_01"
                     and t.tag_name == "EmergencyStop")
    check("EmergencyStop là Boolean", emergency.value_type == "Boolean")
    check("coerce True", coerce_value(True, emergency.kepware_type) is True)

    counter = next(t for t in tags if t.tag_code.startswith("FILL.L01.TOTALCOUNTER"))
    check("Counter là Int64 (Long)", counter.value_type == "Int64",
          f"got {counter.value_type}")

    # ── 9. Thống kê worker ─────────────────────────────────────────────────
    print("\n[8] Thống kê worker")
    stats = worker.stats()
    check("Đã xử lý >= 4 message", stats["processed"] >= 4, str(stats))
    check("Có bỏ qua do dedup", stats["skipped_dedup"] >= 1, str(stats))
    check("Có bỏ qua do state", stats["skipped_state"] >= 1, str(stats))
    check("Có bỏ qua baseline", stats["skipped_baseline"] >= 1, str(stats))

    print(f"\n=== KẾT QUẢ: {PASSED} pass, {FAILED} fail ===\n")
    worker.stop(timeout=5)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
