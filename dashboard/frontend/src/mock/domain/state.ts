// ============================================================================
//  State Resolution Matrix
//  Nguồn: docs/MES_UI_Concept_v1.0.md §C.6
//  Quy ước đã chốt: ĐỎ = LỖI (FAULT), XÁM = DỪNG (STOPPED)
//  ⚠ Thứ tự ưu tiên cần nhà máy phê duyệt trước khi dùng cho alarm.
// ============================================================================

import type { MachineDef, TagDef } from "../catalog.gen";

export type MachineStatus =
  | "RUNNING"
  | "STOPPED"
  | "FAULT"
  | "STARVED"
  | "BLOCKED"
  | "MAINTENANCE"
  | "STARTING"
  | "OFF"
  | "WARNING"
  | "NO_DATA";

export type StatusMeta = {
  key: MachineStatus;
  label: string;
  /** Ký hiệu text — dùng khi màu bị mất (in đen trắng / colorblind). */
  glyph: string;
  color: string;
  bg: string;
  fg: string;
  /** Mức ưu tiên: số nhỏ hơn = nghiêm trọng hơn. */
  severity: number;
  /** Mô tả ý nghĩa — dùng cho bảng chú giải trạng thái. */
  hint?: string;
};

export const STATUS_META: Record<MachineStatus, StatusMeta> = {
  FAULT: {
    key: "FAULT",
    label: "Lỗi",
    glyph: "!",
    color: "var(--state-fault)",
    bg: "var(--state-fault-bg)",
    fg: "var(--state-fault-fg)",
    severity: 1,
    hint: "Máy đang lỗi — cần người phụ trách xử lý",
  },
  MAINTENANCE: {
    key: "MAINTENANCE",
    label: "Bảo trì",
    glyph: "⚒",
    color: "var(--state-maintenance)",
    bg: "var(--state-maintenance-bg)",
    fg: "var(--state-maintenance-fg)",
    severity: 2,
    hint: "Đang bảo trì theo kế hoạch, không tính vào thời gian chạy",
  },
  BLOCKED: {
    key: "BLOCKED",
    label: "Tắc nghẽn",
    glyph: "⊘",
    color: "var(--state-blocked)",
    bg: "var(--state-blocked-bg)",
    fg: "var(--state-blocked-fg)",
    severity: 3,
    hint: "Bị tắc nghẽn — máy không thể đưa sản phẩm đi tiếp",
  },
  STARVED: {
    key: "STARVED",
    label: "Thiếu nguyên liệu",
    glyph: "△",
    color: "var(--state-starved)",
    bg: "var(--state-starved-bg)",
    fg: "var(--state-starved-fg)",
    severity: 4,
    hint: "Thiếu nguyên liệu đầu vào — máy dừng vì không có nguyên liệu",
  },
  WARNING: {
    key: "WARNING",
    label: "Cảnh báo",
    glyph: "⚠",
    color: "var(--state-warning)",
    bg: "var(--state-warning-bg)",
    fg: "var(--state-warning-fg)",
    severity: 5,
    hint: "Có alarm nhưng máy vẫn chạy — cần theo dõi",
  },
  STOPPED: {
    key: "STOPPED",
    label: "Dừng",
    glyph: "■",
    color: "var(--state-stopped)",
    bg: "var(--state-stopped-bg)",
    fg: "var(--state-stopped-fg)",
    severity: 6,
    hint: "Máy dừng có chủ ý — chờ nguyên liệu hoặc chờ lệnh",
  },
  STARTING: {
    key: "STARTING",
    label: "Khởi động",
    glyph: "↻",
    color: "var(--state-starting)",
    bg: "var(--state-starting-bg)",
    fg: "var(--state-starting-fg)",
    severity: 7,
    hint: "Đang khởi động — chưa đạt tốc độ thiết kế",
  },
  RUNNING: {
    key: "RUNNING",
    label: "Đang chạy",
    glyph: "▶",
    color: "var(--state-running)",
    bg: "var(--state-running-bg)",
    fg: "var(--state-running-fg)",
    severity: 8,
    hint: "Đang chạy bình thường trong chế độ tự động",
  },
  OFF: {
    key: "OFF",
    label: "Tắt",
    glyph: "⏻",
    color: "var(--state-off)",
    bg: "var(--state-off-bg)",
    fg: "var(--state-off-fg)",
    severity: 9,
    hint: "Máy tắt — không tham gia sản xuất",
  },
  NO_DATA: {
    key: "NO_DATA",
    label: "Mất dữ liệu",
    glyph: "?",
    color: "var(--state-nodata)",
    bg: "var(--state-nodata-bg)",
    fg: "var(--state-nodata-fg)",
    severity: 10,
    hint: "Không đọc được trạng thái — kiểm tra kết nối hoặc chất lượng dữ liệu",
  },
};

