"""
core/equipment_map.py
─────────────────────
Đọc ``equipment_map.json`` — ánh xạ ``Channel.Device`` (Kepware) → metadata máy.

Cấu trúc file (đã sinh từ ``metadata/catalog.json`` bằng
``tools/generate_tag_csv.py``):

{
  "plantId": "PLANT_01",
  "machines": {
    "LINE_01.L01_FILLER_01": {
      "machineId": "L01_FILLER_01",
      "machineType": "CARBONATED_FILLER",
      "equipmentCode": "FILL-L01-01",
      "lineId": "LINE_01",
      "processId": "FILLING"
    }
  }
}

Quy ước quan trọng (chốt ở design doc):
  - **Device chính là Machine.** ``source.device`` == ``machine.machineId``.
  - ``lineId`` trùng ``source.channel`` ở baseline, giữ cả hai để tương lai
    channel không còn là line.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger("industrial_telemetry.equipment_map")

DEFAULT_PLANT_ID = "PLANT_01"


@dataclass(frozen=True)
class MachineInfo:
    """Metadata của một máy, đã gộp phẳng để đưa vào message."""

    channel: str
    device: str
    machine_id: str
    machine_type: str
    equipment_code: str
    line_id: str
    process_id: str
    plant_id: str = DEFAULT_PLANT_ID

    @property
    def channel_device(self) -> str:
        return f"{self.channel}.{self.device}"

    def to_message_dict(self) -> dict[str, str]:
        """Khối ``plant`` + ``machine`` trong message."""
        return {
            "plant": {
                "plantId": self.plant_id,
                "lineId": self.line_id,
                "processId": self.process_id,
            },
            "machine": {
                "machineId": self.machine_id,
                "machineType": self.machine_type,
                "equipmentCode": self.equipment_code,
            },
        }


class EquipmentMap:
    """Bảng tra cứu metadata máy theo khóa ``Channel.Device``."""

    def __init__(self, machines: dict[str, MachineInfo], plant_id: str = DEFAULT_PLANT_ID):
        self._by_key = machines
        self._plant_id = plant_id

    # ── loading ─────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path | None = None) -> "EquipmentMap":
        """Đọc file JSON và dựng map."""
        resolved = Path(path or settings.EQUIPMENT_MAP_FILE)
        if not resolved.exists():
            raise FileNotFoundError(f"EQUIPMENT_MAP_FILE not found: {resolved}")

        with resolved.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        plant_id = str(raw.get("plantId") or DEFAULT_PLANT_ID)
        raw_machines: dict[str, Any] = raw.get("machines") or {}

        if not raw_machines:
            raise ValueError(
                f"{resolved} has no 'machines' section — expected "
                '{"plantId": ..., "machines": {"CHANNEL.DEVICE": {...}}}'
            )

        machines: dict[str, MachineInfo] = {}
        for key, entry in raw_machines.items():
            channel, device = _split_key(key)
            machine_id = str(entry.get("machineId") or device).strip()
            machines[key.strip()] = MachineInfo(
                channel=channel,
                device=device,
                machine_id=machine_id,
                machine_type=str(entry.get("machineType") or "").strip(),
                equipment_code=str(entry.get("equipmentCode") or "").strip(),
                line_id=str(entry.get("lineId") or channel).strip(),
                process_id=str(entry.get("processId") or "").strip(),
                plant_id=plant_id,
            )

        logger.info(
            "[EQUIPMENT MAP] Loaded %d machine(s) from %s (plant=%s)",
            len(machines),
            resolved.name,
            plant_id,
        )
        return cls(machines, plant_id)

    # ── lookup ──────────────────────────────────────────────────────────────

    def get(self, channel: str, device: str) -> MachineInfo | None:
        """Tra cứu theo channel + device. Trả None nếu không có."""
        return self._by_key.get(f"{channel}.{device}".strip())

    def require(self, channel: str, device: str) -> MachineInfo:
        """Tra cứu, raise nếu thiếu."""
        info = self.get(channel, device)
        if info is None:
            raise KeyError(
                f"No equipment mapping for '{channel}.{device}'. "
                "Add it to equipment_map.json."
            )
        return info

    def known_keys(self) -> set[str]:
        return set(self._by_key.keys())

    def missing_keys(self, channel_devices: set[str]) -> list[str]:
        """Danh sách Channel.Device trong CSV chưa có trong map."""
        return sorted(k for k in channel_devices if k not in self._by_key)

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self):
        return iter(self._by_key.values())


def _split_key(key: str) -> tuple[str, str]:
    """Tách ``"CHANNEL.DEVICE"`` → ``("CHANNEL", "DEVICE")``."""
    text = str(key).strip()
    if "." not in text:
        raise ValueError(
            f"Machine key {key!r} must be in 'CHANNEL.DEVICE' form"
        )
    channel, device = text.split(".", 1)
    return channel.strip(), device.strip()
