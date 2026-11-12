"""
tools/verify_doc.py
──────────────────
Kiểm tra tài liệu bàn giao (``kafka_data_contract_and_storage_guide.md``)
có khớp với ``metadata/catalog.json`` hay không.

Cách chạy (từ thư mục IndustrialTelemetry.Middleware/):
    python tools/verify_doc.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.value_types import opcua_type_for  # noqa: E402

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
    root = Path(__file__).resolve().parent.parent
    catalog = json.loads((root / "metadata" / "catalog.json").read_text(encoding="utf-8"))
    doc_path = root / "docs" / "kafka_data_contract_and_storage_guide.md"
    doc = doc_path.read_text(encoding="utf-8")

    machines = catalog["machines"]
    actual = {m["machineId"]: len(m["tags"]) for m in machines}
    cat_codes = {t["tagCode"] for m in machines for t in m["tags"]}
    cat_types = {
        t["tagCode"]: opcua_type_for(t.get("dataType"))
        for m in machines
        for t in m["tags"]
    }

    print("\n=== Kiểm tra tài liệu bàn giao vs catalog ===\n")

    # 1. Bảng máy
    print("[1] Bảng tổng quan máy")
    rows = re.findall(
        r"^\| (LINE_0\d|SHARED) \| (\w+) \| (\w+) \| \w+ \| (\d+) \|$", doc, re.M
    )
    check("26 dòng máy", len(rows) == 26, f"got {len(rows)}")
    mism = [
        (mid, int(n), actual.get(mid))
        for _, _, mid, n in rows
        if actual.get(mid) != int(n)
    ]
    check("Số tag khớp catalog", not mism, str(mism))
    check(
        "Tổng tag khớp",
        sum(int(n) for _, _, _, n in rows) == catalog["totalTags"],
        f"{sum(int(n) for _, _, _, n in rows)} vs {catalog['totalTags']}",
    )

    # 2. Bảng tag chi tiết
    print("\n[2] Bảng tag chi tiết")
    trows = re.findall(
        r"^\| `([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9_]+)` \| `(\w+)` \| `(\w+)` \|",
        doc,
        re.M,
    )
    check("404 dòng tag", len(trows) == catalog["totalTags"], f"got {len(trows)}")
    doc_codes = [c for c, _, _ in trows]
    check("Không trùng TagCode", len(set(doc_codes)) == len(doc_codes))
    check("Tập TagCode khớp catalog", set(doc_codes) == cat_codes,
          f"thiếu {sorted(cat_codes - set(doc_codes))[:5]}, "
          f"thừa {sorted(set(doc_codes) - cat_codes)[:5]}")
    wrong_vt = [
        (c, vt, cat_types.get(c))
        for c, _, vt in trows
        if cat_types.get(c) != vt
    ]
    check("valueType khớp mapping 3 tầng", not wrong_vt, str(wrong_vt[:5]))

    # 3. Các phần bắt buộc của contract
    print("\n[3] Nội dung contract")
    for section in [
        "## 3. Topic, partition, key, retention",
        "## 4. Schema message đầy đủ",
        "## 5. Giải thích từng trường",
        "## 7. Kiểu dữ liệu",
        "## 11. Đề xuất lưu DB raw data",
        "### 11.2. Phương án A — TimescaleDB (PostgreSQL)",
        "### 11.3. Phương án B — ClickHouse",
        "### 11.4. Phương án C — MinIO + Parquet",
        "## 12. Code mẫu consumer",
    ]:
        check(f"Có mục '{section.strip('# ')[:50]}'", section in doc)

    # 4. Kiểm tra các khẳng định quan trọng
    print("\n[4] Khẳng định quan trọng")
    check("eventId namespace đúng",
          "6f0d2b1e-9a4c-4c0e-9a1b-2c3d4e5f6a7b" in doc)
    check("Nêu rõ giới hạn Long/DWord",
          "Long" in doc and "DWord" in doc and "UInt64" not in
          doc.split("## 7.")[1].split("## 8.")[0].replace("không có `LWord`/`UInt64`", ""))
    check("Nêu Bad → value null", "null" in doc and "Bad" in doc)
    check("Nêu key = machineId", "machineId" in doc)

    # 5. Tính nhất quán với code + catalog hiện tại
    print("\n[5] Tính nhất quán với code hiện tại")
    from utils.event_id import build_event_id  # noqa: E402

    # 5a. Mọi eventId trong ví dụ phải là UUIDv5 thật (version nibble = 5).
    example_ids = re.findall(
        r'"eventId":\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
        doc,
    )
    check("Có eventId trong ví dụ", len(example_ids) >= 5, f"got {len(example_ids)}")
    bad_version = [e for e in example_ids if e.split("-")[2][0] != "5"]
    check("eventId trong ví dụ là UUIDv5 (version nibble = 5)",
          not bad_version, str(bad_version[:3]))

    # 5b. eventId ví dụ phải khớp công thức UUIDv5 của code.
    #      Lấy 1 ví dụ đầy đủ trong §6.1 để đối chiếu.
    m = re.search(
        r'"eventId":\s*"([0-9a-f-]{36})",.*?'
        r'"device":\s*"(\w+)".*?'
        r'"nodeId":\s*"ns=2;s=[\w.]+\.(\w+)".*?'
        r'"eventTime":\s*"([\d\-T:.Z]+)".*?'
        r'"measurement":\s*\{\s*"value":\s*([-\d.]+|true|false|null).*?'
        r'"statusCode":\s*"(\w+)"',
        doc,
        re.S,
    )
    check("Tìm được 1 message ví dụ đầy đủ", m is not None)
    if m:
        eid, device, tag_name, ts, raw_val, status = m.groups()
        if raw_val == "null":
            val = None
        elif raw_val == "true":
            val = True
        elif raw_val == "false":
            val = False
        else:
            val = float(raw_val)
        expected = build_event_id(device, tag_name, ts, val, status)
        check("eventId ví dụ khớp UUIDv5 tính từ code",
              eid == expected, f"doc={eid} code={expected}")

    # 5c. Enum MachineState trong tài liệu phải khớp design doc §9.1.
    check("Enum MachineState đúng (2=RUNNING, 4=FAULTED)",
          "0=OFF 1=STARTING 2=RUNNING 3=STOPPED 4=FAULTED 5=MAINTENANCE" in doc)

    # 5d. Nêu chế độ giả lập + lọc source.system.
    check("Nhắc chế độ giả lập (SIMULATION_MODE)",
          "SIMULATION_MODE" in doc)
    check("Nhắc lọc source.system",
          "source.system" in doc and "simulator" in doc)

    print(f"\n=== KẾT QUẢ: {PASSED} pass, {FAILED} fail ===\n")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
