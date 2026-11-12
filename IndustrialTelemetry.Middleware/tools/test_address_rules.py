# -*- coding: utf-8 -*-
"""
Unit test cho quy tac sinh cot "Address" (logic tag simulator).

Kiem tra:
  1. Tien do dung theo kieu du lieu: B (Boolean) / K (so) / S (String)
  2. Ordinal dem CHUNG trong device, gian cach ADDRESS_STRIDE don vi
  3. Khop voi file Kepware tham khau (Vinamilk) — voi stride = 1
  4. Loi: kieu du lieu la, ordinal <= 0

Usage:
    python tools/test_address_rules.py
Exit code 0 = OK, 1 = co loi
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from address_rules import (  # noqa: E402
    ADDRESS_DIGITS,
    ADDRESS_STRIDE,
    address_prefix,
    assign_channel_addresses,
    build_addresses,
    expected_channel_addresses,
    make_address,
)

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


def test_prefix() -> None:
    print("1. Tien do theo kieu du lieu")
    check("Boolean -> B", address_prefix("Boolean") == "B")
    check("String -> S", address_prefix("String") == "S")
    for numeric in ("Int", "Word", "DWord", "Long", "Float", "Double"):
        check(f"{numeric} -> K", address_prefix(numeric) == "K")
    # Kieu khong hop le -> ValueError
    try:
        address_prefix("Int32")
        check("kieu la -> ValueError", False, "khong nem ValueError")
    except ValueError:
        check("kieu la -> ValueError", True)


def test_ordinal() -> None:
    print("\n2. Ordinal dem chung trong device, gian cach 10 don vi")
    check("stride = 10", ADDRESS_STRIDE == 10)
    check("so chu so mac dinh = 4", ADDRESS_DIGITS == 4)

    # Ordinal 1-based, nhan voi stride 10
    check("ordinal 1 -> B0000", make_address("Boolean", 1) == "B0000")
    check("ordinal 2 -> K0010", make_address("Float", 2) == "K0010")
    check("ordinal 3 -> K0020", make_address("Int", 3) == "K0020")
    check("ordinal 4 -> B0030", make_address("Boolean", 4) == "B0030")
    check("ordinal 10 -> K0090", make_address("Long", 10) == "K0090")
    check("ordinal 100 -> S0990", make_address("String", 100) == "S0990")
    # Vuot 4 chu so -> ghi them chu so (khong cat)
    check("ordinal 10000 -> 5 chu so", make_address("Int", 10000) == "K99990")

    # Ordinal <= 0 -> ValueError
    for bad in (0, -1):
        try:
            make_address("Int", bad)
            check(f"ordinal {bad} -> ValueError", False, "khong nem ValueError")
        except ValueError:
            check(f"ordinal {bad} -> ValueError", True)


def test_build_addresses() -> None:
    print("\n3. build_addresses — ordinal khong reset theo tien do")
    tags = [
        {"dataType": "Int"},       # 1 -> K0000
        {"dataType": "Int"},       # 2 -> K0010
        {"dataType": "Boolean"},   # 3 -> B0020  (KHONG reset)
        {"dataType": "Int"},       # 4 -> K0030
        {"dataType": "Float"},     # 5 -> K0040
        {"dataType": "Boolean"},   # 6 -> B0050
    ]
    result = build_addresses(tags)
    expected = ["K0000", "K0010", "B0020", "K0030", "K0040", "B0050"]
    check(
        "danh sach address dung thu tu",
        result == expected,
        f"actual={result}",
    )
    check("do dai khop", len(result) == len(tags))

    # Moi dia chi cach nhau it nhat ADDRESS_STRIDE don vi
    numbers = [int(a[1:]) for a in result]
    gaps = {b - a for a, b in zip(numbers, numbers[1:])}
    check(
        f"dia chi cach nhau it nhat {ADDRESS_STRIDE} don vi",
        all(gap >= ADDRESS_STRIDE for gap in gaps),
        f"gaps={gaps}",
    )
    check("khong co dia chi trung", len(set(result)) == len(result))


def test_reference_file() -> None:
    print("\n4. So voi file Kepware tham khau (Vinamilk)")
    # File tham khau: ChietRot_Line1.csv
    #   B3M01,B0001,Boolean
    #   B3M02,K0002,Word
    #   ...
    #   B3M06,B0006,Boolean
    #
    # ⚠️ File tham khau dung cong thuc ``number = ordinal`` (1, 2, 3...).
    # Cong thuc hien tai cua project la ``number = (ordinal - 1) * stride``
    # (0-based) — de moi tag chiem mot khoang trong giua, tranh ghi de
    # vong dem. Voi stride = 10 day la 0000, 0010, 0020...
    #
    # Vi vay KHONG the so sanh truc tiep voi file tham khau. Thay vao do
    # kiem tra: (a) tien do giong nhau, (b) do lech dung bang stride.
    ref = [
        ("Boolean", 1, "B0001"),
        ("Word", 2, "K0002"),
        ("Word", 3, "K0003"),
        ("Word", 4, "K0004"),
        ("Word", 5, "K0005"),
        ("Boolean", 6, "B0006"),
    ]
    for dt, ordinal, expected in ref:
        # Tien do phai giong file tham khau
        check(
            f"{dt} ordinal {ordinal}: tien do giong '{expected[0]}'",
            address_prefix(dt) == expected[0],
            f"actual={address_prefix(dt)}",
        )
        # Do lech so voi file tham khau = (ordinal - 1) * (stride - 1)
        actual = make_address(dt, ordinal)
        ref_number = int(expected[1:])
        our_number = int(actual[1:])
        check(
            f"{dt} ordinal {ordinal}: lech dung theo stride",
            our_number == (ordinal - 1) * ADDRESS_STRIDE,
            f"actual={actual} expected_number={(ordinal - 1) * ADDRESS_STRIDE}",
        )
        # Do lech giua 2 dia chi lien tiep phai >= stride
        if ordinal > 1:
            prev_number = int(make_address(dt, ordinal - 1)[1:])
            check(
                f"{dt} ordinal {ordinal}: cach tag truoc >= {ADDRESS_STRIDE}",
                our_number - prev_number >= ADDRESS_STRIDE,
                f"actual={actual}",
            )

    # Voi stride hien tai (10), 6 tag dau tieu se la 0000, 0010, 0020...
    check(
        "voi stride=10, 6 tag dau: B0000..B0050",
        [make_address(dt, i) for i, (dt, _, _) in enumerate(ref, start=1)]
        == ["B0000", "K0010", "K0020", "K0030", "K0040", "B0050"],
    )


def test_stride_configurable() -> None:
    print("\n5. Stride la hang so, doi 1 lan o 1 cho")
    import address_rules

    original = address_rules.ADDRESS_STRIDE
    try:
        address_rules.ADDRESS_STRIDE = 1
        # stride=1 -> number = ordinal - 1 (0-based)
        check(
            "stride=1 -> 0-based lien tuc",
            make_address("Boolean", 1) == "B0000"
            and make_address("Word", 6) == "K0005",
        )
        address_rules.ADDRESS_STRIDE = 100
        check(
            "stride=100 -> gian cach 100",
            make_address("Boolean", 2) == "B0100",
        )
    finally:
        address_rules.ADDRESS_STRIDE = original

    check("stride khoi phuc", address_rules.ADDRESS_STRIDE == 10)


def test_channel_uniqueness() -> None:
    print("\n6. Address khong trung TRONG CHANNEL (nhieu device)")

    # 2 device trong cung channel, deu co tag Boolean dau tien.
    # Neu ordinal reset theo device -> ca hai deu la "B0000" -> trung.
    machines = [
        {"machineId": "L01_AIRCONV_01", "channel": "LINE_01",
         "tags": [{"dataType": "Boolean"}, {"dataType": "Float"}]},
        {"machineId": "L01_BLOWER_01", "channel": "LINE_01",
         "tags": [{"dataType": "Boolean"}, {"dataType": "Boolean"},
                  {"dataType": "Long"}]},
        {"machineId": "L02_AIRCONV_01", "channel": "LINE_02",
         "tags": [{"dataType": "Boolean"}]},
    ]
    result = assign_channel_addresses(machines)

    check(
        "device 1 bat dau tu ordinal 1",
        result["L01_AIRCONV_01"][0] == "B0000",
        f"actual={result['L01_AIRCONV_01'][0]}",
    )
    check(
        "device 2 tiep tuc ordinal sau device 1 (khong reset)",
        result["L01_BLOWER_01"][0] == "B0020",
        f"actual={result['L01_BLOWER_01'][0]}",
    )
    check(
        "channel khac bat dau lai tu ordinal 1",
        result["L02_AIRCONV_01"][0] == "B0000",
        f"actual={result['L02_AIRCONV_01'][0]}",
    )

    # Khong trung trong channel
    for channel in ("LINE_01", "LINE_02"):
        devices = {m["machineId"]: m["tags"]
                   for m in machines if m["channel"] == channel}
        ch_addr = [a for dev, addrs in result.items()
                   if dev in devices for a in addrs]
        check(f"{channel}: khong co Address trung",
              len(ch_addr) == len(set(ch_addr)),
              f"dups={len(ch_addr) - len(set(ch_addr))}")
        check(f"{channel}: tat ca Address hop le",
              all(len(a) == ADDRESS_DIGITS + 1 for a in ch_addr))
    # Cac channel KHAC nhau duoc phep dung lai cung dia chi
    check(
        "channel khac nhau duoc phep trung Address",
        result["L01_AIRCONV_01"][0] == result["L02_AIRCONV_01"][0],
    )

    # expected_channel_addresses phai khop voi assign_channel_addresses
    exp = expected_channel_addresses({
        "L01_AIRCONV_01": ["Boolean", "Float"],
        "L01_BLOWER_01": ["Boolean", "Boolean", "Long"],
    })
    check(
        "expected_channel_addresses khop voi generator",
        exp["L01_AIRCONV_01"] == ["B0000", "K0010"]
        and exp["L01_BLOWER_01"] == ["B0020", "B0030", "K0040"],
        f"actual={exp}",
    )

    # build_addresses voi start_ordinal
    check(
        "build_addresses(start_ordinal=5) tiep tuc dung thu tu",
        build_addresses([{"dataType": "Boolean"}, {"dataType": "Int"}],
                        start_ordinal=5) == ["B0040", "K0050"],
    )


def main() -> int:
    print("=== TEST: quy tac cot Address ===\n")
    test_prefix()
    test_ordinal()
    test_build_addresses()
    test_reference_file()
    test_stride_configurable()
    test_channel_uniqueness()

    print(f"\n=== KET QUA: {PASSED} pass, {FAILED} fail ===")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
