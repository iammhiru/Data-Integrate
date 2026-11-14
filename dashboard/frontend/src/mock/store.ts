// ============================================================================
//  Telemetry store — nguồn dữ liệu cho 4 màn.
//
//  Nguồn được chọn qua `TelemetrySource` (xem `telemetry-source.ts`):
//    · MockSource — dữ liệu giả lập (mặc định)
//    · LiveSource — WebSocket tới `state-api` (FastAPI) của nhánh streaming
//  Toàn bộ `domain/*` + `pages/*` chỉ biết `TelemetryStore` → đổi nguồn
//  không cần sửa UI.
// ============================================================================

import { createContext, useContext } from "react";
import { MACHINES, type MachineDef } from "./catalog.gen";
import { type MockEvent, type MockReading } from "./mock-simulator";
import type { TelemetrySource } from "./telemetry-source";
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
import { computeOee, yieldRate, availabilityOf, performanceOf, idealCycleFromDesignSpeed } from "./domain/oee";
import { shiftOf } from "./domain/shift";
import type { MasterData, MasterLine } from "./master-data";
import type { Dashboard } from "./analytics-api";

export type LineMeta = {
  lineId: string;
  /** Tên tiếng Việt — nguồn: master data (master-api / PG). */
  displayName: string;
  /** SKU đang chạy — nguồn: master data. */
  sku: string | null;
  productName: string | null;
  /** Kế hoạch sản lượng ca — nguồn: master data. */
  plannedQty: number | null;
  /**
   * Chu kỳ lý tưởng (giây/sản phẩm) — nguồn: master data (SKU).
   * Null = chưa có → Performance không tính được, hiển thị "—".
   */
  idealCycleTimeSec: number | null;
  /** Work order đang chạy — nguồn: master data. */
  workOrder: { woId: string; woCode: string; plannedQty: number | null } | null;
  /** Đơn vị sản phẩm (pcs / bottles / cans). */
  unit: string | null;
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
  idealCycleTimeSec: null as number | null,
  workOrder: null as LineMeta["workOrder"],
  unit: null as string | null,
  shift: "Ca hiện tại",
};

/**
 * Master data theo dòng chạy — nguồn: `master-api` (FastAPI :8001), đọc từ
 * PostgreSQL master (hoặc `config/master_data.json` nếu chưa có PG).
 *
 * ⚠ KHÔNG hard-code ở đây nữa (Phase 1, 13/11/2026): trước đây `LINE_META`
 *   chứa cứng SKU / tên dòng / kế hoạch → sai nguồn sự thật và không có
 *   Ideal Cycle Time (Performance tính được nhờ DesignSpeed tạm thời).
 *   Nay UI chỉ đọc; dữ liệu do `tools/gen_master_data.py` sinh từ
 *   `catalog.json` của đồng đội.
 *
 * Nếu `master-api` không chạy → `master-data.ts` trả fallback (giống hệt
 * giá trị hard-code cũ) → app vẫn chạy độc lập.
 */
function lineMetaFromMaster(
  master: MasterData | null,
  lineId: string,
  shiftLabelText: string,
): LineMeta {
  const m: MasterLine | undefined = master?.lines.find((l) => l.lineId === lineId);
  return {
    lineId,
    displayName: m?.displayName ?? lineId,
    sku: m?.sku ?? null,
    productName: m?.productName ?? null,
    plannedQty: m?.plannedQty ?? null,
    idealCycleTimeSec: m?.idealCycleTimeSec ?? null,
    workOrder: m?.workOrder
      ? {
          woId: m.workOrder.woId,
          woCode: m.workOrder.woCode,
          plannedQty: m.workOrder.plannedQty,
        }
      : null,
    unit: m?.unit ?? null,
    shift: shiftLabelText,
  };
}

export type TelemetryStore = {
  reading: MockReading;
  lines: LineView[];
  shared: MachineStateView[];
  events: MockEvent[];
  machines: MachineStateView[];
  byId: (id: string) => MachineStateView | undefined;
  /** Nguồn dữ liệu hiện tại — UI dùng để đổi badge MOCK/LIVE. */
  source: TelemetrySource;
  /** Master data đang dùng (null = chưa tải / fallback). */
  master: MasterData | null;
  /**
   * KPI dashboard đọc từ PostgreSQL (`machine_kpi_1m`), TÍNH THEO WORK ORDER
   * đang chạy. `null` = chưa tải được → UI dùng số liệu tự tính (fallback).
   *
   * ⚠ Đây là nguồn sự thật của OEE/A/P/Q từ 14/11/2026. Xem `analytics-api.ts`.
   */
  dashboard: Dashboard | null;
};

