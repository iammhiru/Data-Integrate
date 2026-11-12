// ============================================================================
//  Mock telemetry store — nguồn dữ liệu cho 3 màn mock
//  Thay thế bằng SignalR store khi tích hợp thật.
// ============================================================================

import { createContext, useContext } from "react";
import { MACHINES, type MachineDef } from "./catalog.gen";
import { MockSimulator, type MockEvent, type MockReading } from "./mock-simulator";
import {
  resolveMachineStatus,
  resolveLineStatus,
  STATUS_META,
  type MachineStatus,
} from "./domain/state";
import {
  freshnessOf,
  type ConnectionState,
  type Freshness,
} from "./domain/quality";
import { computeOee, yieldRate, availabilityOf, performanceOf, plannedProductionSeconds, idealCycleFromDesignSpeed } from "./domain/oee";
import { plannedElapsedMinutes, shiftOf } from "./domain/shift";
import { runFactorOf } from "./domain/runtime";

export type LineMeta = {
  lineId: string;
  /** Tên tiếng Việt — sẽ lấy từ master data PG sau này. */
  displayName: string;
  /** SKU đang chạy — nguồn: PG master. Hiện mock để review layout. */
  sku: string | null;
  productName: string | null;
  /** Kế hoạch sản lượng ca — nguồn: PG master. */
  plannedQty: number | null;
  shift: string;
};

export type MachineStateView = {
  def: MachineDef;
  status: MachineStatus;
  values: Record<string, number | string | boolean | null>;
  quality: Record<string, string>;
  stale: boolean;
  receivedAt: string;
  /** Trạng thái KẾT NỐI của kênh chứa máy (độc lập trạng thái máy). */
  connection: ConnectionState;
  /** Độ tươi của dữ liệu (live / stale / missing). */
  freshness: Freshness;
  /** Tốc độ thực / thiết kế (null nếu máy không có). */
  speed: { current: number | null; design: number | null };
  good: number | null;
  defect: number | null;
  total: number | null;
};

export type LineView = {
  meta: LineMeta;
  machines: MachineStateView[];
  status: MachineStatus;
  connection: ConnectionState;
  oee: { availability: number; performance: number; quality: number; oee: number };
  output: { good: number; total: number };
  plan: number | null;
  /** Số lượng máy theo từng trạng thái — dùng cho "Machine summary". */
  statusCounts: { status: MachineStatus; n: number }[];
};

export const SHARED_META = {
  displayName: "Hệ CIP dùng chung",
  sku: null as string | null,
  productName: null as string | null,
  plannedQty: null as number | null,
  shift: "Ca hiện tại",
};

/**
 * Kế hoạch sản lượng theo ca (pcs) — nguồn thật: bảng `production_plan` trong PG.
 *
 * Giá trị mock được chọn theo công suất thiết kế × thời lượng ca:
 *   LINE_01/02: 120 chai/ph × 480 ph = 57.600 → kế hoạch ~52.000 (OEE mục tiêu 90%)
 *   LINE_03:    115 lon/ph  × 480 ph = 55.200 → kế hoạch ~45.000
 *
 * ⚠ `shift` được gán ĐỘNG khi dựng store (xem buildStore) — không ghim "Ca A",
 *   vì ca hiện tại phụ thuộc đồng hồ nhà máy.
 */
const LINE_META: Record<string, Omit<LineMeta, "shift">> = {
  LINE_01: {
    lineId: "LINE_01",
    displayName: "Chai PET — có ga",
    sku: "PET-500-COKE",
    productName: "Nước có ga 500ml",
    plannedQty: 52000,
  },
  LINE_02: {
    lineId: "LINE_02",
    displayName: "Chai PET — không ga",
    sku: "PET-500-WATER",
    productName: "Nước khoáng 500ml",
    plannedQty: 48000,
  },
  LINE_03: {
    lineId: "LINE_03",
    displayName: "Lon nhôm",
    sku: "CAN-330-SUGAR",
    productName: "Nước giải khát lon 330ml",
    plannedQty: 45000,
  },
};

export type TelemetryStore = {
  reading: MockReading;
  lines: LineView[];
  shared: MachineStateView[];
  events: MockEvent[];
  machines: MachineStateView[];
  byId: (id: string) => MachineStateView | undefined;
  sim: MockSimulator;
};

function machineView(
  def: MachineDef,
  reading: MockReading,
  nowMs: number,
): MachineStateView {
  const values = reading.values[def.machineId] ?? {};
  const quality = reading.quality[def.machineId] ?? {};
  const staleMap = reading.stale[def.machineId] ?? {};
  const staleTags = Object.entries(staleMap)
    .filter(([, v]) => v)
    .map(([k]) => k);
  const status = resolveMachineStatus(values, quality, staleTags);
  const num = (n: string) => {
    const v = values[n];
    return typeof v === "number" ? v : null;
  };
  const receivedAt = reading.receivedAt[def.machineId] ?? new Date(nowMs).toISOString();
  return {
    def,
    status,
    values,
    quality,
    stale: staleTags.length > 0,
    receivedAt,
    connection: reading.connection[def.channel] ?? "connected",
    freshness: freshnessOf(receivedAt, nowMs),
    speed: { current: num("CurrentSpeed"), design: num("DesignSpeed") },
    good: num("GoodCounter"),
    defect: num("DefectCounter"),
    total: num("TotalCounter"),
  };
}

