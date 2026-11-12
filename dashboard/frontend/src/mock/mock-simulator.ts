// ============================================================================
//  MOCK DATA — mô phỏng trực tiếp theo logic simulator của middleware
//  (services/simulator.py + design doc §9.1)
//
//  ⚠ ĐÂY LÀ MOCK. Được đánh dấu rõ bằng badge "MOCK" trên UI và nằm riêng
//    trong thư mục /mock — tách hoàn toàn khỏi đường API thật.
//  Khi tích hợp, thay module này bằng SignalR store.
// ============================================================================

import { MACHINES, type MachineDef } from "./catalog.gen";
import { seedEvents } from "./seed-events";
import type { TagValue } from "./domain/state";
import { statusFromCode } from "./domain/state";
import { runFactorOf } from "./domain/runtime";
import { shiftElapsedMinutes as shiftElapsed, shiftOf, plannedElapsedMinutes } from "./domain/shift";

// ── Enum (design doc §9.1) ───────────────────────────────────────────────
const STATE = { OFF: 0, STARTING: 1, RUNNING: 2, STOPPED: 3, FAULTED: 4, MAINTENANCE: 5 };
const MODE = { OFF: 0, MANUAL: 1, AUTO: 2, MAINTENANCE: 3 };

// ── Hồ sơ đơn vị (giống simulator.py _UNIT_PROFILE) ─────────────────────
const UNIT_PROFILE: Record<string, [number, number]> = {
  "%": [55, 22],
  bar: [3, 0.6],
  degC: [55, 3],
  "Nm3/h": [250, 40],
  "m3/h": [20, 4],
  kPa: [-40, 5],
  mm: [50, 10],
  Nm: [20, 3],
  rpm: [1500, 150],
  kW: [20, 4],
  g: [300, 8],
  s: [12, 2],
  "uS/cm": [400, 80],
  pH: [7.2, 0.2],
  "m/min": [120, 15],
  "bottles/min": [120, 15],
  "preform/min": [120, 15],
  "caps/min": [120, 15],
  "cans/min": [120, 15],
  "pcs/min": [120, 15],
  "cases/min": [20, 4],
};

/**
 * Tốc độ thiết kế theo đúng đơn vị của tag (m/min cho băng tải, cases/min cho
 * đóng thùng…) — nếu dùng chung một con số thì Performance tính sai ngay.
 */
const DESIGN_SPEED_BY_UNIT: Record<string, number> = {
  "preform/min": 130,
  "bottles/min": 120,
  "cans/min": 115,
  "pcs/min": 120,
  "caps/min": 125,
  "m/min": 9,
  "cases/min": 6,
};

/**
 * ═══════════════════════════════════════════════════════════════════════
 *  HỒ SƠ GIÁ TRỊ THEO TÊN TAG — "vỏ có đầy đủ thông tin"
 * ═══════════════════════════════════════════════════════════════════════
 *
 * ⚠ YÊU CẦU (12/11): "máy A có tag B cần hiển thị lên UI thì UI sẽ có sẵn
 *   tag B đấy rồi, chỉ cần mock data là được".
 *
 * `UNIT_PROFILE` chỉ theo ĐƠN VỊ → nhiều tag khác nhau cùng đơn vị bar sẽ
 * nhận CÙNG một giá trị (AirPressure = BlowPressure = 3 bar) — vô lý về mặt
 * nghiệp vụ và làm UI trông như dữ liệu rác.
 *
 * Bảng này gán giá trị riêng cho TỪNG TAG theo đúng ngữ nghĩa thiết bị:
 *   [giá trị nền, biên độ dao động, đơn vị mong đợi (để chống lệch)]
 *
 * Ưu tiên: TAG_PROFILE > TEMP_OVERRIDES > REMAINING_MAX > UNIT_PROFILE.
 * Tất cả tag còn lại rơi về UNIT_PROFILE theo đơn vị (vẫn có số, không null).
 */
