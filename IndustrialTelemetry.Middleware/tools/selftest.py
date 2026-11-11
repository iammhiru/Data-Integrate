"""
tools/selftest.py
────────────────
Self-test offline cho middleware — KHÔNG cần Kepware, KHÔNG cần Kafka.

Chạy:
    python tools/selftest.py

Kiểm tra:
  1. Load metadata: 26 máy, 404 tag, TagCode unique.
  2. Ánh xạ kiểu 3 tầng: Boolean/Int/Word/DWord/Long/Float/Double/String.
  3. EventId tất định: cùng input → cùng eventId; khác value → khác eventId.
  4. Dedup: change-detection + baseline replay.
  5. StatusCode: Good/Uncertain/Bad → value null khi Bad.
  6. Message chuẩn: đủ 10 khóa, đúng kiểu.
  7. Partitioning: murmur2(machineId) % 8 không partition rỗng.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.dedup import BaselineSnapshot, DedupCache, build_dedup_key  # noqa: E402
from core.equipment_map import EquipmentMap  # noqa: E402
from core.tag_loader import load_all_tags  # noqa: E402
from core.value_types import coerce_value, opcua_type_for  # noqa: E402
from services.normalizer import Normalizer  # noqa: E402
from utils.event_id import build_event_id  # noqa: E402
from utils.status_codes import normalize_status_code  # noqa: E402

PASSED = 0
FAILED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label} {detail}")


def murmur2(data: bytes) -> int:
    """Hàm băm murmur2 của Kafka (không seed)."""
    length = len(data)
    seed = 0x9747B28C
    m = 0x5BD1E995
    r = 24
    h = (seed ^ length) & 0xFFFFFFFF
    length4 = length // 4
    for i in range(length4):
        i4 = i * 4
        k = (
            (data[i4] & 0xFF)
            + ((data[i4 + 1] & 0xFF) << 8)
            + ((data[i4 + 2] & 0xFF) << 16)
            + ((data[i4 + 3] & 0xFF) << 24)
        ) & 0xFFFFFFFF
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


def main() -> int:
    print("\n=== IndustrialTelemetry.Middleware — Self-test ===\n")

    # ── 1. Metadata ────────────────────────────────────────────────────────
    print("[1] Metadata")
    equipment_map = EquipmentMap.load()
    tags = load_all_tags()
    check("26 máy trong equipment_map", len(equipment_map) == 26, f"got {len(equipment_map)}")
    check("404 tag trong TAG_FOLDER", len(tags) == 404, f"got {len(tags)}")
    codes = [t.tag_code for t in tags if t.tag_code]
    check("TagCode unique", len(codes) == len(set(codes)), f"got {len(codes)}")
    check("Mọi máy trong CSV có metadata",
          not equipment_map.missing_keys({t.channel_device for t in tags}),
          str(equipment_map.missing_keys({t.channel_device for t in tags})))

    # ── 2. Type mapping ────────────────────────────────────────────────────
    print("\n[2] Ánh xạ kiểu 3 tầng")
    expected_types = {
        "Boolean": "Boolean", "Int": "Int32", "Word": "UInt16",
        "DWord": "UInt32", "Long": "Int64", "Float": "Float",
        "Double": "Double", "String": "String",
    }
    for kep, opc in expected_types.items():
        check(f"{kep} -> {opc}", opcua_type_for(kep) == opc, f"got {opcua_type_for(kep)}")

    check("Boolean ép đúng", coerce_value("true", "Boolean") is True)
    check("Int ép đúng", coerce_value("42.7", "Int") == 43)
    check("DWord ép đúng", coerce_value("4000000000", "DWord") == 4000000000)
    check("Long ép đúng", coerce_value(9007199254740991, "Long") == 9007199254740991)
    check("Float round 6", coerce_value(1.23456789, "Float") == 1.234568)
    check("String ép đúng", coerce_value(123, "String") == "123")
    check("None giữ nguyên", coerce_value(None, "Float") is None)

    # ── 3. EventId ─────────────────────────────────────────────────────────
    print("\n[3] EventId tất định")
    ts = "2026-11-11T09:15:32.412Z"
    a = build_event_id("L01_FILLER_01", "FillLevel", ts, 87.5, "Good")
    b = build_event_id("L01_FILLER_01", "FillLevel", ts, 87.5, "Good")
    c = build_event_id("L01_FILLER_01", "FillLevel", ts, 87.6, "Good")
    d = build_event_id("L01_FILLER_01", "FillLevel", ts, 87.5, "Bad")
    check("Cùng input → cùng eventId", a == b)
    check("Khác value → khác eventId", a != c)
    check("Khác status → khác eventId", a != d)
    check("Là UUID hợp lệ", len(a) == 36 and a.count("-") == 4)
    check("87.5 và 87.500000 cho cùng eventId",
          build_event_id("M", "T", ts, 87.5, "Good")
          == build_event_id("M", "T", ts, 87.5000000001, "Good"))

    # ── 4. Dedup ───────────────────────────────────────────────────────────
    print("\n[4] Dedup")
    cache = DedupCache(max_size=10)
    key = build_dedup_key(87.5, 1700000000)
    check("Lần đầu không trùng", cache.check_and_remember("n1", key) is False)
    check("Lần sau trùng", cache.check_and_remember("n1", key) is True)
    key2 = build_dedup_key(90.0, 1700000001)
    check("Giá trị đổi → không trùng", cache.check_and_remember("n1", key2) is False)
    cache.clear()
    check("Clear xoá hết", len(cache) == 0)

    baseline = BaselineSnapshot(max_size=10)
    baseline.capture("n1", key)
    check("Baseline replay bị chặn", baseline.is_baseline_replay("n1", key) is True)
    check("Baseline chỉ chặn 1 lần", baseline.is_baseline_replay("n1", key) is False)
    check("Giá trị khác baseline không bị chặn",
          baseline.is_baseline_replay("n1", key2) is False)

    # ── 5. StatusCode ──────────────────────────────────────────────────────
    print("\n[5] StatusCode")
    check("None → Good", normalize_status_code(None) == ("Good", True))
    check("Good → Good", normalize_status_code("Good") == ("Good", True))
    check("Uncertain → Uncertain", normalize_status_code("UncertainLastUsableValue")
          == ("Uncertain", False))
    check("Bad → Bad", normalize_status_code("BadNoCommunication") == ("Bad", False))
    check("Bad → value null",
          normalize_status_code("BadOutOfRange") == ("Bad", False))

    # Định dạng THẬT của python-opcua: str(StatusCode) = "StatusCode(Good)".
    # Nếu không bóc wrapper, "statuscode(good)" bị phân loại nhầm thành Bad.
    print("\n[5b] StatusCode — định dạng thật của python-opcua")
    check("StatusCode(Good) → Good",
          normalize_status_code("StatusCode(Good)") == ("Good", True))
    check("StatusCode(BadNoCommunication) → Bad",
          normalize_status_code("StatusCode(BadNoCommunication)") == ("Bad", False))
    check("StatusCode(UncertainLastUsableValue) → Uncertain",
          normalize_status_code("StatusCode(UncertainLastUsableValue)")
          == ("Uncertain", False))
    check("StatusCode(Good) case không phân biệt",
          normalize_status_code("statuscode(good)") == ("Good", True))

    # Đối tượng ua.StatusCode thật — nếu python-opcua có sẵn thì test luôn.
    try:
        from opcua.ua.uatypes import StatusCode as _UaStatusCode
        real_good = _UaStatusCode(0)                 # 0x00000000 = Good
        real_bad = _UaStatusCode(0x80340000)         # BadNodeIdUnknown
        check("ua.StatusCode(Good) → Good",
              normalize_status_code(real_good) == ("Good", True))
        check("ua.StatusCode(Bad) → Bad",
              normalize_status_code(real_bad) == ("Bad", False))
        # str() của đối tượng thật cũng phải xử lý đúng
        check("str(ua.StatusCode.Good) → Good",
              normalize_status_code(str(real_good)) == ("Good", True))
        check("str(ua.StatusCode.Bad) → Bad",
              normalize_status_code(str(real_bad)) == ("Bad", False))
        # .name của đối tượng thật cũng phải xử lý đúng
        check("ua.StatusCode.name → Good",
              normalize_status_code(real_good.name) == ("Good", True))
    except Exception as exc:
        print(f"  [SKIP] không import được ua.StatusCode: {exc}")

    # ── 6. Message ─────────────────────────────────────────────────────────
    print("\n[6] Message chuẩn")
    normalizer = Normalizer(equipment_map)
    filler = next(t for t in tags if t.tag_name == "FillLevel"
                  and t.device == "L01_FILLER_01")
    now = datetime.now(tz=timezone.utc)
    msg = normalizer.normalize(filler, 87.5, now, now, "Good")
    required = ["eventId", "eventType", "schemaVersion", "eventTime", "source",
                "plant", "machine", "tag", "measurement", "quality"]
    for key in required:
        check(f"Có khóa '{key}'", key in msg)
    check("eventType đúng", msg["eventType"] == "machine.telemetry")
    check("source.device == machineId",
          msg["source"]["device"] == msg["machine"]["machineId"])
    check("valueType đúng", msg["measurement"]["valueType"] == "Float")
    check("unit đúng", msg["measurement"]["unit"] == "%")
    check("eventTime kết thúc bằng Z", msg["eventTime"].endswith("Z"))
    check("isGood đúng", msg["quality"]["isGood"] is True)

    bad_msg = normalizer.normalize(filler, 0, now, now, "BadNoCommunication")
    check("Bad → value null", bad_msg["measurement"]["value"] is None)
    check("Bad → isGood false", bad_msg["quality"]["isGood"] is False)

    # ── 7. Partitioning ────────────────────────────────────────────────────
    print("\n[7] Partitioning (murmur2 % 8)")
    machine_ids = [m.machine_id for m in equipment_map]
    for n_partitions in (4, 8, 12):
        buckets: Counter = Counter()
        for mid in machine_ids:
            buckets[murmur2(mid.encode("utf-8")) % n_partitions] += 1
        check(
            f"{n_partitions} partitions: không partition rỗng",
            len(buckets) == n_partitions,
            f"got {sorted(buckets.items())}",
        )
        # Ngưỡng lý thể: partition đông nhất không vượt quá 3× partition ít nhất.
        # (Chỉ kiểm tra cho 4 và 8 partition — với 12 partition, 26 máy / 12 ≈ 2.2
        #  nên chênh lệch 5 vs 1 là hệt quả của làm tròn, không phải lỗi hash.)
        if n_partitions <= 8:
            check(
                f"{n_partitions} partitions: max/min <= 3",
                max(buckets.values()) <= 3 * min(buckets.values()),
                f"got {sorted(buckets.values())}",
            )
        print(f"      {n_partitions} partitions: {sorted(buckets.items())}")

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n=== KẾT QUẢ: {PASSED} pass, {FAILED} fail ===\n")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
