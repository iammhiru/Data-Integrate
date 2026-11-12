"""
tools/preview_message.py
────────────────────────
Sinh thử message chuẩn từ metadata, KHÔNG cần Kepware hay Kafka.

Dùng để:
  - Kiểm tra data contract đúng chưa (sau khi sửa code hoặc đổi catalog).
  - Lấy mẫu JSON để đưa cho đồng đội.
  - Smoke-test: nếu pipeline load metadata + normalize chạy được, phần lớn
    lỗi cấu hình đã bị bắt sớm.

Cách chạy (từ thư mục IndustrialTelemetry.Middleware/):
    python tools/preview_message.py --machine L01_FILLER_01 --tag FillLevel
    python tools/preview_message.py --all --out preview.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Cho phép chạy trực tiếp file này mà không cần cài package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.equipment_map import EquipmentMap  # noqa: E402
from core.tag_loader import load_all_tags  # noqa: E402
from services.normalizer import Normalizer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview normalized telemetry message")
    parser.add_argument("--machine", help="machineId, ví dụ L01_FILLER_01")
    parser.add_argument("--tag", help="tagName, ví dụ FillLevel")
    parser.add_argument("--value", default="87.5", help="giá trị thử (mặc định 87.5)")
    parser.add_argument("--all", action="store_true", help="in 1 message cho mọi tag")
    parser.add_argument("--out", help="ghi kết quả ra file JSON")
    args = parser.parse_args()

    equipment_map = EquipmentMap.load()
    tags = load_all_tags()
    normalizer = Normalizer(equipment_map)

    # Chọn tag theo yêu cầu.
    selected = tags
    if args.machine:
        selected = [t for t in selected if t.device == args.machine]
    if args.tag:
        selected = [t for t in selected if t.tag_name == args.tag]
    if not selected:
        print("Không tìm thấy tag phù hợp.")
        return 1

    now = datetime.now(tz=timezone.utc)
    messages = []
    for tag in selected:
        raw = args.value
        if tag.kepware_type == "Boolean":
            raw = raw.lower() in ("true", "1", "yes")
        elif tag.kepware_type == "String":
            raw = str(raw)
        message = normalizer.normalize(
            tag_def=tag,
            value=raw,
            source_timestamp=now,
            server_timestamp=now,
            quality_raw="Good",
        )
        if message:
            messages.append(message)

    output = json.dumps(messages, ensure_ascii=False, indent=2)
    print(output)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"\nĐã ghi {len(messages)} message vào {args.out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