// ── Enum từ middleware (design doc §9.1) ───────────────────────────────
export const MACHINE_STATE = {
  0: "OFF",
  1: "STARTING",
  2: "RUNNING",
  3: "STOPPED",
  4: "FAULTED",
  5: "MAINTENANCE",
} as const;

export const MACHINE_MODE = {
  0: "OFF",
  1: "MANUAL",
  2: "AUTO",
  3: "MAINTENANCE",
} as const;

export type MachineState = keyof typeof MACHINE_STATE;
export type MachineMode = keyof typeof MACHINE_MODE;

export const MACHINE_STATE_LABEL: Record<MachineState, string> = {
  0: "Tắt",
  1: "Khởi động",
  2: "Đang chạy",
  3: "Dừng",
  4: "Lỗi",
  5: "Bảo trì",
};

export const MACHINE_MODE_LABEL: Record<MachineMode, string> = {
  0: "Tắt",
  1: "Thủ công",
  2: "Tự động",
  3: "Bảo trì",
};

/** Giá trị tag → số (null khi không có / null). */
export type TagValue = number | string | boolean | null;

export type MachineReading = {
  /** machineId → tagName → giá trị */
  values: Record<string, TagValue>;
  /** machineId → tagName → chất lượng nguồn */
  quality: Record<string, string>;
  /** machineId → thời điểm nhận gần nhất (ISO) */
  receivedAt: Record<string, string>;
};

/**
 * Suy ra trạng thái máy từ các tag.
 * Thứ tự ưu tiên theo docs/MES_UI_Concept_v1.0.md §C.6.
 */
export function resolveMachineStatus(
  values: Record<string, TagValue>,
  quality: Record<string, string>,
  /** Tag nào đang stale — chỉ `MachineState` stale mới làm mất trạng thái máy. */
  staleTags: string[] = [],
): MachineStatus {
  const state = values.MachineState;
  const mode = values.MachineMode;
  const eStop = values.EmergencyStop === true;
  const starved = values.Starved === true;
  const blocked = values.Blocked === true;
  const alarm = typeof values.AlarmCode === "number" ? values.AlarmCode : 0;

  // 1. Mất dữ liệu — chỉ khi chính tag trạng thái không đọc được.
  if (staleTags.includes("MachineState")) return "NO_DATA";
  if (state == null || state === undefined) {
    const q = quality.MachineState;
    if (q && q !== "Good" && q !== "Present") return "NO_DATA";
    return "NO_DATA";
  }

  // 2. Lỗi
  if (state === 4 || eStop) return "FAULT";
  // 3. Bảo trì
  if (state === 5 || mode === 3) return "MAINTENANCE";
  // 4. Khởi động
  if (state === 1) return "STARTING";
  // 5. Thiếu nguyên liệu / tắc nghẽn (chỉ khi máy vốn đang chạy)
  if (state === 2 && starved) return "STARVED";
  if (state === 2 && blocked) return "BLOCKED";
  // 6. Đang chạy
  if (state === 2) return "RUNNING";
  // 7. Dừng
  if (state === 3) return "STOPPED";
  // 8. Tắt
  if (state === 0) return "OFF";
  // 9. Có alarm nhưng state bình thường
  if (alarm !== 0) return "WARNING";
  return "NO_DATA";
}

