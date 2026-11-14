// ============================================================================
//  ANALYTICS API — đọc OEE / A / P / Q + sản lượng TỪ PostgreSQL.
//
//  ⚠ NGUỒN SỰ THẬT ĐÃ CHUYỂN (14/11/2026):
//    Trước đây màn Plant Overview + Line View TỰ TÍNH OEE trong browser
//    từ WebSocket (`store.ts:computeLineOee`) → số liệu lệch với hệ thống,
//    cửa sổ tính là "từ lúc mở WebSocket" chứ không phải theo lệnh.
//
//    Nay OEE đọc từ `state-api` → PostgreSQL (`machine_kpi_1m`), và TÍNH
//    THEO WORK ORDER ĐANG CHẠY:
//      · Có WO (IN_PROGRESS/PAUSED) → khoảng [actual_start, actual_end ?? now)
//        của LỆNH → đổi lệnh là OEE đổi theo, không dính lệnh cũ.
//      · Không có WO → ca hiện tại (fallback).
//
//  Chu kỳ làm mới: 1 PHÚT (dữ liệu batch cũngng cập nhật ~1 phút/lần).
//  Không cần real-time — người vận hành đọc số theo phút là đủ.
//
//  Công thức (chuẩn Vinamilk, xem `services/state-api/analytics.py`):
//    A = run_sec(máy tham chiếu) / planned_sec(lệnh)
//    P = ideal_time_sec(máy tham chiếu) / run_sec(máy tham chiếu)
//    Q = good_count / total_count
//    OEE = A × P × Q
// ============================================================================

const STATE_BASE = "/state-api";

/** Chu kỳ làm mới — 1 phút (khớp nhịp batch KPI). */
export const ANALYTICS_REFRESH_MS = 60_000;

export type DashboardCounts = {
  total: number;
  good: number;
  defect: number;
  reject: number;
};

export type DashboardWorkOrder = {
  woId: string;
  woCode: string;
  lineId: string;
  productId: string;
  status: string;
  plannedQty: number | null;
  actualStartTime: string | null;
  actualEndTime: string | null;
};

export type DashboardLine = {
  lineId: string;
  lineName: string;
  unit: string | null;
  referenceMachine: string | null;
  /** "work_order" = tính theo lệnh đang chạy; "shift" = fallback theo ca. */
  scope: "work_order" | "shift";
  workOrder: DashboardWorkOrder | null;
  oee: number | null;
  availability: number | null;
  performance: number | null;
  quality: number | null;
  plannedSec: number | null;
  counts: DashboardCounts | null;
  progressRatio: number | null;
};

export type Dashboard = {
  plant: {
    oee: number | null;
    availability: number | null;
    performance: number | null;
    quality: number | null;
    production: DashboardCounts;
    linesWithWorkOrder: number;
  };
  lines: DashboardLine[];
  /** Mốc thời gian batch đã tính đến (ISO). */
  dataUntil: string | null;
  /** Độ trễ (giây) giữa batch và hiện tại. */
  lagSec: number | null;
  lastSuccessAt: string | null;
  formula: string;
};

type RawDashboard = {
  plant: {
    oee: number | null;
    availability: number | null;
    performance: number | null;
    quality: number | null;
    production: DashboardCounts;
    linesWithWorkOrder: number;
  };
  lines: Array<{
    line_id: string;
    line_name: string;
    unit: string | null;
    referenceMachine: string | null;
    scope: "work_order" | "shift";
    workOrder: {
      woId: string;
      woCode: string;
      lineId: string;
      productId: string;
      status: string;
      plannedQty: number | null;
      actualStartTime: string | null;
      actualEndTime: string | null;
    } | null;
    oee: number | null;
    availability: number | null;
    performance: number | null;
    quality: number | null;
    plannedSec: number | null;
    counts: DashboardCounts | null;
    progressRatio: number | null;
  }>;
  dataUntil: string | null;
  lagSec: number | null;
  lastSuccessAt: string | null;
  formula: string;
};

/**
 * Tải KPI dashboard từ PostgreSQL (qua state-api).
 *
 * Trả `null` nếu lỗi — UI sẽ fallback sang số liệu tự tính để không trắng
 * màn hình khi PG tạm thời không sẵn sàng.
 */
export async function loadDashboard(signal?: AbortSignal): Promise<Dashboard | null> {
  try {
    const res = await fetch(`${STATE_BASE}/api/analytics/dashboard`, {
      signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const raw = (await res.json()) as RawDashboard;
    return {
      plant: raw.plant,
      lines: (raw.lines ?? []).map((l) => ({
        lineId: l.line_id,
        lineName: l.line_name,
        unit: l.unit,
        referenceMachine: l.referenceMachine,
        scope: l.scope,
        workOrder: l.workOrder,
        oee: l.oee,
        availability: l.availability,
        performance: l.performance,
        quality: l.quality,
        plannedSec: l.plannedSec,
        counts: l.counts,
        progressRatio: l.progressRatio,
      })),
      dataUntil: raw.dataUntil,
      lagSec: raw.lagSec,
      lastSuccessAt: raw.lastSuccessAt,
      formula: raw.formula,
    };
  } catch (err) {
    // Abort là hủy chủ động (component unmount) → không phải lỗi.
    if (err instanceof DOMException && err.name === "AbortError") return null;
    console.warn("[analytics] không đọc được KPI từ PostgreSQL:", err);
    return null;
  }
}