function machineView(
  def: MachineDef,
  reading: MockReading,
  nowMs: number,
  source: TelemetrySource,
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
  // ⚠ Bộ đếm hiển thị phải lấy TỪ NGUỒN, không đọc thẳng `values`.
  //   · Mock → bộ đếm theo ca (như mọi khi).
  //   · Live → bộ đếm TĂNG THÊM trong cửa sổ quan sát (thiết bị tích luỹ từ
  //     lúc bật) → cùng mốc với OEE, không lệch nhau.
  const counters = source.countersOf(def.machineId, reading);
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
    good: counters.good,
    defect: counters.defect,
    total: counters.total,
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
 *    ⚠ TỪ 14/11/2026: hàm này chỉ là FALLBACK. Nguồn sự thật của OEE/A/P/Q
 *      là PostgreSQL (`state-api /api/analytics/dashboard`), TÍNH THEO WORK
 *      ORDER đang chạy — xem `analytics-api.ts`. Số ở đây dùng cửa sổ
 *      "từ lúc mở WebSocket" nên lệch hệ thống (gây OEE 2–4%).
 */
function computeLineOee(
  machines: MachineStateView[],
  nowMs: number,
  source: TelemetrySource,
  reading: MockReading,
  masterLine: MasterLine | undefined,
) {
  // Bộ đếm trong cửa sổ quan sát của từng máy.
  const counters = new Map(
    machines.map((m) => [m.def.machineId, source.countersOf(m.def.machineId, reading)]),
  );

  // Máy có bộ đếm sản phẩm (bỏ qua CIP — chỉ đếm chu kỳ CIP).
  const producers = machines.filter((m) => {
    const c = counters.get(m.def.machineId);
    return c?.total != null && c?.good != null;
  });

  // Máy tham chiếu = công đoạn CHIẾT (nơi ra sản phẩm chính, đơn vị pcs).
  // Không lấy "máy đầu tiên" vì máy đầu có thể đếm preform/nắp — đơn vị khác.
  //
  // ⚠ Phase 1: công đoạn chiết lấy từ MASTER DATA (`line.reference_process`),
  //   không ghim cứng "FILLING" — sau này line làm lon/bao có thể khác.
  const refProcess = masterLine?.referenceProcess ?? "FILLING";
  const ref =
    producers.find((m) => m.def.processId === refProcess) ??
    producers.find((m) => m.def.processId === "FILLING") ??
    producers[0];

  const refCounters = ref ? counters.get(ref.def.machineId) : undefined;
  const total = refCounters?.total ?? 0;
  const good = refCounters?.good ?? 0;

  // ── Availability ────────────────────────────────────────────────────
  // Planned Production Time của line = planned time × số máy.
  //
  // ⚠ RunTime phải dùng CÙNG mô hình thời gian với bộ đếm sản lượng
  //   (mock-simulator dùng runFactorOf theo trạng thái máy). Nếu ở đây tính
  //   RunTime = plannedSec cho mọi máy đang chạy còn bộ đếm thì nhân với
  //   runFactor → Performance = (idealCycle × total)/(runTime) vượt 100% và bị
  //   kẹt ở trần. Vì vậy: RunTime của máy = plannedSec × runFactor(status).
  const plannedSec = source.plannedSec(nowMs);
  const runTimeSec = machines.reduce(
    (sum, m) => sum + source.runTimeSecOf(m.def.machineId, m.status, nowMs),
    0,
  );
  const availability = availabilityOf(runTimeSec, plannedSec, machines.length);

  // ── Performance ──────────────────────────────────────────────────────
  // Ideal Cycle Time: ưu tiên MASTER DATA (`product.ideal_cycle_time_sec` —
  // nguồn sự thật theo SKU). Nếu chưa có master → suy ra tạm từ DesignSpeed
  // của máy tham chiếu (đơn vị pcs/min → giây/pcs).
  //
  // RunTime của MÁY THAM CHIẾU (máy công đoạn chiết) mới là mẫu số — vì
  // Performance đo 1 máy, không đo cả line.
  const refRunTimeSec = ref
    ? source.runTimeSecOf(ref.def.machineId, ref.status, nowMs)
    : 0;
  const idealCycleSec =
    masterLine?.idealCycleTimeSec ?? idealCycleFromDesignSpeed(ref?.speed.design ?? null);
  const performance =
    performanceOf(idealCycleSec, total, refRunTimeSec) ?? 0;

  const quality = yieldRate(good, total) ?? 0;

  return {
    oee: computeOee(availability, performance, quality),
    output: { good, total },
  };
}

export function buildStore(
  source: TelemetrySource,
  master: MasterData | null = null,
  dashboard: Dashboard | null = null,
): TelemetryStore {
  const reading = source.read();
  const nowMs = Date.now();
  const machines = MACHINES.map((m) => machineView(m, reading, nowMs, source));
  const byIdMap = new Map(machines.map((m) => [m.def.machineId, m]));

  // Danh sách dòng chạy: ưu tiên master data (thứ tự do master quyết định),
  // fallback về 3 dòng cố định nếu master chưa có.
  const lineIds =
    master && master.lines.length
      ? master.lines.map((l) => l.lineId)
      : ["LINE_01", "LINE_02", "LINE_03"];

  /** KPI của 1 line từ PostgreSQL (null = chưa có dữ liệu). */
  const dashLine = (lineId: string) =>
    dashboard?.lines.find((l) => l.lineId === lineId) ?? null;

  const lines: LineView[] = lineIds.map((lineId) => {
    const ms = machines.filter((m) => m.def.lineId === lineId);
    const masterLine = master?.lines.find((l) => l.lineId === lineId);
    const computed = computeLineOee(ms, nowMs, source, reading, masterLine);
    const meta: LineMeta = lineMetaFromMaster(master, lineId, shiftOf().label);

    // ── ƯU TIÊN SỐ TỪ PostgreSQL ────────────────────────────────────
    // OEE/A/P/Q lấy từ batch (tính theo WORK ORDER đang chạy). Số liệu tự
    // tính trong browser chỉ là FALLBACK khi PG chưa sẵn sàng — vì nó dùng
    // cửa sổ "từ lúc mở WebSocket" nên lệch với hệ thống (đã gây OEE 2–4%).
    const dl = dashLine(lineId);
    const oee =
      dl && dl.oee != null
        ? {
            availability: dl.availability ?? 0,
            performance: dl.performance ?? 0,
            quality: dl.quality ?? 0,
            oee: dl.oee,
          }
        : computed.oee;
    const output =
      dl && dl.counts
        ? { good: dl.counts.good, total: dl.counts.total }
        : computed.output;

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
    events: source.events,
    machines,
    byId: (id) => byIdMap.get(id),
    source,
    master,
    dashboard,
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