/**
 * Ánh xạ mã trạng thái nguyên bản (tag `MachineState`) → trạng thái chuẩn.
 * Mã nguồn: design doc §9.1 — 0=OFF, 1=STARTING, 2=RUNNING, 3=STOPPED,
 * 4=FAULTED, 5=MAINTENANCE.
 */
export function statusFromCode(code: number | undefined): MachineStatus {
  switch (code) {
    case 0:
      return "OFF";
    case 1:
      return "STARTING";
    case 2:
      return "RUNNING";
    case 3:
      return "STOPPED";
    case 4:
      return "FAULT";
    case 5:
      return "MAINTENANCE";
    default:
      return "NO_DATA";
  }
}

/** Trạng thái tổng hợp của line = trạng thái "xấu nhất" trong các máy. */
export function resolveLineStatus(statuses: MachineStatus[]): MachineStatus {
  if (!statuses.length) return "NO_DATA";
  return statuses.reduce((worst, s) =>
    STATUS_META[s].severity < STATUS_META[worst].severity ? s : worst,
  );
}

// ── Nhãn tiếng Việt cho machineType / processId ─────────────────────────
// TODO: nên đưa vào equipment_map.json (master data) để backend/UI dùng chung.
export const MACHINE_TYPE_LABEL: Record<string, string> = {
  PREFORM_FEEDER: "Cấp preform",
  STRETCH_BLOW_MOULDER: "Thổi khuôn",
  AIR_CONVEYOR: "Băng tải khí",
  BOTTLE_RINSER: "Rửa chai",
  CAN_RINSER: "Rửa lon",
  CARBONATED_FILLER: "Chiết có ga",
  STILL_FILLER: "Chiết tĩnh",
  SCREW_CAPPER: "Siết nắp",
  BOTTLE_LABELER: "Dán nhãn",
  DATE_CODER: "In mã ngày",
  CASE_PACKER: "Đóng thùng",
  CAN_DEPALLETIZER: "Khử pallet",
  CAN_FILLER: "Chiết lon",
  CAN_SEAMER: "Hàn seam",
  CAN_INSPECTION: "Kiểm tra lon",
  CIP_SKID: "CIP — rửa CIP",
};

export const PROCESS_LABEL: Record<string, string> = {
  PREFORM_FEEDING: "Cấp preform",
  BLOW_MOULDING: "Thổi khuôn",
  BOTTLE_CONVEYING: "Vận chuyển chai",
  RINSING: "Rửa",
  FILLING: "Chiết rót",
  CAPPING: "Siết nắp",
  LABELLING: "Dán nhãn",
  CODING: "In mã",
  CASE_PACKING: "Đóng thùng",
  CAN_DEPALLETTIZING: "Khử pallet",
  SEAMING: "Hàn seam",
  INSPECTION: "Kiểm tra",
  CIP: "Rửa CIP",
};

/**
 * Thứ tự công đoạn trong một line.
 *
 * ⚠ Vì `processId` dùng chung giữa chai và lon (RINSING/CODING/FILLING),
 *   thứ tự TOÀN CỤC không đủ — cần thứ tự RIÊNG cho từng line.
 *   Đây là điểm cần bổ sung `sequence` vào `catalog.json` khi tích hợp thật
 *   (xem docs/MES_UI_Concept_v1.0.md §B.3).
 */
