// ============================================================================
//  ABSTRACTION "NGUÒN DỮ LIỆU" — điểm móc duy nhất giữa UI và nguồn dữ liệu.
//
//  Trước đây `store.ts` nhận thẳng `MockSimulator`. Nay nó nhận một
//  `TelemetrySource` — có 2 lớp cài đặt:
//
//    ① MockSource — dùng `MockSimulator` (mặc định, chạy độc lập)
//    ② LiveSource — WebSocket tới `state-api` (FastAPI) của nhánh streaming
//
//  Mọi `domain/*` và `pages/*` chỉ biết `TelemetryStore` → không phải sửa
//  dòng nào khi đổi nguồn.
//
//  ⚠ HỢP ĐỒNG OEE (rất quan trọng — không được tự bịa)
//    `docs/architecture.txt` §6 định nghĩa OEE theo CA:
//        Availability = Run Time / Planned Production Time
//    Trong chế độ MOCK, "Run Time" và "bộ đếm" đều là số của CẢ CA nên
//    công thức khớp.
//
//    Trong chế độ LIVE, bộ đếm của thiết bị là bộ đếm TÍCH LUỸ từ lúc
//    thiết bị bật (không tự reset theo ca), và Run Time thực tế phải tích
//    phân từ luồng sự kiện. Ta chọn CỬA SỔ QUAN SÁT = từ lúc mở kết nối:
//        · Planned Production Time = số giây đã trôi kể từ lúc kết nối
//        · Run Time                = thời gian máy ở RUNNING (tích phân)
//        · Total Count             = bộ đếm TĂNG THÊM kể từ lúc kết nối
//    Cả ba cùng một cửa sổ → công thức §6 vẫn đúng, không lệch mốc.
//
//    Khi có job ghi lịch sử vào PostgreSQL (chưa có trong repo), OEE sẽ
//    chuyển sang lấy trực tiếp từ API theo ca — khi đó chỉ cần đổi
//    `plannedSec()` / `runTimeSecOf()` của LiveSource.
// ============================================================================

import { MockSimulator, type MockEvent, type MockReading } from "./mock-simulator";
import type { MachineStatus } from "./domain/state";
import { plannedElapsedMinutes } from "./domain/shift";
import { plannedProductionSeconds } from "./domain/oee";

export type HistoryPoint = { at: number; value: number };
export type OutputPoint = { at: number; good: number; total: number };

export type TelemetrySource = {
  /** "mock" | "live" — hiển thị badge tương ứng. */
  readonly kind: "mock" | "live";
  /** Đọc trạng thái hiện tại (shape `MockReading`). */
  read(): MockReading;
  /** Sự kiện gần đây. */
  readonly events: MockEvent[];
  /** Lịch sử điểm cho sparkline. */
  historyOf(machineId: string, tagName: string): HistoryPoint[];
  /** Lịch sử sản lượng theo line (để vẽ Production Trend). */
  outputHistoryOf(lineId: string): OutputPoint[];
  /** Ghi lịch sử sau mỗi lần đọc (sparkline + trend). */
  record(reading: MockReading, lineOutputs: { lineId: string; good: number; total: number }[]): void;
  /**
   * Planned Production Time của CỬA SỔ QUAN SÁT (giây) — mẫu số của
   * Availability.
   */
  plannedSec(nowMs: number): number;
  /**
   * Run Time của một máy trong cửa sổ quan sát (giây).
   * @param status trạng thái hiện tại (mock suy ra từ runFactorOf).
   */
  runTimeSecOf(machineId: string, status: MachineStatus, nowMs: number): number;
  /** Nhãn mô tả cửa sổ quan sát — hiển thị cạnh KPI. */
  windowLabel(): string;
  /**
   * Bộ đếm TRONG CỬA SỔ QUAN SÁT (good / total / defect) của một máy.
   *
   * · Mock  → bộ đếm đã seed theo ca (dùng thẳng).
   * · Live  → bộ đếm tăng thêm kể từ mốc kết nối (bộ đếm thiết bị là
   *            tích luỹ từ lúc bật, không reset theo ca).
   */
  countersOf(machineId: string, reading: MockReading): {
    good: number | null;
    total: number | null;
    defect: number | null;
  };
  /** Trạng thái kết nối tới nguồn. */
  connectionLabel(): string;
  /** Bắt đầu / dừng nguồn. */
  start(): void;
  stop(): void;
  /** Đăng ký nhận thông báo khi có dữ liệu mới. */
  onChange(cb: () => void): () => void;
}

