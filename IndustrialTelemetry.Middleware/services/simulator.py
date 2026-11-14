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

════════════════════════════════════════════════════════════════════════════
MÔ HÌNH NGHIỆP VỤ (design doc §9.1) — các quy tắc được BẢO ĐẢM
════════════════════════════════════════════════════════════════════════════

1.  **Trạng thái máy** đi theo chu kỳ OFF → STARTING → RUNNING ⇄ STOPPED,
    có thể rơi vào FAULTED / MAINTENANCE.
    -   RUNNING là trạng thái chiếm ưu thế (~85% thời gian).
    -   MTBF 1–2.5 h; thời gian sửa 2–15 phút.
    -   Dừng ngắn (micro-stop) 45 giây – 7 phút, trung bình ~1 lần/2 giờ.
    -   Bảo trì định kỳ 10–40 phút, trung bình ~1 lần/9 giờ.
    -   Có "đường giữa" tối thiểu (>= 2 phút RUNNING) để **không flapping**.

2.  **Bộ đếm tăng theo THỜI GIAN × TỐC ĐỘ**, không tăng theo số lần đọc tag:
    ``dTotal/dt = DesignSpeed/60 × speed_ratio`` (đơn vị/phút → đơn vị/giây).
    ⇒ ``ideal_time_sec = total × 60 / design_speed`` (công thức của batch) ra
    đúng thời gian chạy thực ⇒ Performance ≈ speed_ratio ≈ 0.96.

3.  **``TotalCounter = GoodCounter + DefectCounter``** — LUÔN đúng, tuyệt đối.
    Tỉ lệ NG mỗi máy 0.5%–2.5% (phần lớn là hàng đạt).

4.  **``AlarmCode`` chỉ khác 0 khi ``FAULTED``**, về ``0`` ngay khi rời FAULTED.

5.  **``CurrentSpeed = 0`` khi không ``RUNNING``**; khi chạy thì
    ``= DesignSpeed × speed_ratio`` (dao động mượt quanh 0.96, nằm trong
    0.78–1.02).

6.  **Cờ lỗi boolean** (``Starved``, ``Blocked``, ``CameraFault``…) chỉ True
    đúng lúc máy thực sự ở trạng thái tương ứng — không nhấp nháy ngẫu nhiên.