/**
 * Tính OEE của một line — theo đúng công thức §6 architecture.txt:
 *   Availability = Run Time / Planned Production Time
 *   Performance  = (Ideal Cycle Time × Total Count) / Run Time
 *   Quality      = Good Count / Total Count
 *   OEE          = Availability × Performance × Quality
 *
 * Ngữ nghĩa sản lượng: các máy trong cùng dòng xử lý CÙNG số lượng sản phẩm,
 * nên sản lượng của line = bộ đếm của máy "tham chiếu" (công đoạn CHIẾT),
 * KHÔNG phải tổng các bộ đếm (sẽ nhân lên 9 lần).
 *
 * ⚠ BUG ĐÃ SỬA: trước đây Performance tính bằng trung bình (CurrentSpeed /
 *   DesignSpeed) của các máy đang chạy — đây là TỰ BỊA công thức, trái với
 *   §6 và trái prompt.md §4 ("Không tự tạo công thức nghiệp vụ"). Nay dùng
 *   đúng (Ideal Cycle Time × Total Count) / Run Time.
 * ⚠ RunTime của line = TỔNG run time các máy (mỗi máy chạy đồng thời),
 *   còn Planned Production Time = planned × số máy → Availability ≤ 1.
 *
 * ⚠ Trong mock: bộ đếm được coi là sản lượng TÍCH LUỸ của ca.
 *    Khi tích hợp thật, OEE/sản lượng phải lấy từ API (Spark/PG).
 */
function computeLineOee(machines: MachineStateView[], nowMs: number) {
  // Máy có bộ đếm sản phẩm (bỏ qua CIP — chỉ đếm chu kỳ CIP).
  const producers = machines.filter((m) => m.total != null && m.good != null);

  // Máy tham chiếu = công đoạn CHIẾT (nơi ra sản phẩm chính, đơn vị pcs).
  // Không lấy "máy đầu tiên" vì máy đầu có thể đếm preform/nắp — đơn vị khác.
  const ref =
    producers.find((m) => m.def.processId === "FILLING") ?? producers[0];

  const total = ref?.total ?? 0;
  const good = ref?.good ?? 0;

  // ── Availability ────────────────────────────────────────────────────
  // Planned Production Time của line = planned time × số máy.
  //
  // ⚠ RunTime phải dùng CÙNG mô hình thời gian với bộ đếm sản lượng
  //   (mock-simulator dùng runFactorOf theo trạng thái máy). Nếu ở đây tính
  //   RunTime = plannedSec cho mọi máy đang chạy còn bộ đếm thì nhân với
  //   runFactor → Performance = (idealCycle × total)/(runTime) vượt 100% và bị
  //   kẹt ở trần. Vì vậy: RunTime của máy = plannedSec × runFactor(status).
  const plannedMin = plannedElapsedMinutes(new Date(nowMs));
  const plannedSec = plannedProductionSeconds(plannedMin);  const runTimeSec = machines.reduce(
    (sum, m) => sum + plannedSec * runFactorOf(m.status),
    0,
  );
  const availability = availabilityOf(runTimeSec, plannedSec, machines.length);

  // ── Performance ──────────────────────────────────────────────────────
  // Ideal Cycle Time suy ra từ DesignSpeed của máy tham chiếu (nguồn PG master
  // khi tích hợp thật: production_run.idealCycleTime).
  //
  // RunTime của MÁY THAM CHIẾU (máy công đoạn chiết) mới là mẫu số — vì
  // Performance đo 1 máy, không đo cả line.
  const refRunTimeSec = ref ? plannedSec * runFactorOf(ref.status) : 0;
  const idealCycleSec = idealCycleFromDesignSpeed(ref?.speed.design ?? null);
  const performance =
    performanceOf(idealCycleSec, total, refRunTimeSec) ?? 0;

  const quality = yieldRate(good, total) ?? 0;

  return {
    oee: computeOee(availability, performance, quality),
    output: { good, total },
  };
}

export function buildStore(sim: MockSimulator): TelemetryStore {
  const reading = sim.tick();
  const nowMs = Date.now();
  const machines = MACHINES.map((m) => machineView(m, reading, nowMs));
  const byIdMap = new Map(machines.map((m) => [m.def.machineId, m]));

  const lineIds = ["LINE_01", "LINE_02", "LINE_03"];
  const lines: LineView[] = lineIds.map((lineId) => {
    const ms = machines.filter((m) => m.def.lineId === lineId);
    const { oee, output } = computeLineOee(ms, nowMs);
    const meta: LineMeta = { ...LINE_META[lineId], shift: shiftOf().label };
    return {
      meta,
      machines: ms,
      status: resolveLineStatus(ms.map((m) => m.status)),
      connection: reading.connection[lineId] ?? "connected",
      oee,
      output,
      plan: meta.plannedQty,
      statusCounts: countByStatus(ms.map((m) => m.status)),
    };
  });

  const shared = machines.filter((m) => m.def.channel === "SHARED");

  return {
    reading,
    lines,
    shared,
    events: sim.events,
    machines,
    byId: (id) => byIdMap.get(id),
    sim,
  };
}

/** Đếm số máy theo trạng thái, sắp xếp theo mức nghiêm trọng. */
export function countByStatus(
  list: MachineStatus[],
): { status: MachineStatus; n: number }[] {
  const map = new Map<MachineStatus, number>();
  for (const s of list) map.set(s, (map.get(s) ?? 0) + 1);
  return [...map.entries()]
    .map(([status, n]) => ({ status, n }))
    .sort((a, b) => STATUS_META[a.status].severity - STATUS_META[b.status].severity);
}

export const TelemetryContext = createContext<TelemetryStore | null>(null);

export function useTelemetry(): TelemetryStore {
  const ctx = useContext(TelemetryContext);
  if (!ctx) throw new Error("useTelemetry phải nằm trong TelemetryContext.Provider");
  return ctx;
}