// ── Nguồn MOCK ───────────────────────────────────────────────────────────

/**
 * Bọc `MockSimulator` thành `TelemetrySource`.
 *
 * Không đổi hành vi nào của mock: cửa sổ quan sát vẫn là CA (như §6 yêu
 * cầu) và Run Time vẫn suy ra từ `runFactorOf(status)` — đúng như lúc
 * mock được viết.
 */
export class MockSource implements TelemetrySource {
  readonly kind = "mock" as const;
  readonly sim: MockSimulator;

  constructor(machines?: ConstructorParameters<typeof MockSimulator>[0]) {
    this.sim = new MockSimulator(machines);
  }

  read(): MockReading {
    return this.sim.tick();
  }

  get events(): MockEvent[] {
    return this.sim.events;
  }

  historyOf(machineId: string, tagName: string): HistoryPoint[] {
    return this.sim.historyOf(machineId, tagName);
  }

  outputHistoryOf(lineId: string): OutputPoint[] {
    return this.sim.outputHistoryOf(lineId);
  }

  record(
    reading: MockReading,
    lineOutputs: { lineId: string; good: number; total: number }[],
  ): void {
    for (const [machineId, values] of Object.entries(reading.values)) {
      for (const [tagName, v] of Object.entries(values)) {
        if (typeof v === "number") this.sim.pushHistory(machineId, tagName, v);
      }
    }
    for (const l of lineOutputs) this.sim.pushOutput(l.lineId, l.good, l.total);
  }

  plannedSec(nowMs: number): number {
    // Cửa sổ quan sát = CA (mock): planned = phút sản xuất thực đã trôi.
    return plannedProductionSeconds(plannedElapsedMinutes(new Date(nowMs)));
  }

  runTimeSecOf(_machineId: string, status: MachineStatus, nowMs: number): number {
    // Mock: Run Time = planned × runFactorOf(status) — cùng mô hình với
    // bộ đếm được seed theo ca (xem mock-simulator).
    const factor = RUN_FACTOR[status] ?? 0.15;
    return this.plannedSec(nowMs) * factor;
  }

  windowLabel(): string {
    return "theo ca";
  }

  countersOf(machineId: string, reading: MockReading): {
    good: number | null;
    total: number | null;
    defect: number | null;
  } {
    const v = reading.values[machineId] ?? {};
    const num = (n: string): number | null => {
      const x = v[n];
      return typeof x === "number" ? x : null;
    };
    return {
      good: num("GoodCounter"),
      total: num("TotalCounter"),
      defect: num("DefectCounter"),
    };
  }

  connectionLabel(): string {
    return "Đang kết nối";
  }

  start(): void {
    /* mock không cần gì */
  }

  stop(): void {
    /* mock không cần gì */
  }

  onChange(): () => void {
    return () => {};
  }
}

/** Bảng hệ số thời gian chạy — trùng `domain/runtime.ts` (giữ ở đây để
 *  `MockSource` không phụ thuộc vòng import của UI). */
const RUN_FACTOR: Record<MachineStatus, number> = {
  RUNNING: 1,
  STARTING: 0.85,
  STOPPED: 0.4,
  FAULT: 0.35,
  MAINTENANCE: 0.25,
  STARVED: 0.6,
  BLOCKED: 0.6,
  WARNING: 0.6,
  NO_DATA: 0.15,
  OFF: 0.15,
};
