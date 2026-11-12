"""
services/normalizer.py
──────────────────────
Dựng message chuẩn theo data contract (design doc §5).

Mỗi message = MỘT tag update. Không gom nhiều tag vào một record.

Cấu trúc message:
{
  "eventId":      "<uuid v5 tất định>",
  "eventType":    "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime":    "<ISO-8601 UTC, SourceTimestamp>",
  "source":       { system, channel, device, nodeId, serverTimestamp },
  "plant":        { plantId, lineId, processId },
  "machine":      { machineId, machineType, equipmentCode },
  "tag":          { tagName, tagCode, tagType },
  "measurement":  { value, valueType, unit },
  "quality":      { statusCode, isGood }
}
"""

from __future__ import annotations

import logging
from typing import Any

from config import settings
from core.equipment_map import MachineInfo
from core.tag_loader import TagDefinition
from utils.event_id import build_event_id
from utils.status_codes import normalize_status_code
from utils.time_utils import to_iso

logger = logging.getLogger("industrial_telemetry.normalizer")


class Normalizer:
    """
    Chuyển payload thô từ OPC UA thành message chuẩn.

    Normalizer là **stateless** (trừ việc đọc metadata), nên có thể dùng
    trong nhiều thread mà không cần khoá.
    """

    def __init__(self, equipment_map, source_system: str | None = None):
        self._equipment_map = equipment_map
        #: ``source.system`` ghi ra message. Mặc định lấy từ settings
        #: (``SOURCE_SYSTEM``). Chế độ giả lập sẽ override thành "simulator".
        self._source_system = source_system or settings.SOURCE_SYSTEM

    # ── main entry ──────────────────────────────────────────────────────────

    def normalize(
        self,
        tag_def: TagDefinition,
        value: Any,
        source_timestamp: Any,
        server_timestamp: Any = None,
        quality_raw: Any = None,
    ) -> dict[str, Any] | None:
        """
        Dựng message chuẩn.

        Returns:
            dict message, hoặc None nếu không tra được metadata máy.
        """
        machine = self._equipment_map.get(tag_def.channel, tag_def.device)
        if machine is None:
            logger.warning(
                "[NORMALIZER] No equipment metadata for %s — skipping %s",
                tag_def.channel_device,
                tag_def.node_id,
            )
            return None

        status_label, is_good = normalize_status_code(quality_raw)

        # Chỉ dùng giá trị khi quality không Bad.
        # Bad → value = null (không bao giờ bịa giá trị thay thế).
        if status_label == "Bad":
            normalized_value: Any = None
        else:
            normalized_value = self._coerce(tag_def, value)

        event_time = to_iso(source_timestamp, default_now=True)
        server_time = to_iso(server_timestamp)

        event_id = build_event_id(
            machine.machine_id,
            tag_def.tag_name,
            event_time or "",
            normalized_value,
            status_label,
        )

        message: dict[str, Any] = {
            "eventId": event_id,
            "eventType": settings.EVENT_TYPE,
            "schemaVersion": settings.SCHEMA_VERSION,
            "eventTime": event_time,
            "source": {
                "system": self._source_system,
                "channel": tag_def.channel,
                "device": tag_def.device,
                "nodeId": tag_def.node_id,
                "serverTimestamp": server_time,
            },
            "plant": {
                "plantId": machine.plant_id,
                "lineId": machine.line_id,
                "processId": machine.process_id,
            },
            "machine": {
                "machineId": machine.machine_id,
                "machineType": machine.machine_type,
                "equipmentCode": machine.equipment_code,
            },
            "tag": {
                "tagName": tag_def.tag_name,
                "tagCode": tag_def.tag_code,
                "tagType": tag_def.tag_type,
            },
            "measurement": {
                "value": normalized_value,
                "valueType": tag_def.value_type,
                "unit": tag_def.unit,
            },
            "quality": {
                "statusCode": status_label,
                "isGood": is_good,
            },
        }
        return message

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _coerce(tag_def: TagDefinition, value: Any) -> Any:
        """Ép giá trị theo kiểu Kepware khai báo trong CSV."""
        from core.value_types import coerce_value

        return coerce_value(value, tag_def.kepware_type)

    @staticmethod
    def preview(message: dict[str, Any]) -> str:
        """Tóm tắt ngắn gọn message để log (không log cả message dài)."""
        m = message.get("measurement", {})
        q = message.get("quality", {})
        return (
            f"{message.get('eventTime')} "
            f"{message.get('machine', {}).get('machineId')}/"
            f"{message.get('tag', {}).get('tagName')} "
            f"= {m.get('value')} {m.get('unit') or ''} "
            f"[{m.get('valueType')}/{q.get('statusCode')}]"
        ).strip()
