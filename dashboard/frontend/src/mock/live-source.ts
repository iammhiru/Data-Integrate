// ============================================================================
//  Nguồn dữ liệu THẬT — WebSocket tới `state-api` (FastAPI, nhánh streaming).
//
//  Đường đi của dữ liệu:
//    Kepware/OPC-UA (hoặc middleware-sim)
//      → Kafka `industrial.telemetry`  (1 message = 1 tag đổi)
//      → Spark `machine_state_stream.py` (giữ giá trị mới nhất mỗi máy+tag)
//      → Kafka `machine-state` (compacted)
//      → state-api (FastAPI) đọc topic, giữ trạng thái trong RAM
//      → WebSocket `/ws/machines` → ĐÂY LÀ FILE NÀY
//
//  Giao thức server → client (xem `services/state-api/app.py`):
//    {"type":"snapshot", "ready":bool, "serverTime":str, "machines":[...]}
//    {"type":"patch",    "serverTime":str, "machines":[...]}   // chỉ tag vừa đổi
//    {"type":"heartbeat","serverTime":str, "ready":bool}
//
//  Mỗi máy trong `machines` có shape:
//    { machineId, plantId, lineId, processId, machineType, equipmentCode,
//      sourceSystem, state, stateSince, summary:{...}, tagCount,
//      lastEventTime, ageSeconds, stale,
//      tags: { <tagName>: { value, valueType, unit, statusCode, isGood,
//                            tagCode, tagType, eventTime, emittedAt } } }
//
//  ⚠ VÌ SAO CẦN LỚP NÀY
//    UI dùng mô hình "reading" (values / quality / receivedAt / stale /
//    connection) — cùng shape với `mock-simulator.ts`. Lớp này dịch
//    payload của `state-api` sang đúng shape đó, để `store.ts` và toàn bộ
//    `domain/*` + `pages/*` KHÔNG phải sửa một dòng nào.
//
//  ⚠ ĐIỂM KHÁC BIỆT SO VỚI MOCK (đã xử lý ở đây)
//    1. Tag CHƯA TỪNG có giá trị  → KHÔNG có trong `tags`.
//       → Ta để `values[tag] = null` (không phải 0) đúng nguyên tắc
//         "không đọc được ≠ 0".
//    2. `statusCode` của middleware là Good / Uncertain / Bad.
//       UI dùng "Good" / "Present" → map "Good"→"Good", còn lại giữ nguyên.
//    3. Kết nối theo KÊNH: `state-api` không trả trạng thái kết nối theo
//       channel (đó là khái niệm của lớp connection của Kepware).
//       Ta SUY RA từ độ tươi dữ liệu của các máy trong cùng kênh:
//       máy nào quá ngưỡng stale → kênh "degraded"; mất hết → "offline".
//    4. Bộ đếm thiết bị là TÍCH LUỸ từ lúc bật, không reset theo ca.
//       → Ta lưu MỐC (baseline) lúc kết nối và chỉ dùng phần TĂNG THÊM
//         để tính OEE theo cửa sổ quan sát (xem telemetry-source.ts).
// ============================================================================

import { MACHINES, type MachineDef } from "./catalog.gen";
import type { MockEvent, MockReading } from "./mock-simulator";
import type { ConnectionState } from "./domain/quality";
import { STALE_AFTER_SEC } from "./domain/quality";
import { resolveMachineStatus, type MachineStatus } from "./domain/state";
import type { HistoryPoint, OutputPoint, TelemetrySource } from "./telemetry-source";

// ── Payload của state-api ────────────────────────────────────────────────

export type StateApiTag = {
  value: number | string | boolean | null;
  valueType?: string;
  unit?: string | null;
  statusCode?: string | null;
  isGood?: boolean;
  tagCode?: string | null;
  tagType?: string | null;
  eventTime?: string | null;
  emittedAt?: string | null;
  /** Chỉ có ở tag `MachineState` (Spark ghi kèm). */
  stateName?: string | null;
};