const TAG_PROFILE: Record<string, [number, number]> = {
  // ── Nhiệt độ ────────────────────────────────────────────────────────
  MoldTemp: [210, 8],
  HeaterTemp: [185, 6],
  ProductTemp: [8, 0.5],
  WaterTemp: [22, 1],
  RinseWaterTemp: [24, 1],
  TankTemp: [60, 2],

  // ── Áp suất (mỗi công đoạn một giá trị riêng) ──────────────────────
  AirPressure: [1.8, 0.15], // bar — áp suất khí nén băng tải
  BlowPressure: [38, 2.5], // bar — thổi khuôn PET
  CO2Pressure: [4.2, 0.25], // bar — bình CO₂
  FillingPressure: [2.6, 0.12], // bar — áp suất chiết rót
  NozzlePressure: [3.1, 0.15], // bar — vòi rửa
  Pressure: [5.5, 0.3], // bar — áp suất chung CIP
  RinseWaterPressure: [2.2, 0.1], // bar — nước rửa
  SeamPressure: [12, 0.8], // bar — hàn seam
  CanVacuum: [-48, 6], // kPa — chân hút (âm = hút)

  // ── Lưu lượng ───────────────────────────────────────────────────────
  AirFlowRate: [3200, 180], // Nm³/h — khí băng tải
  CO2FlowRate: [65, 6], // Nm³/h — khí CO₂
  FlowRate: [18, 2], // m³/h — CIP
  RinseWaterFlowRate: [42, 4], // m³/h — nước rửa
  WaterConductivity: [380, 40], // µS/cm — độ dẫn nước
  Conductivity: [420, 45], // µS/cm — dung dịch CIP

  // ── Tốc độ ──────────────────────────────────────────────────────────
  CanFeedRate: [115, 8], // lon/ph
  CapFeedRate: [125, 8], // nắp/ph
  PreformFeedRate: [130, 9], // preform/ph
  FillRate: [118, 6], // chai/ph — tốc độ chiết
  MotorSpeed: [1450, 120], // rpm
  CycleTime: [11.5, 0.6], // s — chu kỳ thổi

  // ── Mức / lượng còn lại ────────────────────────────────────────────
  BottleWeight: [28.5, 0.8], // g — khối lượng chai
  NozzleHeight: [42, 2], // mm — chiều cao vòi in
  TankLevel: [64, 8], // % — mực bể CIP
  DefectRate: [1.6, 0.5], // % — tỷ lệ lỗi
  FillLevel: [92, 3], // % — mức chiết
  HopperLevel: [68, 12], // % — mực phễu
  InkLevel: [58, 14], // % — mực in
  ChemicalDose: [4.5, 1.2], // L — liều hóa chất CIP
  pH: [7.2, 0.2], // pH — dung dịch CIP

  // ── Mô-men ──────────────────────────────────────────────────────────
  Torque: [18.5, 1.2], // Nm — mô-men siết nắp
  SeamTorque: [42, 3], // Nm — mô-men hàn seam

  // ── Công suất ──────────────────────────────────────────────────────
  PowerConsumption: [21.5, 3.5], // kW
};

/**
 * Ca sản xuất — nguồn: PG master (shift).
 * ⚠ BUG ĐÃ SỬA: trước đây ghim cứng "Ca A: 06:00–14:00" trong khi đồng hồ
 *   hệ thống là 16:16 → topbar hiển thị "Ca A · 06:00–14:00" lúc đó là SAI.
 *   Nay ca được suy ra từ đồng hồ → thông tin luôn nhất quán.
 */
function shiftElapsedMinutes(now = new Date()): number {
  return shiftElapsed(now);
}

/**
 * Tốc độ sản xuất (pcs/min) của sản phẩm chính trên từng line.
 * LINE_01/02: chai PET 500ml — LINE_03: lon nhôm 330ml.
 */
function productRateOf(m: MachineDef): number {
  if (m.lineId === "LINE_03") return 115; // lon/ph
  return 120; // chai/ph
}

/** Số chai/lon trong một thùng. */
function packSizeOf(m: MachineDef): number {
  return m.lineId === "LINE_03" ? 12 : 24;
}

/**
 * Tốc độ mà bộ đếm TotalCounter của chính máy này đếm (đơn vị pcs/min).
 * Mỗi công đoạn đếm theo đơn vị riêng (preform, nắp, chai…) nên không thể
 * dùng chung một hệ số cho cả line.
 */
function countRateOf(m: MachineDef): number {
  const product = productRateOf(m);
  switch (m.machineType) {
    case "PREFORM_FEEDER":
      return 130; // preform/ph
    case "SCREW_CAPPER":
      return 125; // nắp/ph
    case "AIR_CONVEYOR":
      return product; // băng tải khí — chỉ đếm sản phẩm đi qua
    case "CAN_DEPALLETTIZER":
      return product;
    case "CASE_PACKER":
      return product; // TotalCounter tính theo chai/lon, CaseCount mới tính thùng
    default:
      return product;
  }
}