export const LINE_PROCESS_SEQUENCE: Record<string, string[]> = {
  LINE_01: [
    "PREFORM_FEEDING",
    "BLOW_MOULDING",
    "BOTTLE_CONVEYING",
    "RINSING",
    "FILLING",
    "CAPPING",
    "LABELLING",
    "CODING",
    "CASE_PACKING",
  ],
  LINE_02: [
    "PREFORM_FEEDING",
    "BLOW_MOULDING",
    "BOTTLE_CONVEYING",
    "RINSING",
    "FILLING",
    "CAPPING",
    "LABELLING",
    "CODING",
    "CASE_PACKING",
  ],
  LINE_03: [
    "CAN_DEPALLETTIZING",
    "RINSING",
    "FILLING",
    "SEAMING",
    "CODING",
    "INSPECTION",
    "CASE_PACKING",
  ],
};

/** Thứ tự công đoạn trong một line — suy ra từ `LINE_PROCESS_SEQUENCE`. */
export function processOrder(processId: string, lineId?: string): number {
  if (lineId) {
    const seq = LINE_PROCESS_SEQUENCE[lineId];
    if (seq) {
      const i = seq.indexOf(processId);
      if (i !== -1) return i;
    }
  }
  // Fallback: thứ tự chung (chỉ dùng khi line chưa khai báo trong bảng).
  const global: string[] = [
    "PREFORM_FEEDING",
    "BLOW_MOULDING",
    "CAN_DEPALLETTIZING",
    "BOTTLE_CONVEYING",
    "RINSING",
    "FILLING",
    "CAPPING",
    "SEAMING",
    "LABELLING",
    "CODING",
    "INSPECTION",
    "CASE_PACKING",
  ];
  const i = global.indexOf(processId);
  return i === -1 ? global.length : i;
}

/** Tìm tag theo tên trong danh sách tag của máy. */
export function findTag(tags: TagDef[], name: string): TagDef | undefined {
  return tags.find((t) => t.name === name);
}

/**
 * Đơn vị hiển thị — lấy từ catalog rồi VIẾT LẠI cho dễ đọc.
 * Catalog dùng ký hiệu gốc của thiết bị (degC, uS/cm, m3/h) — hiển thị cho
 * người vận hành nên dùng ký hiệu SI tiếng Việt.
 */
export function displayUnit(unit: string | null | undefined): string | null {
  if (!unit) return null;
  switch (unit) {
    case "degC":
      return "°C";
    case "uS/cm":
      return "µS/cm";
    case "m3/h":
      return "m³/h";
    case "Nm3/h":
      return "Nm³/h";
    case "pH":
      return null; // pH là đơn vị, nhưng đã nằm trong nhãn → không lặp lại
    case "cycles":
      return "chu kỳ";
    // Đơn vị "trên phút" của thiết bị → đổi sang "trên giờ" cho người
    // vận hành đọc quen (nhà máy VN hay dùng pcs/ph, chai/ph, lon/ph…).
    case "preform/min":
      return "preform/ph";
    case "bottles/min":
      return "chai/ph";
    case "cans/min":
      return "lon/ph";
    case "caps/min":
      return "nắp/ph";
    case "pcs/min":
      return "pcs/ph";
    case "cases/min":
      return "thùng/ph";
    case "m/min":
      return "m/ph";
    default:
      return unit;
  }
}

/**
 * Đơn vị hiển thị cho tốc độ — lấy đúng unit của tag `CurrentSpeed` trong
 * catalog, không dùng "đv/ph" chung cho mọi máy (băng tải là m/min,
 * đóng thùng là thùng/ph…).
 */
export function speedUnitLabel(def: MachineDef): string {
  const tag = findTag(def.tags, "CurrentSpeed");
  switch (tag?.unit) {
    case "m/min":
      return "m/ph";
    case "cases/min":
      return "thùng/ph";
    case "preform/min":
      return "preform/ph";
    case "bottles/min":
      return "chai/ph";
    case "cans/min":
      return "lon/ph";
    case "caps/min":
      return "nắp/ph";
    case "pcs/min":
      return "pcs/ph";
    default:
      return "đv/ph";
  }
}