export type StateApiMachine = {
  machineId: string;
  plantId?: string;
  lineId?: string;
  processId?: string;
  machineType?: string;
  equipmentCode?: string;
  sourceSystem?: string;
  state?: string | null;
  stateSince?: string | null;
  summary?: Record<string, unknown>;
  tagCount?: number;
  lastEventTime?: string | null;
  ageSeconds?: number | null;
  stale?: boolean;
  tags?: Record<string, StateApiTag>;
};

export type StateApiMessage =
  | { type: "snapshot"; ready?: boolean; serverTime?: string; machines?: StateApiMachine[] }
  | { type: "patch"; serverTime?: string; machines?: StateApiMachine[] }
  | { type: "heartbeat"; serverTime?: string; ready?: boolean }
  | { type: "error"; message?: string };

// ── Cấu hình ─────────────────────────────────────────────────────────────

/**
 * URL WebSocket của `state-api`.
 *
 * Mặc định dùng proxy của Vite (`/state-api` → `http://localhost:8000`) nên
 * không dính CORS và chạy được cả khi app đóng gói. Có thể ghi đè bằng
 * biến môi trường `VITE_STATE_API_WS` (build-time) — hữu ích khi deploy
 * Docker (khi đó proxy Vite không có).
 */
export const STATE_API_WS_URL: string =
  (import.meta.env.VITE_STATE_API_WS as string | undefined) ??
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/state-api/ws/machines`;

/** Bật/tắt nguồn thật bằng query param hoặc biến môi trường. */
export function liveEnabled(): boolean {
  const q = new URLSearchParams(location.search).get("source");
  if (q === "live") return true;
  if (q === "mock") return false;
  const env = import.meta.env.VITE_DATA_SOURCE as string | undefined;
  return env === "live";
}

// ── Chuẩn hóa chất lượng ─────────────────────────────────────────────────

/**
 * `statusCode` của middleware (Good/Uncertain/Bad) → chuẩn của UI.
 *
 * UI coi "Good" và "Present" là dữ liệu dùng được ("Present" là chuẩn cũ
 * của backend .NET). "Uncertain"/"Bad" → giữ nguyên để hiển thị đúng nhãn.
 */
function normalizeQuality(statusCode: string | null | undefined): string {
  if (!statusCode) return "Unknown";
  const s = statusCode.trim();
  if (s === "Good" || s === "Present") return "Good";
  return s;
}

// ── Nguồn LIVE ───────────────────────────────────────────────────────────

export type LiveStatus = "connecting" | "open" | "closed";

/**
 * Adapter giữ trạng thái hiện tại của 26 máy và phát sự kiện khi có patch.
 *
 * `read()` trả về đúng shape `MockReading` mà `store.ts` đang dùng.
 */
export class LiveSource implements TelemetrySource {
  readonly kind = "live" as const;

  /** Trạng thái kết nối — để nút "Đang kết nối" phản ánh thật. */
  status: LiveStatus = "closed";
  /** Sự kiện phát hiện được từ luồng (đổi trạng thái / bật alarm). */
  private readonly eventLog: MockEvent[] = [];

  private ws: WebSocket | null = null;
  private retry = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  /**
   * "Thế hệ" của kết nối — tăng mỗi lần start/stop.
   * Mọi callback của socket cũ so với `generation` hiện tại → bị bỏ qua,
   * nên StrictMode (mount → unmount → mount) không mở 2 socket cùng lúc.
   */
  private generation = 0;

  /** machineId → tags (chỉ những tag đã từng nhận được giá trị). */
  private machines = new Map<string, StateApiMachine>();
  /** machineId → trạng thái trước đó (để phát hiện đổi trạng thái). */
  private prevState = new Map<string, string | null>();
  /** machineId → alarm code trước đó. */
  private prevAlarm = new Map<string, number | null>();

  // ── Tích phân cửa sổ quan sát ───────────────────────────────────────
  /** Mốc thời gian bắt đầu quan sát (lúc nhận snapshot đầu tiên). */
  private windowStartMs: number | null = null;
  /** machineId → thời điểm bắt đầu chạy liên tục (để tích phân Run Time). */
  private runningSince = new Map<string, number>();
  /** machineId → tổng giây đã chạy (RUNNING) trong cửa sổ. */
  private runMs = new Map<string, number>();
  /** machineId → bộ đếm tại MỐC (baseline) khi bắt đầu cửa sổ. */
  private baseline = new Map<string, { good: number; total: number; defect: number }>();
  /** machineId → trạng thái lần trước (để biết máy đang chạy hay không). */
  private lastStatus = new Map<string, MachineStatus>();

  /** Lịch sử sparkline: machineId/tagName → điểm. */
  private history = new Map<string, HistoryPoint[]>();
  /** Lịch sử sản lượng theo line. */
  private outputHistory = new Map<string, OutputPoint[]>();

  private listeners = new Set<() => void>();

  constructor(private readonly url: string = STATE_API_WS_URL) {}

  /** Đăng ký lắng nghe — gọi mỗi khi có dữ liệu mới. */
  onChange(cb: () => void): () => void {
    this.listeners.add(cb);
    return () => {
      this.listeners.delete(cb);
    };
  }

  start(): void {
    this.stopped = false;
    this.generation += 1;
    this.open(this.generation);
  }

  stop(): void {
    this.stopped = true;
    // Tăng "thế hệ" → mọi callback của socket cũ bị bỏ qua (tránh mở 2
    // socket khi React StrictMode mount/unmount/mount lại trong dev).
    this.generation += 1;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  private emit(): void {
    for (const cb of this.listeners) cb();
  }

  private open(generation: number): void {
    if (this.stopped || generation !== this.generation) return;
    this.status = "connecting";
    this.emit();
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.url);
    } catch {
      this.scheduleRetry(generation);
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      if (generation !== this.generation) {
        ws.close();
        return;
      }
      this.retry = 0;
      this.status = "open";
      this.emit();
      // Ping định kỳ — giữ kết nối sống qua proxy.
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ action: "ping" }));
        }
      }, 20000);
      ws.addEventListener("close", () => clearInterval(ping));
    };

    ws.onmessage = (ev) => {
      if (generation !== this.generation) return;
      let msg: StateApiMessage;
      try {
        msg = JSON.parse(String(ev.data)) as StateApiMessage;
      } catch {
        return; // bỏ qua frame không phải JSON — không được làm hỏng cả stream
      }
      this.handle(msg);
    };

    ws.onerror = () => {
      /* onclose sẽ xử lý */
    };

    ws.onclose = () => {
      if (generation !== this.generation) return; // socket cũ → không đụng state
      this.status = "closed";
      this.emit();
      this.scheduleRetry(generation);
    };
  }

  private scheduleRetry(generation: number): void {
    if (this.stopped || generation !== this.generation) return;
    // Backoff 1s → 2s → 4s → 8s → tối đa 15s.
    const delay = Math.min(15000, 1000 * 2 ** this.retry);
    this.retry += 1;
    this.timer = setTimeout(() => this.open(generation), delay);
  }

  private handle(msg: StateApiMessage): void {
    if (msg.type === "snapshot") {
      // Snapshot = trạng thái đầy đủ → thay thế, không gộp.
      this.machines = new Map();
      for (const m of msg.machines ?? []) {
        this.machines.set(m.machineId, m);
        this.detectEvents(m);
      }
      this.markWindowStart();
      this.emit();
      return;
    }

    if (msg.type === "patch") {
      for (const m of msg.machines ?? []) {
        const prev = this.machines.get(m.machineId);
        if (!prev) {
          this.machines.set(m.machineId, m);
        } else {
          // Patch chỉ chứa tag vừa đổi → gộp vào bản đang có.
          this.machines.set(m.machineId, {
            ...prev,
            ...m,
            tags: { ...(prev.tags ?? {}), ...(m.tags ?? {}) },
          });
        }
        this.detectEvents(m);
      }
      this.emit();
      return;
    }

    // heartbeat / error → không đổi dữ liệu, nhưng vẫn báo cho UI biết
    // server còn sống (để đổi trạng thái nút "Đang kết nối").
    this.emit();
  }

  /**
   * Đánh dấu MỐC cửa sổ quan sát: thời điểm bắt đầu + bộ đếm baseline.
   *
   * Bộ đếm của thiết bị là tích luỹ từ lúc bật → để tính OEE theo cửa sổ
   * quan sát, ta chỉ dùng phần TĂNG THÊM kể từ mốc này.
   */
  private markWindowStart(): void {
    if (this.windowStartMs !== null) return;
    this.windowStartMs = Date.now();
    for (const [mid, m] of this.machines) {
      const tags = m.tags ?? {};
      this.baseline.set(mid, {
        good: numOf(tags.GoodCounter?.value),
        total: numOf(tags.TotalCounter?.value),
        defect: numOf(tags.DefectCounter?.value),
      });
    }
  }

  /**
   * Phát hiện SỰ KIỆN từ luồng thật:
   *   - đổi trạng thái máy (RUNNING → STOPPED …)
   *   - alarm bật lên (AlarmCode 0 → khác 0) hoặc tắt
   *
   * Đây là nguồn sự kiện DUY NHẤT của chế độ thật — không bịa thêm.
   */
  private detectEvents(m: StateApiMachine): void {
    const tags = m.tags ?? {};
    const stateTag = tags.MachineState;
    const alarmTag = tags.AlarmCode;

    const newState = stateTag?.stateName ?? null;
    const oldState = this.prevState.get(m.machineId) ?? null;
    if (stateTag && newState !== oldState) {
      this.prevState.set(m.machineId, newState);
      if (oldState !== null) {
        this.pushEvent({
          machineId: m.machineId,
          equipmentCode: m.equipmentCode ?? m.machineId,
          kind: "state",
          text: `${oldState} → ${newState}`,
          severity:
            newState === "FAULTED" ? "crit" : newState === "STOPPED" ? "warn" : "info",
        });
      }
    }

    if (alarmTag && typeof alarmTag.value === "number") {
      const oldAlarm = this.prevAlarm.get(m.machineId) ?? null;
      this.prevAlarm.set(m.machineId, alarmTag.value);
      if (oldAlarm !== null && oldAlarm === 0 && alarmTag.value !== 0) {
        this.pushEvent({
          machineId: m.machineId,
          equipmentCode: m.equipmentCode ?? m.machineId,
          kind: "alarm",
          text: `Alarm ${alarmTag.value} phát sinh`,
          severity: "crit",
        });
      } else if (oldAlarm !== null && oldAlarm !== 0 && alarmTag.value === 0) {
        this.pushEvent({
          machineId: m.machineId,
          equipmentCode: m.equipmentCode ?? m.machineId,
          kind: "state",
          text: `Alarm ${oldAlarm} đã xóa`,
          severity: "info",
        });
      }
    }
  }

  private pushEvent(e: Omit<MockEvent, "at">): void {
    this.eventLog.unshift({ ...e, at: new Date().toISOString() });
    if (this.eventLog.length > 60) this.eventLog.pop();
  }

  // ── Tích phân Run Time theo trạng thái ────────────────────────────────

  /**
   * Cập nhật Run Time tích luỹ của từng máy theo trạng thái hiện tại.
   *
   * Cách làm: giữ mốc `runningSince` cho máy đang RUNNING. Mỗi lần gọi,
   * nếu máy vẫn RUNNING thì cộng (now − runningSince) và dời mốc.
   * Nếu máy vừa chuyển sang RUNNING → đặt mốc = now (chưa cộng gì).
   */
  private integrate(nowMs: number, reading: MockReading): void {
    for (const def of MACHINES) {
      const values = reading.values[def.machineId] ?? {};
      const quality = reading.quality[def.machineId] ?? {};
      // Tag `MachineState` stale → máy KHÔNG còn chắc là đang chạy → phải
      // ngừng cộng Run Time (giống luật của `resolveMachineStatus`).
      const staleMap = reading.stale[def.machineId] ?? {};
      const staleTags = Object.entries(staleMap)
        .filter(([, v]) => v)
        .map(([k]) => k);

      const status = resolveMachineStatus(values, quality, staleTags);
      const prev = this.lastStatus.get(def.machineId);
      this.lastStatus.set(def.machineId, status);

      const wasRunning = prev === "RUNNING";
      const isRunning = status === "RUNNING";

      if (isRunning) {
        if (!wasRunning) {
          this.runningSince.set(def.machineId, nowMs);
        } else {
          const since = this.runningSince.get(def.machineId) ?? nowMs;
          const delta = Math.max(0, nowMs - since);
          this.runMs.set(def.machineId, (this.runMs.get(def.machineId) ?? 0) + delta);
          this.runningSince.set(def.machineId, nowMs);
        }
      } else {
        this.runningSince.delete(def.machineId);
      }
    }
  }

  // ── TelemetrySource ────────────────────────────────────────────────────

  read(): MockReading {
    const values: MockReading["values"] = {};
    const quality: MockReading["quality"] = {};
    const receivedAt: MockReading["receivedAt"] = {};
    const stale: MockReading["stale"] = {};
    const badQuality: MockReading["badQuality"] = {};
    const connection: MockReading["connection"] = {};

    const nowMs = Date.now();

    for (const def of MACHINES) {
      const m = this.machines.get(def.machineId);
      const tags = m?.tags ?? {};
      const v: Record<string, number | string | boolean | null> = {};
      const q: Record<string, string> = {};
      const st: Record<string, boolean> = {};
      const bq: Record<string, boolean> = {};

      for (const tagDef of def.tags) {
        const rec = tags[tagDef.name];
        if (!rec) {
          // Chưa từng có giá trị → null + quality Unknown (không phải 0).
          v[tagDef.name] = null;
          q[tagDef.name] = "Unknown";
          st[tagDef.name] = true;
          bq[tagDef.name] = false;
          continue;
        }
        v[tagDef.name] = rec.value ?? null;
        const nq = normalizeQuality(rec.statusCode);
        q[tagDef.name] = nq;
        bq[tagDef.name] = nq !== "Good";
        // Tag cũ hơn ngưỡng freshness → coi như KHÔNG có dữ liệu.
        const t = Date.parse(rec.eventTime ?? "");
        st[tagDef.name] = Number.isFinite(t)
          ? nowMs - t > STALE_AFTER_SEC * 1000 * 4
          : false;
      }

      values[def.machineId] = v;
      quality[def.machineId] = q;
      stale[def.machineId] = st;
      badQuality[def.machineId] = bq;
      receivedAt[def.machineId] = m?.lastEventTime ?? new Date(nowMs).toISOString();
    }

    // ── Trạng thái kết nối theo KÊNH (suy ra từ độ tươi) ─────────────
    //
    // `state-api` không báo trạng thái kết nối của từng channel Kepware —
    // đó là khái niệm ở tầng middleware. Ở đây ta dùng tín hiệu khả dụng
    // duy nhất: máy nào trong kênh đã quá ngưỡng stale.
    //
    //   mọi máy kênh đều mới        → "connected"
    //   có máy cũ nhưng còn máy khác → "degraded"
    //   mất kết nối / không có máy nào → "offline"
    const byChannel = new Map<string, { live: number; total: number }>();
    for (const def of MACHINES) {
      const m = this.machines.get(def.machineId);
      const age = m?.ageSeconds;
      const alive = m != null && (age == null || age <= STALE_AFTER_SEC * 4);
      const cur = byChannel.get(def.channel) ?? { live: 0, total: 0 };
      cur.total += 1;
      if (alive) cur.live += 1;
      byChannel.set(def.channel, cur);
    }
    for (const [ch, c] of byChannel) {
      connection[ch] =
        c.live === 0 ? "offline" : c.live < c.total ? "degraded" : "connected";
    }

    const reading: MockReading = {
      values,
      quality,
      receivedAt,
      stale,
      badQuality,
      connection,
    };

    // Tích phân Run Time theo trạng thái hiện tại (chỉ khi đã có mốc).
    if (this.windowStartMs !== null) this.integrate(nowMs, reading);

    return reading;
  }

  get events(): MockEvent[] {
    return this.eventLog;
  }

  historyOf(machineId: string, tagName: string): HistoryPoint[] {
    return this.history.get(`${machineId}/${tagName}`) ?? [];
  }

  outputHistoryOf(lineId: string): OutputPoint[] {
    return this.outputHistory.get(lineId) ?? [];
  }

  record(
    reading: MockReading,
    lineOutputs: { lineId: string; good: number; total: number }[],
  ): void {
    const now = Date.now();
    for (const [machineId, vals] of Object.entries(reading.values)) {
      for (const [tagName, v] of Object.entries(vals)) {
        if (typeof v !== "number") continue;
        const key = `${machineId}/${tagName}`;
        const arr = this.history.get(key) ?? [];
        arr.push({ at: now, value: v });
        if (arr.length > 60) arr.shift();
        this.history.set(key, arr);
      }
    }
    for (const l of lineOutputs) {
      const arr = this.outputHistory.get(l.lineId) ?? [];
      arr.push({ at: now, good: l.good, total: l.total });
      if (arr.length > 90) arr.shift();
      this.outputHistory.set(l.lineId, arr);
    }
  }

  /**
   * Planned Production Time của cửa sổ quan sát (giây).
   *
   * Cửa sổ quan sát = từ lúc mở kết nối → planned = số giây đã trôi.
   * (Khi có job ghi lịch sử vào PG, chuyển sang lấy planned theo ca.)
   */
  plannedSec(nowMs: number): number {
    if (this.windowStartMs === null) return 0;
    return Math.max(0, (nowMs - this.windowStartMs) / 1000);
  }

  /**
   * Run Time của máy trong cửa sổ quan sát (giây) — tích phân từ luồng.
   */
  runTimeSecOf(machineId: string, _status: MachineStatus, nowMs: number): number {
    const accumulated = this.runMs.get(machineId) ?? 0;
    // Máy đang chạy → cộng nốt từ mốc lần gần nhất.
    const since = this.runningSince.get(machineId);
    const live = since != null ? Math.max(0, nowMs - since) : 0;
    return (accumulated + live) / 1000;
  }

  /**
   * Bộ đếm TĂNG THÊM kể từ mốc — dùng cho Total/Good/Defect trong OEE.
   */
  countersOf(machineId: string, _reading: MockReading): {
    good: number | null;
    total: number | null;
    defect: number | null;
  } {
    const m = this.machines.get(machineId);
    const tags = m?.tags ?? {};
    const base = this.baseline.get(machineId) ?? { good: 0, total: 0, defect: 0 };
    const cur = {
      good: numOf(tags.GoodCounter?.value),
      total: numOf(tags.TotalCounter?.value),
      defect: numOf(tags.DefectCounter?.value),
    };
    // Chưa có mốc (chưa nhận snapshot) → trả null để UI hiện "—" thay vì 0.
    if (!this.baseline.has(machineId)) {
      return { good: null, total: null, defect: null };
    }
    return {
      good: Math.max(0, cur.good - base.good),
      total: Math.max(0, cur.total - base.total),
      defect: Math.max(0, cur.defect - base.defect),
    };
  }

  windowLabel(): string {
    return "từ lúc kết nối";
  }

  connectionLabel(): string {
    if (this.status === "open") return "Đang kết nối";
    if (this.status === "connecting") return "Đang nối lại";
    return "Mất kết nối";
  }

  connectionState(): ConnectionState {
    return this.status === "open" ? "connected" : "offline";
  }
}

/** Đọc số từ giá trị tag (null khi không phải số). */
function numOf(v: number | string | boolean | null | undefined): number {
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}