const TEMP_OVERRIDES: Record<string, [number, number]> = {
  // ⚠ Bản đồ này đã được hợp nhất vào TAG_PROFILE (giữ lại để tương thích
  //   với các script/tool cũ tham chiếu tên hằng này).
  MoldTemp: [210, 8],
  HeaterTemp: [185, 6],
  ProductTemp: [8, 0.5],
  WaterTemp: [22, 1],
  RinseWaterTemp: [24, 1],
  TankTemp: [60, 2],
  DefectRate: [1.6, 0.5],
  FillLevel: [92, 3],
  HopperLevel: [68, 12],
  InkLevel: [58, 14],
  ChemicalDose: [4.5, 1.2],
};

const REMAINING_MAX: Record<string, number> = {
  LabelRollRemaining: 1200,
  FilmRemaining: 800,
};

const INT_CONST: Record<string, number> = {
  BottlesPerCase: 24,
  CansPerCase: 12,
  CavityCount: 2,
  LayerCount: 1,
  RejectReason: 0,
};

const INT_ENUM: Record<string, number> = {
  CaseFormat: 3,
  InspectResult: 2,
  PrintQuality: 2,
  SeamQuality: 2,
  CIPPhase: 4,
};

/**
 * Máy nào luôn ở trạng thái nào — cố ý để demo có đủ tình huống.
 *
 * ⚠ Ghi chú: `CONNECTION_FORCED` mô phỏng KÊNH (channel), không phải máy —
 *   một channel rớt thì mọi máy trên channel đó mất kết nối.
 */
const FORCED_STATE: Record<string, number> = {
  L01_RINSER_01: STATE.STOPPED,
  L01_CODER_01: STATE.FAULTED,
  L02_AIRCONV_01: STATE.MAINTENANCE,
  L03_CANFILLER_01: STATE.STARTING,
  L03_CANDEPAL_01: STATE.STOPPED,
};

/** Channel bị mất kết nối / kết nối yếu — để demo tách 3 chiều trạng thái. */
const CONNECTION_FORCED: Record<string, "degraded" | "offline"> = {
  LINE_03: "degraded",
};

/** Máy bị "đứng" đường truyền (mất bản ghi > ngưỡng freshness). */
const STALE_MACHINES = new Set<string>(["L03_CANCODER_01"]);

/** Độ trễ nhận dữ liệu (giây) — để demo trạng thái "dữ liệu cũ". */
const LAG_SECONDS: Record<string, number> = {
  L03_CANCODER_01: 95,
  L02_LABELER_01: 12,
};

type Runtime = {
  state: number;
  mode: number;
  alarmCode: number;
  total: number;
  good: number;
  defect: number;
  designSpeed: number;
  counters: Record<string, number>;
  phases: Record<string, number>;
  remaining: Record<string, number>;
};

export type MockReading = {
  values: Record<string, Record<string, TagValue>>;
  quality: Record<string, Record<string, string>>;
  receivedAt: Record<string, string>;
  /** Tag nào bị đánh dấu stale (mất dữ liệu) — để demo trạng thái NO_DATA. */
  stale: Record<string, Record<string, boolean>>;
  /** Tag nào quality = Bad — để demo phân biệt null vs 0. */
  badQuality: Record<string, Record<string, boolean>>;
  /** Trạng thái KẾT NỐI theo channel — độc lập với trạng thái máy. */
  connection: Record<string, "connected" | "degraded" | "offline">;
};

export type MockEvent = {
  at: string;
  machineId: string;
  equipmentCode: string;
  kind: "state" | "alarm" | "info";
  text: string;
  severity: "info" | "warn" | "crit";
};

function rng(seed: number): () => number {
  // xorshift32 — deterministic để mock ổn định giữa các lần reload.
  let x = seed || 1;
  return () => {
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    return ((x >>> 0) % 1_000_000) / 1_000_000;
  };
}

