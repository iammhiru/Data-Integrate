"""
services/simulator.py
─────────────────────
Nguồn dữ liệu **GIẢ LẬP** — thay thế Kepware OPC UA server.

Bật/tắt bằng biến môi trường ``SIMULATION_MODE=true``.

Khi bật, middleware **không kết nối Kepware** mà tự sinh dữ liệu cho toàn bộ
tag trong ``TAG_FOLDER`` rồi đẩy vào **cùng một hàng đợi** và **cùng một đường
ống** với chế độ thật::

    SimulatedSource (thread) ──put_nowait──▶ value_queue ──▶ ValueWorker
                                                        ├─ STABLE gate
                                                        ├─ dedup (LRU + baseline)
                                                        ├─ Normalizer (message chuẩn)
                                                        └─ KafkaProducer.send()

⇒ Message ra Kafka **giống hệt** chế độ đọc Kepware thật: cùng data contract,
cùng partition key (``machineId``), cùng cơ chế dedup, cùng ``eventId`` UUID v5
tất định. Khác duy nhất: ``source.system`` = ``simulator`` (config được).

Vì sao cần:
-   Đồng đội không cài được Kepware vẫn chạy được middleware thật, kiểm tra
    được toàn bộ luồng xuống Kafka.
-   Test consumer / pipeline lưu trữ mà không cần dựng Kepware.

Mô phỏng bám theo quy tắc nghiệp vụ trong design doc §9.1:
-   ``MachineState`` đi theo chu kỳ OFF → STARTING → RUNNING ⇄ STOPPED, có
    thể rơi vào FAULTED / MAINTENANCE.
-   ``CurrentSpeed = 0`` khi không ``RUNNING``.
-   Bộ đếm **chỉ tăng khi ``RUNNING``**.
-   ``AlarmCode != 0`` khi ``FAULTED``.
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from config import settings
from core.tag_loader import TagDefinition
from utils.time_utils import utc_now

logger = logging.getLogger("industrial_telemetry.simulator")


# ─── Enum (design doc §9.1 / §9.2) ───────────────────────────────────────────

STATE_OFF = 0
STATE_STARTING = 1
STATE_RUNNING = 2
STATE_STOPPED = 3
STATE_FAULTED = 4
STATE_MAINTENANCE = 5

MODE_OFF = 0
MODE_MANUAL = 1
MODE_AUTO = 2
MODE_MAINTENANCE = 3


# ─── Hồ sơ giá trị theo đơn vị đo ────────────────────────────────────────────
#: (điểm gốc, biên độ dao động) cho tag số thực.
_UNIT_PROFILE: dict[str, tuple[float, float]] = {
    "%":       (55.0, 22.0),
    "bar":     (3.0, 0.6),
    "degC":    (55.0, 3.0),
    "Nm3/h":   (250.0, 40.0),
    "m3/h":    (20.0, 4.0),
    "kPa":     (-40.0, 5.0),
    "mm":      (50.0, 10.0),
    "Nm":      (20.0, 3.0),
    "rpm":     (1500.0, 150.0),
    "kW":      (20.0, 4.0),
    "g":       (300.0, 8.0),
    "s":       (12.0, 2.0),
    "uS/cm":   (400.0, 80.0),
    "pH":      (7.2, 0.2),
    "m/min":   (120.0, 15.0),
    "bottles/min": (120.0, 15.0),
    "preform/min": (120.0, 15.0),
    "caps/min":    (120.0, 15.0),
    "cans/min":    (120.0, 15.0),
    "pcs/min":     (120.0, 15.0),
    "cases/min":   (20.0, 4.0),
}

#: Đơn vị tốc độ dòng — dùng cho ``DesignSpeed`` / ``CurrentSpeed``.
_RATE_UNITS = frozenset(
    {"m/min", "bottles/min", "preform/min", "caps/min", "cans/min",
     "pcs/min", "cases/min"}
)

#: Tag nhiệt độ có điểm gốc riêng.
_TEMP_OVERRIDES: dict[str, tuple[float, float]] = {
    "MoldTemp":    (210.0, 8.0),
    "HeaterTemp":  (185.0, 6.0),
    "ProductTemp": (8.0, 0.5),
    "WaterTemp":   (22.0, 1.0),
    "RinseWaterTemp": (24.0, 1.0),
    "TankTemp":    (60.0, 2.0),
}

#: Tag hàng còn lại (met) — giảm dần rồi đặt lại.
_REMAINING_TAGS: dict[str, tuple[float, float]] = {
    "LabelRollRemaining": (1200.0, 2.0),   # (max, m/giây)
    "FilmRemaining":      (800.0, 3.0),
}

#: Tốc độ tích luỹ cho bộ đếm, theo đơn vị đo (đơn vị/giây).
_COUNTER_RATE: dict[str, float] = {
    "pcs": 45.0,
    "cases": 1.2,
    "pallets": 0.15,
}

#: Tag Boolean luôn False trừ khi có quy tắc riêng.
_BOOL_ALWAYS_FALSE = frozenset({
    "CameraFault", "GripperFault", "CaseJam", "CapMissing", "LabelMissing",
    "InkLow", "FilmLow", "TorqueHigh", "HopperLevelLow", "LabelRollLow",
})

#: Tag Int có giá trị hằng số.
_INT_CONST: dict[str, int] = {
    "BottlesPerCase": 24,
    "CansPerCase": 12,
    "CavityCount": 2,
    "LayerCount": 1,
    "RejectReason": 0,
}

#: Tag Int là enum nhỏ, đổi ngẫu nhiên trong khoảng.
_INT_ENUM: dict[str, int] = {
    "CaseFormat": 3,
    "InspectResult": 2,
    "PrintQuality": 2,
    "SeamQuality": 2,
    "CIPPhase": 4,
}


# ─── Trạng thái runtime của 1 máy ───────────────────────────────────────────


@dataclass
class MachineRuntime:
    """Trạng thái mô phỏng của một máy (dùng chung cho mọi tag của máy)."""

    rng: random.Random
    state: int = STATE_OFF
    mode: int = MODE_AUTO
    alarm_code: int = 0
    emergency_stop: bool = False
    state_timer: int = 0
    total: int = 0
    good: int = 0
    defect: int = 0
    design_speed: float = 100.0
    #: Bộ đếm phụ (Long) theo tên tag → giá trị tích luỹ.
    counters: dict[str, float] = field(default_factory=dict)
    #: Pha dao động của từng tag số thực (để giá trị chuyển động mượt).
    phases: dict[str, float] = field(default_factory=dict)
    #: Hàng còn lại (m) theo tên tag.
    remaining: dict[str, float] = field(default_factory=dict)


# ─── Sinh giá trị ───────────────────────────────────────────────────────────


class ValueGenerator:
    """Sinh giá trị giả lập cho một tag, dựa trên tên tag + đơn vị + kiểu."""

    def __init__(self, rng: random.Random):
        self._rng = rng

    # ── helpers ─────────────────────────────────────────────────────────────

    def _profile(self, tag: TagDefinition) -> tuple[float, float]:
        unit = (tag.unit or "").strip()
        if tag.tag_name in _TEMP_OVERRIDES:
            return _TEMP_OVERRIDES[tag.tag_name]
        return _UNIT_PROFILE.get(unit, (50.0, 10.0))

    def _wave(self, rt: MachineRuntime, tag_name: str, base: float, amp: float) -> float:
        """Giá trị số thực có dao động + nhiễu nhỏ (để luôn "đổi giá trị")."""
        phase = rt.phases.get(tag_name)
        if phase is None:
            phase = self._rng.uniform(0.0, math.tau)
        phase += 0.08
        rt.phases[tag_name] = phase
        wave = math.sin(phase)
        noise = self._rng.gauss(0.0, amp * 0.04)
        return round(base + amp * wave + noise, 3)

    # ── dispatch ────────────────────────────────────────────────────────────

    def generate(self, rt: MachineRuntime, tag: TagDefinition) -> object:
        """Sinh giá trị cho ``tag`` theo trạng thái runtime của máy."""
        name = tag.tag_name
        ktype = tag.kepware_type

        # ── Boolean ────────────────────────────────────────────────────────
        if ktype == "Boolean":
            return self._boolean(rt, name)

        # ── Long → bộ đếm tích luỹ ─────────────────────────────────────────
        if ktype == "Long":
            return self._counter(rt, tag, dt=1.0)

        # ── Int ────────────────────────────────────────────────────────────
        if ktype == "Int":
            return self._integer(rt, name)

        # ── Float ──────────────────────────────────────────────────────────
        return self._float(rt, tag)

    # ── từng nhóm kiểu ─────────────────────────────────────────────────────

    def _boolean(self, rt: MachineRuntime, name: str) -> bool:
        if name == "EmergencyStop":
            return rt.state == STATE_FAULTED and self._rng.random() < 0.3
        if name == "Starved":
            return rt.state == STATE_STOPPED and self._rng.random() < 0.15
        if name == "Blocked":
            return rt.state == STATE_STOPPED and self._rng.random() < 0.10
        if name in _BOOL_ALWAYS_FALSE:
            return False
        # Các cờ khác: hiếm khi True
        return self._rng.random() < 0.01

    def _integer(self, rt: MachineRuntime, name: str) -> int:
        if name == "MachineState":
            return rt.state
        if name == "MachineMode":
            return rt.mode
        if name == "AlarmCode":
            return rt.alarm_code
        if name == "HeadCount":
            # Bộ đếm kiểu Int — tích luỹ theo phút, chỉ khi RUNNING.
            value = rt.counters.get(name, 0.0)
            if rt.state == STATE_RUNNING:
                value += self._rng.uniform(0, 3)
            rt.counters[name] = value
            return int(value)
        if name in _INT_CONST:
            return _INT_CONST[name]
        if name in _INT_ENUM:
            # Enum nhỏ: đổi ngẫu nhiên, phần lớn giữ nguyên.
            if self._rng.random() < 0.05:
                rt.counters[name] = float(self._rng.randint(0, _INT_ENUM[name]))
            return int(rt.counters.get(name, 0.0))
        return 0

    def _counter(self, rt: MachineRuntime, tag: TagDefinition, dt: float) -> int:
        """Bộ đếm tích luỹ — chỉ tăng khi máy đang ``RUNNING`` (design doc §9.1)."""
        name = tag.tag_name
        running = rt.state == STATE_RUNNING

        if name == "TotalCounter":
            if running:
                rt.total += 1
            return rt.total
        if name == "GoodCounter":
            if running:
                rt.good += 1
            return rt.good
        if name == "DefectCounter":
            if running:
                rt.defect += 1
            return rt.defect

        unit = (tag.unit or "pcs").strip()
        rate = _COUNTER_RATE.get(unit, 10.0)
        # Bộ đếm phụ tăng chậm hơn bộ đếm chính.
        value = rt.counters.get(name, 0.0)
        if running:
            value += rate * 0.01 * self._rng.uniform(0.5, 1.5)
        rt.counters[name] = value
        return int(value)

    def _float(self, rt: MachineRuntime, tag: TagDefinition) -> float:
        name = tag.tag_name
        unit = (tag.unit or "").strip()

        # ── Tốc độ ─────────────────────────────────────────────────────────
        if name == "DesignSpeed":
            return round(rt.design_speed, 3)
        if name == "CurrentSpeed":
            if rt.state != STATE_RUNNING:
                return 0.0
            base, amp = self._profile(tag)
            value = self._wave(rt, name, rt.design_speed, rt.design_speed * 0.06)
            return round(max(0.0, value), 3)

        # ── Hàng còn lại (giảm dần) ───────────────────────────────────────
        if name in _REMAINING_TAGS:
            maximum, per_sec = _REMAINING_TAGS[name]
            remaining = rt.remaining.get(name, maximum)
            remaining -= per_sec * 0.01 * self._rng.uniform(0.5, 1.5)
            if remaining <= 0:
                remaining = maximum
            rt.remaining[name] = remaining
            return round(remaining, 3)

        # ── Mức phần trăm (dao động chậm) ─────────────────────────────────
        if unit == "%":
            base, amp = self._profile(tag)
            phase = rt.phases.get(name)
            if phase is None:
                phase = self._rng.uniform(0.0, math.tau)
            phase += 0.02
            rt.phases[name] = phase
            value = base + amp * math.sin(phase) + self._rng.gauss(0.0, 0.4)
            return round(min(100.0, max(0.0, value)), 3)

        # ── Tốc độ dòng / lưu lượng ──────────────────────────────────────
        if unit in _RATE_UNITS:
            if rt.state != STATE_RUNNING:
                return 0.0
            base, amp = self._profile(tag)
            return round(max(0.0, self._wave(rt, name, base, amp)), 3)

        # ── Còn lại: profile theo đơn vị ──────────────────────────────────
        base, amp = self._profile(tag)
        return round(self._wave(rt, name, base, amp), 3)


# ─── Nguồn dữ liệu giả lập ───────────────────────────────────────────────────


class SimulatedSource:
    """
    Thread tạo dữ liệu giả lập và đẩy vào ``value_queue``.

    Mỗi tag được phát theo đúng ``Scan Rate`` khai báo trong CSV (giống cách
    Kepware quét) — nhân với ``SIMULATION_SPEED_FACTOR``.
    """

    def __init__(
        self,
        tags: list[TagDefinition],
        enqueue: Callable[[dict], None],
    ):
        self._tags = list(tags)
        self._enqueue = enqueue
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        rng = random.Random(settings.SIMULATION_SEED)

        # Gom tag theo máy.
        self._by_device: dict[str, list[TagDefinition]] = {}
        for tag in self._tags:
            self._by_device.setdefault(tag.channel_device, []).append(tag)

        self._runtimes: dict[str, MachineRuntime] = {}
        for key in self._by_device:
            rt = MachineRuntime(rng=rng)
            # Tốc độ thiết kế khác nhau theo máy, cố định trong vòng đời.
            rt.design_speed = round(rng.uniform(80.0, 150.0), 3)
            self._runtimes[key] = rt

        self._generator = ValueGenerator(rng)

        # Mốc phát tiếp theo cho từng tag.
        self._next_due: dict[str, float] = {
            tag.node_id: 0.0 for tag in self._tags
        }

    # ── lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> threading.Thread:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="simulated-source", daemon=True
        )
        self._thread.start()
        logger.info(
            "[SIMULATOR] Started — %d tag(s) / %d machine(s), "
            "tick=%dms, speed_factor=%.2f, seed=%d",
            len(self._tags),
            len(self._by_device),
            settings.SIMULATION_TICK_MS,
            settings.SIMULATION_SPEED_FACTOR,
            settings.SIMULATION_SEED,
        )
        return self._thread

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            logger.info("[SIMULATOR] Stopped")

    # ── vòng lặp ───────────────────────────────────────────────────────────

    def _run(self) -> None:
        tick_sec = settings.SIMULATION_TICK_MS / 1000.0
        last = time.monotonic()
        while not self._stop_event.is_set():
            self._stop_event.wait(tick_sec)
            now = time.monotonic()
            dt = now - last
            last = now
            try:
                self._tick(now, dt)
            except Exception as exc:  # pragma: no cover - không được làm chết thread
                logger.error("[SIMULATOR] Tick error: %s", exc)

    def _tick(self, now: float, dt: float, advance_state: bool = True) -> None:
        """Mỗi nhịp: tiến trạng thái máy, rồi phát các tag đã đến hạn.

        Args:
            now: mốc thời gian hiện tại (monotonic).
            dt: khoảng thời gian đã trôi qua (giây).
            advance_state: False → giữ nguyên trạng thái máy (dùng cho test).
        """
        if advance_state:
            for rt in self._runtimes.values():
                self._advance_state(rt, dt)

        speed = settings.SIMULATION_SPEED_FACTOR
        if speed <= 0:
            speed = 1.0

        emitted = 0
        for tag in self._tags:
            due = self._next_due.get(tag.node_id, 0.0)
            if now < due:
                continue

            rt = self._runtimes[tag.channel_device]
            value = self._generator.generate(rt, tag)
            self._enqueue(self._make_payload(tag, value))

            # Lịch phát tiếp theo theo Scan Rate của CSV.
            scan_ms = tag.scan_rate_ms or settings.SIMULATION_DEFAULT_SCAN_MS
            interval = max(0.01, (scan_ms / 1000.0) / speed)
            self._next_due[tag.node_id] = now + interval
            emitted += 1

        if emitted:
            logger.debug("[SIMULATOR] Emitted %d tag(s) this tick", emitted)

    # ── helpers ────────────────────────────────────────────────────────────

    def _advance_state(self, rt: MachineRuntime, dt: float) -> None:
        """Chuyển trạng thái máy theo luật §9.1 của design doc."""
        rt.state_timer += dt
        roll = rt.rng.random()

        if rt.state == STATE_OFF:
            if rt.state_timer > 3.0:
                rt.state = STATE_STARTING
                rt.state_timer = 0.0
        elif rt.state == STATE_STARTING:
            if rt.state_timer > 2.0:
                rt.state = STATE_RUNNING
                rt.state_timer = 0.0
        elif rt.state == STATE_RUNNING:
            if roll < 0.004:
                rt.state = STATE_FAULTED
                rt.state_timer = 0.0
                rt.alarm_code = rt.rng.randint(100, 999)
            elif roll < 0.020:
                rt.state = STATE_STOPPED
                rt.state_timer = 0.0
            elif roll < 0.023:
                rt.state = STATE_MAINTENANCE
                rt.state_timer = 0.0
        elif rt.state == STATE_STOPPED:
            if rt.state_timer > 8.0:
                rt.state = STATE_RUNNING
                rt.state_timer = 0.0
        elif rt.state == STATE_FAULTED:
            if rt.state_timer > 6.0:
                rt.state = STATE_RUNNING
                rt.state_timer = 0.0
                rt.alarm_code = 0
        elif rt.state == STATE_MAINTENANCE:
            if rt.state_timer > 12.0:
                rt.state = STATE_RUNNING
                rt.state_timer = 0.0

        # Chế độ điều khiển: AUTO là mặc định, thỉnh thoảng MANUAL/MAINTENANCE.
        if rt.state == STATE_MAINTENANCE:
            rt.mode = MODE_MAINTENANCE
        elif rt.state == STATE_OFF:
            rt.mode = MODE_OFF
        elif rt.mode == MODE_MAINTENANCE or rt.mode == MODE_OFF:
            rt.mode = MODE_AUTO

    def _make_payload(self, tag: TagDefinition, value: object) -> dict:
        """Dựng payload đúng cấu trúc SubHandler tạo ra."""
        now = utc_now()
        return {
            "node_id": tag.node_id,
            "tag_def": tag,
            "value": value,
            "raw_value": value,
            "source_timestamp": now,
            "server_timestamp": now,
            "quality_raw": self._quality(),
            "force": False,
        }

    def _quality(self) -> str:
        """Chất lượng giả lập — mặc định luôn ``Good``."""
        rate = settings.SIMULATION_QUALITY_FAULT_RATE
        if rate <= 0:
            return "Good"
        roll = self._generator._rng.random()
        if roll < rate:
            return "BadNoCommunication"
        if roll < rate * 2:
            return "UncertainLastUsableValue"
        return "Good"
