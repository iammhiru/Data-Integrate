// ============================================================================
//  MASTER DATA — nguồn dữ liệu chuẩn cho UI (dong chay, SKU, ke hoạch, WO).
//
//  Phase 1 (13/11/2026): trước đây UI hard-code `LINE_META` trong `store.ts`
//  (SKU, tên dòng chạy, kế hoạch sản lượng) — sai vị trí, và không khai báo
//  Ideal Cycle Time (không có dữ liệu cho Performance).
//
//  Nay master data đến từ `master-api` (FastAPI :8001), bê phía sau:
//     PostgreSQL (master)  ──┐
//                            ├──> master-api (:8001) ──> frontend
//     config/master_data.json┘
//
//  ⚠ FALLBACK: nếu master-api không chạy, dùng `FALLBACK` bên dưới — giá trị
//    GIỐNG HỆT với hard-code cũ, nên app vẫn chạy được độc lập.
// ============================================================================

import { SHIFTS } from "./domain/shift";

export type MasterWorkOrder = {
  woId: string;
  woCode: string;
  plannedQty: number | null;
  status: string;
  actualStartTime: string | null;
};

export type MasterLine = {
  lineId: string;
  displayName: string;
  sku: string | null;
  productName: string | null;
  /** Chu kỳ lý tưởng (giây/sản phẩm) — mẫu số của Performance. */
  idealCycleTimeSec: number | null;
  /** Kế hoạch sản lượng ca (pcs) — mẫu số của "còn bao nhiêu pcs". */
  plannedQty: number | null;
  /** Công đoạn CHIẾT (ra sản phẩm chính) — lấy bộ đếm của máy này. */
  referenceProcess: string | null;
  unit: string | null;
  workOrder: MasterWorkOrder | null;
};

export type MasterShift = {
  shiftId: string;
  shiftName: string;
  startTime: string;
  endTime: string;
  plannedMinutes: number;
  plannedBreakMinutes: number;
};

export type MasterData = {
  /** "master-api" = đọc từ service; "fallback" = dùng giá trị mặc định. */
  source: "master-api" | "fallback";
  plantId: string;
  shift: MasterShift | null;
  lines: MasterLine[];
};

// ── Fallback ────────────────────────────────────────────────────────────
//
// Giá trị GIỐNG HỆT với hard-code cũ trong `store.ts` (LINE_META) + shift
// trong `domain/shift.ts` — để không đổi hiển thị khi master-api chưa chạy.
const FALLBACK: MasterData = {
  source: "fallback",
  plantId: "PLANT_01",
  shift: null,
  lines: [
    {
      lineId: "LINE_01",
      displayName: "Chai PET — có ga",
      sku: "PET-500-COKE",
      productName: "Nước có ga 500ml",
      idealCycleTimeSec: null,
      plannedQty: 52000,
      referenceProcess: "FILLING",
      unit: "bottles",
      workOrder: null,
    },
    {
      lineId: "LINE_02",
      displayName: "Chai PET — không ga",
      sku: "PET-500-WATER",
      productName: "Nước khoáng 500ml",
      idealCycleTimeSec: null,
      plannedQty: 48000,
      referenceProcess: "FILLING",
      unit: "bottles",
      workOrder: null,
    },
    {
      lineId: "LINE_03",
      displayName: "Lon nhôm",
      sku: "CAN-330-SUGAR",
      productName: "Nước giải khát lon 330ml",
      idealCycleTimeSec: null,
      plannedQty: 45000,
      referenceProcess: "FILLING",
      unit: "cans",
      workOrder: null,
    },
  ],
};

/** Shift từ `domain/shift.ts` (dùng chung khi fallback). */
function fallbackShift(): MasterShift | null {
  const now = new Date();
  const cur = now.getHours() * 60 + now.getMinutes();
  for (const s of SHIFTS) {
    const start = s.startHour * 60;
    const end = s.endHour * 60;
    const inside =
      start < end ? cur >= start && cur < end : cur >= start || cur < end;
    if (inside) {
      return {
        shiftId: s.id,
        shiftName: s.label,
        startTime: `${String(s.startHour).padStart(2, "0")}:00`,
        endTime: `${String(s.endHour).padStart(2, "0")}:00`,
        plannedMinutes: s.plannedMinutes,
        plannedBreakMinutes: s.breakMinutes,
      };
    }
  }
  return null;
}

const FALLBACK_WITH_SHIFT: MasterData = {
  ...FALLBACK,
  shift: fallbackShift(),
};

// ── Fetch ───────────────────────────────────────────────────────────────

/** Timeout fetch — app phải khởi động nhanh, không đợi master-api. */
const FETCH_TIMEOUT_MS = 3000;

type LinesResponse = {
  shift?: {
    shiftId: string;
    shiftName: string;
    startTime: string;
    endTime: string;
    plannedMinutes: number;
    plannedBreakMinutes: number;
  } | null;
  lines?: Array<{
    line_id: string;
    display_name: string;
    sku: string | null;
    productName: string | null;
    idealCycleTimeSec: number | null;
    plannedQty: number | null;
    reference_process: string | null;
    unit: string | null;
    workOrder?: {
      woId: string;
      woCode: string;
      plannedQty: number | null;
      status: string;
      actualStartTime: string | null;
    } | null;
  }>;
};

/**
 * Tải master data. LUÔN trả về dữ liệu hợp lệ — nếu lỗi thì trả fallback.
 *
 * Gọi 1 lần lúc app mount; khi đổi master data cần reload trang.
 */
export async function loadMasterData(): Promise<MasterData> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch("/master-api/api/lines", {
      signal: ctrl.signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as LinesResponse;
    const lines = (data.lines ?? []).map<MasterLine>((l) => ({
      lineId: l.line_id,
      displayName: l.display_name,
      sku: l.sku ?? null,
      productName: l.productName ?? null,
      idealCycleTimeSec: l.idealCycleTimeSec ?? null,
      plannedQty: l.plannedQty ?? null,
      referenceProcess: l.reference_process ?? null,
      unit: l.unit ?? null,
      workOrder: l.workOrder ?? null,
    }));
    if (!lines.length) throw new Error("master-api trả về 0 dòng chạy");
    return {
      source: "master-api",
      plantId: "PLANT_01",
      shift: data.shift ?? null,
      lines,
    };
  } catch (err) {
    console.warn(
      "[master-data] không đọc được master-api, dùng giá trị fallback:",
      err,
    );
    return FALLBACK_WITH_SHIFT;
  } finally {
    clearTimeout(timer);
  }
}