function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export class MockSimulator {
  private runtimes = new Map<string, Runtime>();
  private machines: MachineDef[];
  private rand = rng(20261112);
  /** Sự kiện gần đây (mô phỏng) — nguồn cho tab "Sự kiện". */
  events: MockEvent[] = [];
  /** Lịch sử ngắn cho sparkline: machineId → tagName → mảng điểm. */
  history = new Map<string, { at: number; value: number }[]>();
  /** Lịch sử sản lượng theo line (để vẽ Production Trend). */
  outputHistory = new Map<string, { at: number; good: number; total: number }[]>();

  constructor(machines: MachineDef[] = MACHINES) {
    this.machines = machines;
    const elapsed = shiftElapsedMinutes();
    for (const m of machines) {
      const seed = hashSeed(m.machineId);
      const r = rng(seed);

      // Bộ đếm được coi là SẢN LƯỢNG THEO CA (đồng hồ ca được reset mỗi ca —
      // cách phổ biến ở nhà máy, và là điều kiện để so sánh với kế hoạch ca).
      // Giá trị = tốc độ × số phút đã chạy × hiệu suất thực tế.
      //
      // ⚠ Sửa 1: nhân thêm hệ số thời gian CHẠY THỰC TẾ của máy (runFactorOf).
      //   Trước đây mọi máy đều được seed như thể chạy trọn ca, trong khi
      //   RunTime dùng để tính OEE lại phản ánh việc máy đang dừng → Performance
      //   bị kẹt ở 100% và OEE sai. Nay cả hai dùng CÙNG một mô hình thời gian.
      //
      // ⚠ Sửa 2: seed theo THỜI GIAN SẢN XUẤT (đã trừ giờ nghỉ) — cùng mốc
      //   với Planned Production Time dùng làm mẫu số cho Availability/§6.
      //   Nếu seed theo thời gian thô (gồm giờ nghỉ) thì sản lượng luôn vượt
      //   kế hoạch → Performance > 100% → bị kẹt ở trần 100%.
      const rate = countRateOf(m);
      const efficiency = 0.82 + r() * 0.16; // 82–98% hiệu suất thực tế
      const status = statusFromCode(FORCED_STATE[m.machineId] ?? STATE.RUNNING);
      const runFactor = runFactorOf(status);
      const productionMinutes = plannedElapsedMinutes();
      const total = Math.floor(rate * productionMinutes * efficiency * runFactor);

      // Yield thực tế ~97-99.6% → good + defect = total
      const defect = Math.floor(total * (0.004 + r() * 0.026));

      // Bộ đếm đặc trưng (PrintCount, LabelApplyCount, CaseCount, PalletCount…)
      // cũng theo ca, và PHẢI nhất quán với bộ đếm chính của máy.
      const counters: Record<string, number> = {};
      const packSize = packSizeOf(m);
      for (const tag of m.tags) {
        if (tag.tagType !== "COUNTER") continue;
        if (
          (tag.name === "TotalCounter" && tag.unit !== "cycles") ||
          tag.name === "GoodCounter" ||
          tag.name === "DefectCounter"
        )
          continue;
        switch (tag.name) {
          case "PrintCount":
          case "LabelApplyCount":
          case "InspectionCount":
            counters[tag.name] = total; // đếm theo sản phẩm đi qua
            break;
          case "CaseCount":
            counters[tag.name] = Math.floor(total / packSize);
            break;
          case "PalletCount":
            counters[tag.name] = Math.floor(total / packSize / 25); // ~25 thùng/pallet
            break;
          default:
            counters[tag.name] = Math.floor(rate * elapsed * efficiency);
        }
      }
      // CIP: TotalCounter đếm CHU KỲ CIP (đơn vị cycles), không phải sản lượng.
      if (m.machineType === "CIP_SKID") {
        const planned = shiftOf().plannedMinutes;
        counters["TotalCounter"] = Math.floor(elapsed / (planned / 6)); // ~6 chu kỳ/ca
      }

      const speedTag = m.tags.find((t) => t.name === "DesignSpeed");
      const designSpeed = DESIGN_SPEED_BY_UNIT[speedTag?.unit ?? ""] ?? 100;

      this.runtimes.set(m.machineId, {
        state: FORCED_STATE[m.machineId] ?? STATE.RUNNING,
        mode: FORCED_STATE[m.machineId] === STATE.MAINTENANCE ? MODE.MAINTENANCE : MODE.AUTO,
        alarmCode: FORCED_STATE[m.machineId] === STATE.FAULTED ? 417 : 0,
        total,
        good: total - defect,
        defect,
        designSpeed,
        counters,
        phases: {},
        remaining: {},
      });
    }
    this.events = seedEvents();
  }

  /** Sinh snapshot mới cho toàn bộ máy. */
  tick(): MockReading {
    const values: MockReading["values"] = {};
    const quality: MockReading["quality"] = {};
    const receivedAt: MockReading["receivedAt"] = {};
    const stale: MockReading["stale"] = {};
    const badQuality: MockReading["badQuality"] = {};
    const connection: MockReading["connection"] = {};
    const nowMs = Date.now();

    for (const m of this.machines) {
      const rt = this.runtimes.get(m.machineId)!;
      values[m.machineId] = {};
      quality[m.machineId] = {};
      // `receivedAt` là thời điểm ĐỌC ĐƯỢC bản ghi, không phải thời điểm sinh
      // giá trị — máy có độ trễ đường truyền thì bản ghi cũ hơn hiện tại.
      receivedAt[m.machineId] = new Date(
        nowMs - (LAG_SECONDS[m.machineId] ?? 0) * 1000,
      ).toISOString();

      // Trạng thái kết nối theo CHANNEL (kênh truyền), độc lập trạng thái máy.
      connection[m.channel] = CONNECTION_FORCED[m.channel] ?? "connected";

      for (const tag of m.tags) {
        const v = this.generate(rt, tag);
        values[m.machineId][tag.name] = v;

        // Demo: 1 máy có tag quality Bad (hiển thị null, không phải 0)
        const isBad =
          m.machineId === "L02_LABELER_01" && tag.name === "LabelRollRemaining";
        // Tag stale: bản ghi cũ hơn ngưỡng freshness → coi như KHÔNG có dữ liệu.
        const isStale =
          (STALE_MACHINES.has(m.machineId) && tag.name === "InkLevel") ||
          (m.machineId === "L03_CANCODER_01" && tag.name === "MachineState");

        quality[m.machineId][tag.name] = isBad ? "Bad" : "Good";
        stale[m.machineId] = { ...(stale[m.machineId] ?? {}), [tag.name]: isStale };
        badQuality[m.machineId] = {
          ...(badQuality[m.machineId] ?? {}),
          [tag.name]: isBad,
        };
      }
    }
    return { values, quality, receivedAt, stale, badQuality, connection };
  }

  private generate(rt: Runtime, tag: { name: string; dataType: string; unit: string | null }): TagValue {
    const name = tag.name;
    const unit = tag.unit ?? "";

    if (tag.dataType === "Boolean") return this.bool(rt, name);
    if (tag.dataType === "Long") return this.counter(rt, name, unit);
    if (tag.dataType === "Int") return this.int(rt, name);
    return this.float(rt, name, unit);
  }

  private bool(rt: Runtime, name: string): boolean {
    if (name === "EmergencyStop") return rt.state === STATE.FAULTED && this.rand() < 0.5;
    if (name === "Starved") return rt.state === STATE.STOPPED && this.rand() < 0.4;
    if (name === "Blocked") return rt.state === STATE.STOPPED && this.rand() < 0.3;
    if (name === "CirculationOn") return rt.state === STATE.RUNNING;
    if (name === "HeatingOn") return rt.state === STATE.RUNNING;
    if (name === "InkLow" || name === "FilmLow" || name === "HopperLevelLow" || name === "LabelRollLow") {
      return this.rand() < 0.12;
    }
    // ⚠ YÊU CẦU (12/11): các cờ lỗi của thiết bị phải có NGỮ NGHĨA riêng,
    //   không phải "2% ngẫu nhiên" cho tất cả — nếu không UI không phân biệt
    //   được "camera hỏng" với "nắp rơi".
    if (name === "CameraFault") return rt.state === STATE.FAULTED && this.rand() < 0.6;
    if (name === "GripperFault") return rt.state === STATE.FAULTED && this.rand() < 0.5;
    if (name === "TorqueHigh") return rt.state === STATE.RUNNING && this.rand() < 0.08;
    if (name === "CapMissing") return rt.state === STATE.STARTING && this.rand() < 0.25;
    if (name === "LabelMissing") return rt.state === STATE.STARTING && this.rand() < 0.2;
    if (name === "CaseJam") return rt.state === STATE.STOPPED && this.rand() < 0.35;
    return this.rand() < 0.02;
  }

  private int(rt: Runtime, name: string): number {
    if (name === "MachineState") return rt.state;
    if (name === "MachineMode") return rt.mode;
    if (name === "AlarmCode") return rt.alarmCode;
    if (name === "HeadCount") {
      rt.counters[name] = (rt.counters[name] ?? 6) + (rt.state === STATE.RUNNING ? 1 : 0);
      return Math.round(rt.counters[name]);
    }
    if (name in INT_CONST) return INT_CONST[name];
    if (name in INT_ENUM) return INT_ENUM[name];
    return 0;
  }

  private counter(rt: Runtime, name: string, unit: string): number {
    // TotalCounter của CIP đếm chu kỳ CIP (đơn vị cycles), không phải sản lượng.
    if (name === "TotalCounter" && unit !== "cycles") {
      if (rt.state === STATE.RUNNING) rt.total += Math.round(this.rand() * 3);
      return rt.total;
    }
    if (name === "GoodCounter") {
      if (rt.state === STATE.RUNNING) rt.good += Math.round(this.rand() * 3);
      return rt.good;
    }
    if (name === "DefectCounter") {
      if (rt.state === STATE.RUNNING) rt.defect += this.rand() < 0.05 ? 1 : 0;
      return rt.defect;
    }
    // Số lon lỗi seam — tăng chậm hơn DefectCounter (lỗi seam hiếm hơn).
    if (name === "SeamDefectCount") {
      if (rt.state === STATE.RUNNING && this.rand() < 0.02) {
        rt.counters[name] = (rt.counters[name] ?? 0) + 1;
      }
      return rt.counters[name] ?? 0;
    }
    // Bộ đếm đặc trưng: tăng đều theo tốc độ thực tế của máy (mỗi tick = 1s).
    const rate = rt.designSpeed / 60;
    const cur =
      (rt.counters[name] ?? 0) + (rt.state === STATE.RUNNING ? rate * this.rand() : 0);
    rt.counters[name] = cur;
    return Math.round(cur);
  }

  private float(rt: Runtime, name: string, unit: string): number {
    if (name === "DesignSpeed") return round(rt.designSpeed, 1);
    if (name === "CurrentSpeed") {
      if (rt.state !== STATE.RUNNING) return 0;
      const base = TEMP_OVERRIDES[name]?.[0] ?? rt.designSpeed;
      // Dao động LUÔN ở dưới tốc độ thiết kế (92–100%): máy thật không bao giờ
      // vượt thiết kế ổn định. Nếu dao động quanh design speed thì Performance
      // sẽ > 100% → OEE sai (góp ý work.md §1.2.C).
      const wobble = 0.92 + 0.08 * (0.5 + 0.5 * Math.sin(this.phase(rt, name)));
      return round(base * wobble, 2);
    }
    if (name in REMAINING_MAX) {
      const max = REMAINING_MAX[name];
      const cur = (rt.remaining[name] ?? max) - 0.4 * this.rand();
      rt.remaining[name] = cur <= 0 ? max : cur;
      return round(rt.remaining[name], 1);
    }
    const profile =
      TAG_PROFILE[name] ?? TEMP_OVERRIDES[name] ?? UNIT_PROFILE[unit] ?? [50, 10];
    const [base, amp] = profile;
    return round(base + amp * 0.25 * Math.sin(this.phase(rt, name)), 2);
  }

  private phase(rt: Runtime, name: string): number {
    const p = (rt.phases[name] ?? this.rand() * 6.28) + 0.08;
    rt.phases[name] = p;
    return p;
  }

  /** Ghi 1 điểm vào lịch sử (cho sparkline). */
  pushHistory(machineId: string, tagName: string, value: number) {
    const key = `${machineId}/${tagName}`;
    const arr = this.history.get(key) ?? [];
    arr.push({ at: Date.now(), value });
    if (arr.length > 60) arr.shift();
    this.history.set(key, arr);
  }

  historyOf(machineId: string, tagName: string) {
    return this.history.get(`${machineId}/${tagName}`) ?? [];
  }

  /** Ghi 1 điểm sản lượng của line (để vẽ Production Trend). */
  pushOutput(lineId: string, good: number, total: number) {
    const arr = this.outputHistory.get(lineId) ?? [];
    arr.push({ at: Date.now(), good, total });
    if (arr.length > 90) arr.shift();
    this.outputHistory.set(lineId, arr);
  }

  outputHistoryOf(lineId: string) {
    return this.outputHistory.get(lineId) ?? [];
  }

  logEvent(e: MockEvent) {
    this.events.unshift(e);
    if (this.events.length > 60) this.events.pop();
  }
}

function round(v: number, d: number): number {
  const f = 10 ** d;
  return Math.round(v * f) / f;
}
