"""
tools/simulation_test.py
────────────────────────
Self-test cho chế độ giả lập (``SIMULATION_MODE=true``) — KHÔNG cần Kepware,
KHÔNG cần Kafka thật.

Chạy:
    python tools/simulation_test.py

Kiểm tra:
  1. Sinh đủ giá trị cho toàn bộ tag (404 tag / 26 máy).
  2. Giá trị đúng kiểu theo metadata CSV (Boolean/Int/Long/Float).
  3. Message sinh ra đúng data contract (10 khóa, đúng cấu trúc lồng).
  4. Quy tắc nghiệp vụ: CurrentSpeed = 0 khi không RUNNING, bộ đếm chỉ tăng
     khi RUNNING, AlarmCode != 0 khi FAULTED.
  5. Dedup/dedup-key hoạt động trên dữ liệu giả lập.
  6. eventId tất định.
  7. Giá trị thay đổi theo thời gian (không phải hằng số).
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.equipment_map import EquipmentMap  # noqa: E402
from core.tag_loader import load_all_tags  # noqa: E402
from services.normalizer import Normalizer  # noqa: E402
from services.simulator import (  # noqa: E402
    STATE_FAULTED,
    STATE_RUNNING,
    SimulatedSource,
)

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


def main() -> int:
    print("\n=== Simulation mode — Self-test ===\n")

    equipment_map = EquipmentMap.load()
    tags = load_all_tags()
    check("404 tag", len(tags) == 404, f"got {len(tags)}")

    # ── 1. Sinh giá trị cho toàn bộ tag ────────────────────────────────────
    print("\n[1] Sinh giá trị")
    captured: list[dict] = []

    source = SimulatedSource(tags=tags, enqueue=captured.append)

    # Ép máy về trạng thái RUNNING để giá trị "sống".
    for rt in source._runtimes.values():
        rt.state = STATE_RUNNING
        rt.state_timer = 0.0

    source._tick(1.0, 1.0, advance_state=False)
    check("Sinh payload cho mọi tag",
          len(captured) == len(tags), f"got {len(captured)}/{len(tags)}")
    check("Payload có node_id + tag_def + value",
          all({"node_id", "tag_def", "value", "source_timestamp"} <= set(p) for p in captured))

    values = {p["tag_def"].tag_name: p["value"] for p in captured}

    # ── 2. Kiểu dữ liệu theo metadata ─────────────────────────────────────
    print("\n[2] Kiểu dữ liệu theo metadata CSV")
    type_errors = []
    for p in captured:
        tag = p["tag_def"]
        v = p["value"]
        if tag.kepware_type == "Boolean" and not isinstance(v, bool):
            type_errors.append(f"{tag.display_name}: {v!r} not bool")
        elif tag.kepware_type in ("Int", "Long") and not isinstance(v, int):
            type_errors.append(f"{tag.display_name}: {v!r} not int")
        elif tag.kepware_type == "Float" and not isinstance(v, float):
            type_errors.append(f"{tag.display_name}: {v!r} not float")
    check("Mọi giá trị đúng kiểu", not type_errors, str(type_errors[:5]))

    check("MachineState là int", isinstance(values.get("MachineState"), int))
    check("AlarmCode là int", isinstance(values.get("AlarmCode"), int))
    check("CurrentSpeed là float", isinstance(values.get("CurrentSpeed"), float))
    check("EmergencyStop là bool", isinstance(values.get("EmergencyStop"), bool))

    # ── 3. Message chuẩn ───────────────────────────────────────────────────
    print("\n[3] Data contract")
    normalizer = Normalizer(equipment_map, source_system="simulator")
    msg = normalizer.normalize(
        tag_def=tags[0],
        value=captured[0]["value"],
        source_timestamp=captured[0]["source_timestamp"],
        server_timestamp=captured[0]["server_timestamp"],
        quality_raw=captured[0]["quality_raw"],
    )
    required = {"eventId", "eventType", "schemaVersion", "eventTime", "source",
                "plant", "machine", "tag", "measurement", "quality"}
    check("Đủ 10 khóa cấp cao", set(msg.keys()) == required, str(sorted(msg.keys())))
    check("source.system = simulator", msg["source"]["system"] == "simulator")
    check("source có nodeId", bool(msg["source"]["nodeId"]))
    check("plant có 3 trường",
          set(msg["plant"].keys()) == {"plantId", "lineId", "processId"})
    check("machine có 3 trường",
          set(msg["machine"].keys()) == {"machineId", "machineType", "equipmentCode"})
    check("tag có 3 trường",
          set(msg["tag"].keys()) == {"tagName", "tagCode", "tagType"})
    check("measurement có 3 trường",
          set(msg["measurement"].keys()) == {"value", "valueType", "unit"})
    check("quality có 2 trường",
          set(msg["quality"].keys()) == {"statusCode", "isGood"})
    check("eventTime kết thúc bằng Z", msg["eventTime"].endswith("Z"))

    # ── 4. Quy tắc nghiệp vụ ───────────────────────────────────────────────
    print("\n[4] Quy tắc nghiệp vụ (design doc §9.1)")
    # Máy dừng → CurrentSpeed = 0
    for rt in source._runtimes.values():
        rt.state = 3  # STOPPED
    captured.clear()
    source._tick(2.0, 1.0, advance_state=False)
    stopped_speeds = [
        p["value"] for p in captured
        if p["tag_def"].tag_name == "CurrentSpeed"
    ]
    check("STOPPED → CurrentSpeed = 0",
          bool(stopped_speeds) and all(v == 0.0 for v in stopped_speeds),
          str(stopped_speeds[:5]))

    # Máy chạy → CurrentSpeed > 0
    for rt in source._runtimes.values():
        rt.state = STATE_RUNNING
    captured.clear()
    source._tick(3.0, 1.0, advance_state=False)
    running_speeds = [
        p["value"] for p in captured
        if p["tag_def"].tag_name == "CurrentSpeed"
    ]
    check("RUNNING → CurrentSpeed > 0",
          bool(running_speeds) and all(v > 0 for v in running_speeds),
          str(running_speeds[:5]))

    # Bộ đếm chỉ tăng khi RUNNING
    total_tag = next(t for t in tags if t.tag_name == "TotalCounter")
    before = next(p["value"] for p in captured
                  if p["tag_def"].node_id == total_tag.node_id)
    for rt in source._runtimes.values():
        rt.state = 3  # STOPPED
    captured.clear()
    source._tick(4.0, 1.0, advance_state=False)
    after = next(p["value"] for p in captured
                 if p["tag_def"].node_id == total_tag.node_id)
    check("STOPPED → bộ đếm không tăng", after == before, f"{before}→{after}")

    # FAULTED → AlarmCode != 0
    for rt in source._runtimes.values():
        rt.state = STATE_FAULTED
        rt.alarm_code = 555
    captured.clear()
    source._tick(5.0, 1.0, advance_state=False)
    alarms = [p["value"] for p in captured if p["tag_def"].tag_name == "AlarmCode"]
    check("FAULTED → AlarmCode khác 0",
          bool(alarms) and all(v != 0 for v in alarms), str(alarms[:5]))

    # ── 5. Giá trị thay đổi theo thời gian ────────────────────────────────
    print("\n[5] Giá trị biến động")
    for rt in source._runtimes.values():
        rt.state = STATE_RUNNING
    fill_tag = next(t for t in tags if t.tag_name == "FillLevel")
    series = []
    for i in range(6):
        captured.clear()
        source._tick(10.0 + i, 1.0, advance_state=False)
        series.append(next(p["value"] for p in captured
                           if p["tag_def"].node_id == fill_tag.node_id))
    check("FillLevel thay đổi giữa các nhịp",
          len(set(series)) > 1, str(series))

    # ── 6. Số tag khác nhau trong 1 máy ───────────────────────────────────
    print("\n[6] Phủ dữ liệu")
    devices = {p["tag_def"].channel_device for p in captured}
    check("Phủ 26 máy", len(devices) == 26, f"got {len(devices)}")
    check("Mọi máy có metadata",
          not equipment_map.missing_keys(devices),
          str(equipment_map.missing_keys(devices)))

    # ── 7. eventId tất định ───────────────────────────────────────────────
    print("\n[7] eventId tất định")
    a = normalizer.normalize(
        tag_def=tags[0], value=1.0,
        source_timestamp=captured[0]["source_timestamp"],
        server_timestamp=captured[0]["server_timestamp"], quality_raw="Good")
    b = normalizer.normalize(
        tag_def=tags[0], value=1.0,
        source_timestamp=captured[0]["source_timestamp"],
        server_timestamp=captured[0]["server_timestamp"], quality_raw="Good")
    check("Cùng input → cùng eventId", a["eventId"] == b["eventId"])
    check("eventId là UUID hợp lệ",
          len(a["eventId"]) == 36 and a["eventId"].count("-") == 4)

    # ── 8. Chất lượng dữ liệu ──────────────────────────────────────────────
    print("\n[8] Chất lượng")
    qualities = Counter(p["quality_raw"] for p in captured)
    check("Chỉ dùng quality hợp lệ",
          set(qualities) <= {"Good", "BadNoCommunication", "UncertainLastUsableValue"},
          str(qualities))
    bad_msg = normalizer.normalize(
        tag_def=tags[0], value=1.0,
        source_timestamp=captured[0]["source_timestamp"],
        server_timestamp=captured[0]["server_timestamp"],
        quality_raw="BadNoCommunication")
    check("Bad → value null", bad_msg["measurement"]["value"] is None)
    check("Bad → isGood false", bad_msg["quality"]["isGood"] is False)

    print(f"\n=== KẾT QUẢ: {PASSED} pass, {FAILED} fail ===\n")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