════════════════════════════════════════════════════════════════════════════
LƯU Ý VỀ ``SIMULATION_SPEED_FACTOR``
════════════════════════════════════════════════════════════════════════════
Hệ số này chỉ **tăng tần suất phát message** (rút ngắn chu kỳ quét), KHÔNG
tăng tốc độ thời gian mô phỏng. Lý do: ``batch_kpi`` tính ``run_sec`` theo
**wall-clock** của event; nếu bộ đếm chạy nhanh hơn wall-clock thì Performance
sẽ vượt 100%. Vì vậy bộ đếm và máy trạng thái đều dùng **thời gian thật**.
"""

from __future__ import annotations

import json
import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
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

#: Tag phần trăm có vùng làm việc riêng (điểm gốc, biên độ).
_LEVEL_OVERRIDES: dict[str, tuple[float, float]] = {
    "FillLevel":  (92.0, 4.0),
    "TankLevel":  (78.0, 10.0),
    "InkLevel":   (68.0, 14.0),
}

#: Tag hàng còn lại (met) — giảm dần rồi đặt lại.
_REMAINING_TAGS: dict[str, tuple[float, float]] = {
    "LabelRollRemaining": (1200.0, 2.0),   # (max, m/giây)
    "FilmRemaining":      (800.0, 3.0),
}

#: Tốc độ tích luỹ cho bộ đếm phụ, theo đơn vị đo (đơn vị/giây).
_COUNTER_RATE: dict[str, float] = {
    "pcs": 45.0,
    "cases": 1.2,
    "pallets": 0.15,
}

#: Tag Int có giá trị hằng số.
_INT_CONST: dict[str, int] = {
    "BottlesPerCase": 24,
    "CansPerCase": 12,
    "CavityCount": 2,
    "LayerCount": 1,
}

#: Tag Int là enum nhỏ — giá trị ổn định, đổi rất hiếm.
_INT_ENUM: dict[str, int] = {
    "CaseFormat": 2,
    "CIPPhase": 4,
}

#: Tag enum "chất lượng" — 2 = đạt, 0/1 = không đạt.
_QUALITY_INT = frozenset({"InspectResult", "PrintQuality", "SeamQuality"})

#: Mã alarm theo loại sự cố (chỉ dùng khi FAULTED).
_FAULT_CODES: dict[str, int] = {
    "sensor":     1021,
    "motor":      1032,
    "mechanical": 1057,
    "pneumatic":  1063,
    "quality":    1073,
    "safety":     1088,
}

#: Nguyên nhân dừng (micro-stop) → boolean tag tương ứng.
_STOP_REASONS: tuple[str, ...] = (
    "starved", "blocked", "jam", "missing_cap", "missing_label",
    "ink_low", "film_low", "hopper_low", "label_roll",
)

#: Nguyên nhân dừng → boolean tag phải bật.
_STOP_REASON_TAG: dict[str, str] = {
    "starved": "Starved",
    "blocked": "Blocked",
    "jam": "CaseJam",
    "missing_cap": "CapMissing",
    "missing_label": "LabelMissing",
    "ink_low": "InkLow",
    "film_low": "FilmLow",
    "hopper_low": "HopperLevelLow",
    "label_roll": "LabelRollLow",
}

#: Loại lỗi → boolean tag phải bật khi FAULTED.
_FAULT_REASON_TAG: dict[str, str] = {
    "sensor": "CameraFault",
    "motor": "MotorFault",
    "mechanical": "GripperFault",
    "pneumatic": "TorqueHigh",
    "quality": "QualityFault",
    "safety": "EmergencyStop",
}


# ─── Tham số mô phỏng (chọn theo thực tế nhà máy) ───────────────────────────

#: Thời gian OFF trước khi máy khởi động (giây).
_OFF_MIN_S = 5.0
_OFF_MAX_S = 20.0

#: Thời gian khởi động (STARTING) — máy nóng dần, chưa ra sản phẩm.
_START_MIN_S = 8.0
_START_MAX_S = 25.0

#: MTBF (giây) — thời gian RUNNING liên tục giữa 2 lần lỗi.
_MTBF_MIN_S = 3_600.0      # 1 giờ
_MTBF_MAX_S = 9_000.0      # 2.5 giờ

#: Thời gian sửa chữa sau lỗi (giây).
_REPAIR_MIN_S = 90.0       # 1.5 phút
_REPAIR_MAX_S = 600.0      # 10 phút

#: Dừng ngắn không có lỗi (micro-stop).
_STOP_MIN_S = 45.0
_STOP_MAX_S = 420.0
_STOP_GAP_MIN_S = 7_200.0    # trung bình ~1 lần / 2.5 giờ
_STOP_GAP_MAX_S = 14_400.0

#: Bảo trì định kỳ (planned maintenance — ít và đều).
_MAINT_MIN_S = 600.0          # 10 phút
_MAINT_MAX_S = 1_800.0        # 30 phút
_MAINT_GAP_MIN_S = 28_800.0   # trung bình ~1 lần / 13 giờ
_MAINT_GAP_MAX_S = 57_600.0

#: Thời gian RUNNING tối thiểu trước khi được phép dừng/lỗi (chống flapping).
_MIN_RUN_MIN_S = 120.0
_MIN_RUN_MAX_S = 300.0

#: Tốc độ thực tế so với thiết kế (nhân với ``DesignSpeed``).
_SPEED_RATIO_MEAN = 0.96
_SPEED_RATIO_MIN = 0.78
_SPEED_RATIO_MAX = 1.02
#: Cường độ nhiễu dao động tốc độ (đơn vị: tỉ lệ / giây).
_SPEED_NOISE = 0.02
#: Hệ số kéo tốc độ về trung bình (1/s) — quy trình OU.
_SPEED_PULL = 0.15

#: Tỉ lệ NG của máy (phần sản lượng bị loại).
_DEFECT_RATE_MIN = 0.005
_DEFECT_RATE_MAX = 0.025

#: CIP: chu kỳ rửa (giây) — bộ đếm "cycles" tăng 1 mỗi chu kỳ.
_CIP_CYCLE_S = 7_200.0

#: Thiết bị phụ (CIP) dễ lỗi hơn/ít hơn máy chính.
_AUX_FAULT_FACTOR = 0.4

#: DesignSpeed fallback theo đơn vị (khi không đọc được file cấu hình).
_FALLBACK_DESIGN_SPEED: dict[str, tuple[float, float]] = {
    "bottles/min": (85.0, 150.0),
    "preform/min": (90.0, 150.0),
    "cans/min":    (100.0, 150.0),
    "pcs/min":     (110.0, 140.0),
    "cases/min":   (85.0, 115.0),
    "m/min":       (100.0, 130.0),
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

    # ── Cấu hình riêng của máy ────────────────────────────────────────────
    #: Tỉ lệ NG (0.005 – 0.025) — phần lớn sản lượng là hàng đạt.
    defect_rate: float = 0.01
    #: Hệ số tốc độ thực / thiết kế (dao động mượt quanh 0.96).
    speed_ratio: float = _SPEED_RATIO_MEAN
    #: Máy có tag GoodCounter / DefectCounter hay không.
    has_good: bool = True
    has_defect: bool = True
    #: Máy phụ (CIP) — không tính OEE sản xuất.
    is_aux: bool = False
    #: Số chai/lon trong 1 thùng (dùng cho bộ đếm dẫn xuất).
    bottles_per_case: int = 24
    #: Ước lượng số thùng / pallet (để bộ đếm pallet hợp lý).
    cases_per_pallet: int = 40
    #: Số đầu chiết (hằng số theo máy).
    head_count: int = 6
    #: Đơn vị của ``DesignSpeed`` (vd "bottles/min") — quyết định cách hiểu
    #: bộ đếm chính (bộ đếm chính luôn tính theo ĐƠN VỊ THIẾT KẾ để công thức
    #: ``ideal_time_sec = total × 60 / design_speed`` của batch khớp đúng).
    design_unit: str = ""
    #: Đơn vị của bộ đếm chính (pcs / cases / cycles).
    counter_unit: str = "pcs"

    # ── Trạng thái tích luỹ của bộ đếm ───────────────────────────────────
    #: Phần sản lượng chưa làm tròn (để bộ đếm tăng đều, không nhảy cục).
    prod_fraction: float = 0.0
    #: Phần NG chưa làm tròn.
    defect_fraction: float = 0.0
    #: Thời gian mô phỏng đã trôi qua (giây) — dùng làm mốc cho sự kiện.
    sim_time: float = 0.0
    #: Mốc lần cuối có NG (để enum chất lượng / RejectReason phản ánh thực tế).
    last_defect_time: float = -999.0

    # ── Lịch trạng thái ───────────────────────────────────────────────────
    #: Thời gian đã trôi qua ở trạng thái hiện tại (giây).
    state_elapsed: float = 0.0
    #: Thời điểm (giây kể từ lúc vào trạng thái) chuyển sang trạng thái sau.
    next_transition_s: float = 0.0
    #: MTBF của máy (giây) — kỳ vọng giữa 2 lần lỗi.
    mtbf_s: float = 6_000.0
    #: Khoảng cách kỳ vọng giữa 2 lần dừng ngắn (giây).
    stop_gap_s: float = 8_000.0
    #: Khoảng cách kỳ vọng giữa 2 lần bảo trì (giây).
    maint_gap_s: float = 32_000.0
    #: Thời gian RUNNING tối thiểu trước khi được phép dừng/lỗi.
    min_run_s: float = 180.0
    #: Hệ số nhân xác suất lỗi (máy phụ ít lỗi hơn).
    fault_factor: float = 1.0
    #: Nguyên nhân của sự cố / lý do dừng hiện tại.
    fault_kind: str = ""
    stop_reason: str = ""


# ─── Sinh giá trị ───────────────────────────────────────────────────────────


class ValueGenerator:
    """Sinh giá trị giả lập cho một tag, dựa trên tên tag + đơn vị + kiểu."""

    def __init__(self, rng: random.Random):
        self._rng = rng

    # ── helpers ─────────────────────────────────────────────────────────────

    def _profile(self, tag: TagDefinition) -> tuple[float, float]:
        name = tag.tag_name
        unit = (tag.unit or "").strip()
        if name in _TEMP_OVERRIDES:
            return _TEMP_OVERRIDES[name]
        if name in _LEVEL_OVERRIDES:
            return _LEVEL_OVERRIDES[name]
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

    def _recent_defect(self, rt: MachineRuntime, window_s: float = 5.0) -> bool:
        """Vừa xảy ra NG trong ``window_s`` giây gần đây hay không."""
        return (rt.sim_time - rt.last_defect_time) <= window_s

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
            return self._counter(rt, tag)

        # ── Int ────────────────────────────────────────────────────────────
        if ktype == "Int":
            return self._integer(rt, name)

        # ── Float ──────────────────────────────────────────────────────────
        return self._float(rt, tag)

    # ── từng nhóm kiểu ─────────────────────────────────────────────────────

    def _boolean(self, rt: MachineRuntime, name: str) -> bool:
        """Cờ boolean — chỉ True đúng lúc máy thực sự gặp sự cố tương ứng."""
        if name == "EmergencyStop":
            return rt.emergency_stop
        if name in ("HeatingOn", "CirculationOn"):
            # CIP: bơm/hơi nóng chạy khi máy RUNNING.
            return rt.state == STATE_RUNNING
        if name in _STOP_REASON_TAG.values():
            # Cờ dừng (Starved/Blocked/CaseJam/CapMissing…) chỉ bật đúng lúc
            # máy STOPPED với nguyên nhân tương ứng.
            if rt.state != STATE_STOPPED:
                return False
            return _STOP_REASON_TAG.get(rt.stop_reason) == name
        # Cờ lỗi cơ/khí (CameraFault, GripperFault, TorqueHigh…)
        if rt.state == STATE_FAULTED:
            return _FAULT_REASON_TAG.get(rt.fault_kind) == name
        return False

    def _integer(self, rt: MachineRuntime, name: str) -> int:
        if name == "MachineState":
            return rt.state
        if name == "MachineMode":
            return rt.mode
        if name == "AlarmCode":
            # Chỉ khác 0 khi FAULTED — nếu không thì luôn 0.
            return rt.alarm_code if rt.state == STATE_FAULTED else 0
        if name == "HeadCount":
            return rt.head_count
        if name in _INT_CONST:
            return _INT_CONST[name]
        if name in _QUALITY_INT:
            # 2 = đạt; 0/1 = NG — chỉ xuất hiện NG khi máy thực sự vừa phát
            # hiện phế phẩm (bám theo sự kiện defect, không nhấp nháy ngẫu nhiên).
            if not rt.has_defect:
                return 2
            if self._recent_defect(rt, window_s=2.0) and self._rng.random() < 0.25:
                return self._rng.choice([0, 1])
            return 2
        if name == "RejectReason":
            # 0 = không loại; khác 0 khi vừa phát hiện NG.
            if self._recent_defect(rt, window_s=3.0):
                return self._rng.randint(1, 4)
            return 0
        if name == "CIPPhase":
            # Pha CIP (0 = không CIP) — chỉ máy rửa mới có tag này.
            # Pha tiến dần theo thời gian chạy; khi máy dừng → về 0.
            if rt.state != STATE_RUNNING:
                return 0
            phase = int((rt.sim_time % (4 * _CIP_CYCLE_S)) // _CIP_CYCLE_S) + 1
            return min(phase, 4)
        if name in _INT_ENUM:
            # Enum ổn định — đổi rất hiếm để tránh nhấp nháy.
            cur = rt.counters.get(name)
            if cur is None or self._rng.random() < 0.01:
                rt.counters[name] = float(self._rng.randint(0, _INT_ENUM[name]))
            return int(rt.counters[name])
        return 0

    def _counter(self, rt: MachineRuntime, tag: TagDefinition) -> int:
        """Bộ đếm tích luỹ — cập nhật theo THỜI GIAN ở ``_advance_production``.

        ⚠ Bộ đếm KHÔNG tăng trong hàm này. Việc tăng bộ đếm do
        ``SimulatedSource._advance_production`` đảm nhiệm (theo wall-clock ×
        tốc độ), nhờ vậy:
          · ``Total = Good + Defect`` luôn đúng;
          · tốc độ sản xuất không phụ thuộc tần suất đọc tag;
          · ``ideal_time_sec`` của batch khớp thời gian chạy thực.
        """
        name = tag.tag_name
        if name == "TotalCounter":
            return rt.total
        if name == "GoodCounter":
            return rt.good
        if name == "DefectCounter":
            return rt.defect

        # ── Bộ đếm dẫn xuất — luôn <= bộ đếm chính, tăng đồng bộ ──────────
        if name == "CaseCount":
            # Máy đóng hàng (thiết kế theo cases/min) → bộ đếm chính đã tính
            # theo thùng; máy tính theo pcs → chia cho số chai/lon mỗi thùng.
            if rt.design_unit == "cases/min":
                return rt.total
            return int(rt.total // rt.bottles_per_case)
        if name == "PalletCount":
            if rt.design_unit == "cases/min":
                return int(rt.total // rt.cases_per_pallet)
            return int(rt.total // (rt.bottles_per_case * rt.cases_per_pallet))
        if name in ("PrintCount", "LabelApplyCount", "InspectionCount"):
            return rt.total
        if name == "SeamDefectCount":
            return rt.defect

        # ── Bộ đếm phụ khác: tăng theo tốc độ máy ─────────────────────────
        unit = (tag.unit or "pcs").strip()
        rate = _COUNTER_RATE.get(unit, 10.0)
        value = rt.counters.get(name, 0.0)
        if rt.state == STATE_RUNNING:
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
            return round(max(0.0, rt.design_speed * rt.speed_ratio), 3)

        # ── Hàng còn lại (giảm dần) ───────────────────────────────────────
        if name in _REMAINING_TAGS:
            maximum, per_sec = _REMAINING_TAGS[name]
            remaining = rt.remaining.get(name, maximum)
            if rt.state == STATE_RUNNING:
                remaining -= per_sec * 0.01 * self._rng.uniform(0.5, 1.5)
            if remaining <= 0:
                remaining = maximum
            rt.remaining[name] = remaining
            return round(remaining, 3)

        # ── Tốc độ dòng / lưu lượng (bám theo tốc độ máy) ──────────────────
        if unit in _RATE_UNITS:
            if rt.state != STATE_RUNNING:
                return 0.0
            jitter = self._rng.gauss(0.0, 0.012)
            if rt.design_speed > 0 and unit == rt.design_unit:
                # Cùng đơn vị với thiết kế → bám trực tiếp DesignSpeed.
                return round(max(0.0, rt.design_speed * rt.speed_ratio * (1.0 + jitter)), 3)
            # Khác đơn vị (vd CapFeedRate caps/min trên máy thiết kế bottles/min)
            # → dùng điểm gốc riêng của đơn vị, nhưng dao động theo tốc độ máy.
            base, _amp = self._profile(tag)
            return round(max(0.0, base * rt.speed_ratio * (1.0 + jitter)), 3)

        # ── Mức phần trăm (dao động chậm) ─────────────────────────────────
        if unit == "%":
            if name == "DefectRate":
                # Tỉ lệ NG thật của máy (dao động nhẹ quanh defect_rate).
                value = rt.defect_rate * 100.0 * self._rng.uniform(0.6, 1.4)
                return round(min(100.0, max(0.0, value)), 3)
            base, amp = self._profile(tag)
            phase = rt.phases.get(name)
            if phase is None:
                phase = self._rng.uniform(0.0, math.tau)
            phase += 0.02
            rt.phases[name] = phase
            value = base + amp * math.sin(phase) + self._rng.gauss(0.0, 0.4)
            return round(min(100.0, max(0.0, value)), 3)

        # ── Còn lại: profile theo đơn vị ──────────────────────────────────
        base, amp = self._profile(tag)
        return round(self._wave(rt, name, base, amp), 3)


# ─── Nguồn dữ liệu giả lập ───────────────────────────────────────────────────


class SimulatedSource:
    """
    Thread tạo dữ liệu giả lập và đẩy vào ``value_queue``.

    Mỗi tag được phát theo đúng ``Scan Rate`` khai báo trong CSV (giống cách
    Kepware quét) — nhân với ``SIMULATION_SPEED_FACTOR``.

    Trạng thái máy và bộ đếm được cập nhật theo **wall-clock thực**, nên số
    liệu OEE tính được từ PostgreSQL luôn có ý nghĩa.
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

        self._design_speeds = self._load_design_speeds()

        self._runtimes: dict[str, MachineRuntime] = {}
        for key, device_tags in self._by_device.items():
            self._runtimes[key] = self._make_runtime(rng, key, device_tags)

        self._generator = ValueGenerator(rng)

        # Mốc phát tiếp theo cho từng tag.
        self._next_due: dict[str, float] = {
            tag.node_id: 0.0 for tag in self._tags
        }

    # ── khởi tạo ───────────────────────────────────────────────────────────

    def _load_design_speeds(self) -> dict[str, float]:
        """Đọc ``metadata/design_speed.json`` (nếu có) — tốc độ thiết kế thật.

        File này giữ cho simulator và PostgreSQL (``machine.ideal_speed``)
        dùng CÙNG một con số → Performance tính ra khớp với thiết kế.
        """
        path = getattr(settings, "SIMULATION_DESIGN_SPEED_FILE", None)
        if not path:
            return {}
        p = Path(path)
        if not p.is_absolute():
            p = settings.PROJECT_ROOT / p
        if not p.exists():
            logger.info("[SIMULATOR] design_speed file not found: %s (dùng fallback)", p)
            return {}
        try:
            with p.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            logger.warning("[SIMULATOR] Cannot read design_speed file %s: %s", p, exc)
            return {}
        out: dict[str, float] = {}
        for mid, item in (data or {}).items():
            val = item.get("design_speed") if isinstance(item, dict) else None
            if val:
                out[mid] = float(val)
        return out

    def _make_runtime(
        self,
        rng: random.Random,
        key: str,
        device_tags: list[TagDefinition],
    ) -> MachineRuntime:
        """Dựng runtime cho 1 máy theo đặc điểm tag của máy đó."""
        names = {t.tag_name for t in device_tags}
        machine_id = device_tags[0].device if device_tags else key

        ds_tag = next((t for t in device_tags if t.tag_name == "DesignSpeed"), None)
        ds_unit = ((ds_tag.unit or "").strip() if ds_tag else "") or ""
        total_tag = next((t for t in device_tags if t.tag_name == "TotalCounter"), None)
        total_unit = ((total_tag.unit or "").strip() if total_tag else "") or ""
        # Máy phụ (CIP): bộ đếm tính theo "chu kỳ" (cycles), không theo pcs —
        # và KHÔNG phải máy sản xuất (không tính vào OEE của line).
        is_aux = total_unit == "cycles"

        design_speed = self._design_speeds.get(machine_id, 0.0)
        if not design_speed and ds_tag is not None:
            # Chỉ sinh ngẫu nhiên khi máy CÓ tag DesignSpeed — máy không có
            # tag này (vd CIP) thì không có tốc độ dòng.
            lo, hi = _FALLBACK_DESIGN_SPEED.get(ds_unit, (90.0, 140.0))
            design_speed = round(rng.uniform(lo, hi), 3)

        rt = MachineRuntime(rng=rng, design_speed=design_speed, is_aux=is_aux)
        rt.design_unit = ds_unit
        rt.counter_unit = total_unit

        rt.has_good = "GoodCounter" in names
        rt.has_defect = "DefectCounter" in names
        rt.defect_rate = 0.0 if is_aux else round(rng.uniform(_DEFECT_RATE_MIN, _DEFECT_RATE_MAX), 5)
        rt.speed_ratio = round(rng.uniform(_SPEED_RATIO_MEAN - 0.02, _SPEED_RATIO_MEAN + 0.02), 4)
        rt.bottles_per_case = 12 if "CansPerCase" in names else 24
        rt.cases_per_pallet = 40
        rt.head_count = rng.randint(4, 8)

        rt.mtbf_s = round(rng.uniform(_MTBF_MIN_S, _MTBF_MAX_S), 1)
        rt.stop_gap_s = round(rng.uniform(_STOP_GAP_MIN_S, _STOP_GAP_MAX_S), 1)
        rt.maint_gap_s = round(rng.uniform(_MAINT_GAP_MIN_S, _MAINT_GAP_MAX_S), 1)
        rt.min_run_s = round(rng.uniform(_MIN_RUN_MIN_S, _MIN_RUN_MAX_S), 1)
        rt.fault_factor = _AUX_FAULT_FACTOR if is_aux else 1.0

        # Trạng thái khởi đầu: nhà máy đang chạy → phần lớn máy đã RUNNING,
        # vài máy đang khởi động hoặc dừng (để dữ liệu đầu tiên đa dạng).
        roll = rng.random()
        if roll < 0.80:
            rt.state = STATE_RUNNING
            rt.state_elapsed = round(rng.uniform(0.0, 3_600.0), 1)
        elif roll < 0.90:
            rt.state = STATE_STARTING
            rt.next_transition_s = round(rng.uniform(_START_MIN_S, _START_MAX_S), 1)
        else:
            rt.state = STATE_STOPPED
            rt.stop_reason = rng.choice(_STOP_REASONS)
            rt.next_transition_s = round(rng.uniform(_STOP_MIN_S, _STOP_MAX_S), 1)
        rt.mode = MODE_AUTO if rt.state == STATE_RUNNING else MODE_AUTO
        return rt

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
        """Mỗi nhịp: tiến trạng thái máy + sản lượng, rồi phát các tag đã đến hạn.

        Args:
            now: mốc thời gian hiện tại (monotonic).
            dt: khoảng thời gian đã trôi qua (giây).
            advance_state: False → giữ nguyên trạng thái máy (dùng cho test).
        """
        for rt in self._runtimes.values():
            rt.sim_time += dt
            self._drift_speed(rt, dt)
            if advance_state:
                self._advance_state(rt, dt)
            # Bộ đếm luôn theo wall-clock (độc lập advance_state).
            self._advance_production(rt, dt)

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

    def _drift_speed(self, rt: MachineRuntime, dt: float) -> None:
        """Dao động mượt của ``speed_ratio`` quanh 0.96 (mean-reverting).

        Dùng quy trình OU (Ornstein-Uhlenbeck): nhiễu nhỏ + lực kéo về trung
        bình ⇒ dao động mượt, **không** nhấp nháy, và trung bình giữ đúng
        ~0.96 ⇒ Performance của batch luôn hợp lý.
        """
        if rt.state != STATE_RUNNING:
            return
        drift = rt.rng.gauss(0.0, 1.0) * _SPEED_NOISE * dt
        pull = (_SPEED_RATIO_MEAN - rt.speed_ratio) * _SPEED_PULL * dt
        rt.speed_ratio = min(_SPEED_RATIO_MAX,
                             max(_SPEED_RATIO_MIN, rt.speed_ratio + drift + pull))

    def _advance_state(self, rt: MachineRuntime, dt: float) -> None:
        """Chuyển trạng thái máy theo luật §9.1 (có kiểm soát, không flapping)."""
        rt.state_elapsed += dt

        if rt.state == STATE_OFF:
            if rt.state_elapsed >= rt.next_transition_s:
                self._set_state(rt, STATE_STARTING)

        elif rt.state == STATE_STARTING:
            if rt.state_elapsed >= rt.next_transition_s:
                self._set_state(rt, STATE_RUNNING)

        elif rt.state == STATE_RUNNING:
            # Chỉ cho phép dừng/lỗi sau khi chạy đủ lâu (chống flapping).
            if rt.state_elapsed < rt.min_run_s:
                return
            p_fault = dt / max(rt.mtbf_s, 1.0) * rt.fault_factor
            p_stop = dt / max(rt.stop_gap_s, 1.0)
            p_maint = dt / max(rt.maint_gap_s, 1.0)
            roll = rt.rng.random()
            if roll < p_fault:
                self._set_state(rt, STATE_FAULTED)
            elif roll < p_fault + p_stop:
                self._set_state(rt, STATE_STOPPED)
            elif roll < p_fault + p_stop + p_maint:
                self._set_state(rt, STATE_MAINTENANCE)

        elif rt.state == STATE_STOPPED:
            if rt.state_elapsed >= rt.next_transition_s:
                self._set_state(rt, STATE_RUNNING)

        elif rt.state == STATE_FAULTED:
            if rt.state_elapsed >= rt.next_transition_s:
                # 15% lỗi kéo dài → chuyển sang bảo trì thay vì chạy lại luôn.
                if rt.rng.random() < 0.15:
                    self._set_state(rt, STATE_MAINTENANCE)
                else:
                    self._set_state(rt, STATE_RUNNING)

        elif rt.state == STATE_MAINTENANCE:
            if rt.state_elapsed >= rt.next_transition_s:
                # 15% lần bảo trì kết thúc bằng tắt máy (OFF) trước khi chạy lại
                # — phản ánh việc dừng cuối ca / đóng line có thể trở lại.
                if rt.rng.random() < 0.15:
                    self._set_state(rt, STATE_OFF)
                else:
                    self._set_state(rt, STATE_RUNNING)

    def _set_state(self, rt: MachineRuntime, new_state: int) -> None:
        """Chuyển trạng thái và thiết lập lịch cho trạng thái mới."""
        rt.state = new_state
        rt.state_elapsed = 0.0
        rt.state_timer = 0

        # ⚠ Alarm CHỈ tồn tại ở FAULTED — mọi trạng thái khác phải về 0.
        if new_state != STATE_FAULTED:
            rt.alarm_code = 0
            rt.emergency_stop = False
            rt.fault_kind = ""

        if new_state == STATE_STARTING:
            rt.next_transition_s = round(rt.rng.uniform(_START_MIN_S, _START_MAX_S), 1)

        elif new_state == STATE_OFF:
            rt.next_transition_s = round(rt.rng.uniform(_OFF_MIN_S, _OFF_MAX_S), 1)

        elif new_state == STATE_RUNNING:
            rt.next_transition_s = 0.0
            rt.stop_reason = ""

        elif new_state == STATE_STOPPED:
            rt.stop_reason = rt.rng.choice(_STOP_REASONS)
            rt.next_transition_s = round(rt.rng.uniform(_STOP_MIN_S, _STOP_MAX_S), 1)

        elif new_state == STATE_FAULTED:
            rt.fault_kind = rt.rng.choice(list(_FAULT_CODES.keys()))
            rt.alarm_code = _FAULT_CODES[rt.fault_kind]
            rt.emergency_stop = rt.fault_kind == "safety"
            rt.next_transition_s = round(rt.rng.uniform(_REPAIR_MIN_S, _REPAIR_MAX_S), 1)

        elif new_state == STATE_MAINTENANCE:
            rt.next_transition_s = round(rt.rng.uniform(_MAINT_MIN_S, _MAINT_MAX_S), 1)

        # Chế độ điều khiển theo trạng thái.
        if new_state == STATE_MAINTENANCE:
            rt.mode = MODE_MAINTENANCE
        elif new_state == STATE_OFF:
            rt.mode = MODE_OFF
        elif new_state == STATE_STOPPED:
            # Dừng do thao tác tay (người vận hành) thì ở chế độ MANUAL,
            # dừng do hệ thống (kẹt/nguyên liệu) thì vẫn AUTO.
            rt.mode = MODE_MANUAL if rt.stop_reason in ("manual", "operator") else MODE_AUTO
        else:
            rt.mode = MODE_AUTO

    def _advance_production(self, rt: MachineRuntime, dt: float) -> None:
        """Cập nhật bộ đếm theo THỜI GIAN × TỐC ĐỘ (chỉ khi RUNNING).

        Công thức (giữ đúng đơn vị với ``DesignSpeed``):
            ``dTotal = design_speed / 60 × speed_ratio × dt``   [đơn vị/giây]

        ⇒ ``ideal_time_sec = total × 60 / design_speed`` của batch
          = ``speed_ratio × run_sec``  ⇒ Performance ≈ speed_ratio ≈ 0.96.

        Phân bổ NG: mỗi đơn vị sản xuất có xác suất ``defect_rate`` là NG;
        ``good = total - defect`` ⇒ **Total = Good + Defect** luôn đúng.
        """
        if rt.state != STATE_RUNNING:
            return

        if rt.design_speed > 0:
            rate_per_sec = rt.design_speed / 60.0 * rt.speed_ratio
        elif rt.is_aux:
            # CIP: 1 chu kỳ rửa mỗi ``_CIP_CYCLE_S`` giây chạy.
            rate_per_sec = 1.0 / _CIP_CYCLE_S
        else:
            rate_per_sec = 0.0

        if rate_per_sec <= 0:
            return

        produced = rate_per_sec * dt
        rt.prod_fraction += produced
        n = int(rt.prod_fraction)
        if n <= 0:
            return
        rt.prod_fraction -= n
        rt.total += n

        if rt.has_defect and rt.defect_rate > 0:
            rt.defect_fraction += n * rt.defect_rate
            d = int(rt.defect_fraction)
            if d > 0:
                rt.defect_fraction -= d
                rt.defect += min(d, rt.total - rt.defect)
                rt.last_defect_time = rt.sim_time

        # Bất biến nghiệp vụ: Total = Good + Defect.
        rt.good = rt.total - rt.defect

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
