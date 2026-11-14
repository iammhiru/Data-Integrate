// ============================================================================
//  WORK ORDER API — client cho vong doi lenh san xuat (MES).
//
//  Nguon: master-api (:8001) — service so huu nghiep vu ghi WO.
//
//  Vong doi:
//    DRAFT ──release──▶ RELEASED ──start──▶ IN_PROGRESS ⇄ PAUSED
//                                                │
//                                            complete
//                                                ▼
//                                           COMPLETED
//    DRAFT/RELEASED/IN_PROGRESS ──cancel──▶ CANCELLED
//
//  ⚠ Backend tra snake_case (PostgreSQL) cho `/api/work-orders`.
//    O day chuan hoa ve camelCase de UI dung nhat quan.
// ============================================================================

export type WoStatus =
  | "DRAFT"
  | "RELEASED"
  | "IN_PROGRESS"
  | "PAUSED"
  | "COMPLETED"
  | "CANCELLED";

export type WorkOrder = {
  woId: string;
  woCode: string;
  lineId: string;
  productId: string;
  shiftId: string | null;
  status: WoStatus;
  seq: number;
  plannedQty: number | null;
  unit: string | null;
  plannedStart: string | null;
  plannedEnd: string | null;
  actualStartTime: string | null;
  actualEndTime: string | null;
  releasedAt: string | null;
  releasedBy: string | null;
  operatorId: string | null;
  note: string | null;
  pausedAt: string | null;
  pauseAccumSec: number;
  createdAt: string | null;
  updatedAt: string | null;
  // --- tien do (tu view work_order_progress, co san khi doc qua DB)
  elapsedSec: number | null;
  actualQty: number | null;
  goodQty: number | null;
  defectQty: number | null;
  runSec: number | null;
  stoppedSec: number | null;
  faultedSec: number | null;
  quality: number | null;
  progressRatio: number | null;
};

export type WoLogEntry = {
  logId: number;
  action: string;
  oldStatus: string | null;
  newStatus: string | null;
  actionAt: string;
  actionBy: string | null;
  message: string | null;
  note: string | null;
};

export type WoBaseline = {
  machineId: string;
  tagCode: string;
  baselineValue: number;
  lastRawValue: number | null;
  recordedAt: string | null;
};

/** OEE cua 1 work order (state-api `/api/analytics/wo/{wo_id}`). */
export type WoOee = {
  workOrder: Record<string, unknown> & { wo_code?: string; line_id?: string; product_id?: string };
  started: boolean;
  oee: number | null;
  availability: number | null;
  performance: number | null;
  quality: number | null;
  plannedSec: number | null;
  progressRatio: number | null;
  counts?: { total: number; good: number; defect: number; reject: number };
  time?: { runSec: number; stoppedSec: number; faultedSec: number; maintSec: number };
  items: Array<{
    line_id?: string;
    machine_id?: string;
    machines: number;
    oee: number | null;
    availability: number | null;
    performance: number | null;
    quality: number | null;
    counts: { total: number; good: number; defect: number; reject: number };
    time: Record<string, number>;
  }>;
  plannedTimeRule?: string;
  message?: string;
};

export type CreateWoInput = {
  line_id: string;
  product_id: string;
  planned_qty?: number | null;
  shift_id?: string | null;
  planned_start?: string | null;
  planned_end?: string | null;
  wo_code?: string | null;
  unit?: string | null;
  note?: string | null;
  operator_id?: string | null;
};

// ── Fetch helpers ────────────────────────────────────────────────────────
const MASTER_BASE = "/master-api";
const STATE_BASE = "/state-api";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

/** Chuẩn hoá row snake_case (tu view/DB) -> WorkOrder camelCase. */
function toWo(r: Record<string, unknown>): WorkOrder {
  const num = (v: unknown): number | null =>
    v === null || v === undefined ? null : Number(v);
  return {
    woId: String(r.wo_id ?? ""),
    woCode: String(r.wo_code ?? ""),
    lineId: String(r.line_id ?? ""),
    productId: String(r.product_id ?? ""),
    shiftId: (r.shift_id as string) ?? null,
    status: (r.status as WoStatus) ?? "DRAFT",
    seq: Number(r.seq ?? 0),
    plannedQty: num(r.planned_qty),
    unit: (r.unit as string) ?? null,
    plannedStart: (r.planned_start as string) ?? null,
    plannedEnd: (r.planned_end as string) ?? null,
    actualStartTime: (r.actual_start_time as string) ?? null,
    actualEndTime: (r.actual_end_time as string) ?? null,
    releasedAt: (r.released_at as string) ?? null,
    releasedBy: (r.released_by as string) ?? null,
    operatorId: (r.operator_id as string) ?? null,
    note: (r.note as string) ?? null,
    pausedAt: (r.paused_at as string) ?? null,
    pauseAccumSec: num(r.pause_accum_sec) ?? 0,
    createdAt: (r.created_at as string) ?? null,
    updatedAt: (r.updated_at as string) ?? null,
    elapsedSec: num(r.elapsed_sec),
    actualQty: num(r.actual_qty),
    goodQty: num(r.good_qty),
    defectQty: num(r.defect_qty),
    runSec: num(r.run_sec),
    stoppedSec: num(r.stopped_sec),
    faultedSec: num(r.faulted_sec),
    quality: num(r.quality),
    progressRatio: num(r.progress_ratio),
  };
}

// ── API ───────────────────────────────────────────────────────────────────

/** Danh sach lenh san xuat (loc theo chuyen / trang thai / khoang ngay). */
export async function listWorkOrders(params?: {
  lineId?: string;
  status?: string;
  from?: string;
  to?: string;
}): Promise<WorkOrder[]> {
  const qs = new URLSearchParams();
  if (params?.lineId) qs.set("lineId", params.lineId);
  if (params?.status) qs.set("status", params.status);
  if (params?.from) qs.set("from", params.from);
  if (params?.to) qs.set("to", params.to);
  const q = qs.toString();
  const data = await req<{ workOrders: Array<Record<string, unknown>> }>(
    `${MASTER_BASE}/api/work-orders${q ? `?${q}` : ""}`,
  );
  return (data.workOrders ?? []).map(toWo);
}

/** WO dang chay (IN_PROGRESS/PAUSED) — 1 chuyen = 1 lenh. */
export async function listRunningWorkOrders(lineId?: string): Promise<WorkOrder[]> {
  const qs = lineId ? `?lineId=${encodeURIComponent(lineId)}` : "";
  const data = await req<{ workOrders: Array<Record<string, unknown>> }>(
    `${MASTER_BASE}/api/work-orders/current${qs}`,
  );
  return (data.workOrders ?? []).map(toWo);
}

export async function createWorkOrder(input: CreateWoInput): Promise<WorkOrder> {
  const data = await req<{ workOrder: Record<string, unknown> }>(
    `${MASTER_BASE}/api/work-orders`,
    { method: "POST", body: JSON.stringify(input) },
  );
  return toWo(data.workOrder);
}

export async function updateWorkOrder(
  woId: string,
  input: CreateWoInput,
): Promise<WorkOrder> {
  const data = await req<{ workOrder: Record<string, unknown> }>(
    `${MASTER_BASE}/api/work-orders/${encodeURIComponent(woId)}`,
    { method: "PUT", body: JSON.stringify(input) },
  );
  return toWo(data.workOrder);
}

export type WoAction = "release" | "start" | "pause" | "resume" | "complete" | "cancel";

/** Thuc hien action vong doi (release/start/pause/resume/complete/cancel). */
export async function workOrderAction(
  woId: string,
  action: WoAction,
  payload?: { operator_id?: string | null; note?: string | null },
): Promise<{ workOrder: WorkOrder; baseline?: Record<string, number> }> {
  const data = await req<{
    workOrder: Record<string, unknown>;
    baseline?: Record<string, number>;
  }>(`${MASTER_BASE}/api/work-orders/${encodeURIComponent(woId)}/${action}`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
  return { workOrder: toWo(data.workOrder), baseline: data.baseline };
}

/** Nhat ky hanh dong cua lenh. */
export async function workOrderLog(woId: string): Promise<WoLogEntry[]> {
  const data = await req<{
    logs: Array<Record<string, unknown>>;
  }>(`${MASTER_BASE}/api/work-orders/${encodeURIComponent(woId)}/log`);
  return (data.logs ?? []).map((r) => ({
    logId: Number(r.log_id ?? 0),
    action: String(r.action ?? ""),
    oldStatus: (r.old_status as string) ?? null,
    newStatus: (r.new_status as string) ?? null,
    actionAt: String(r.action_at ?? ""),
    actionBy: (r.action_by as string) ?? null,
    message: (r.message as string) ?? null,
    note: (r.note as string) ?? null,
  }));
}

/** Baseline bo dem cua lenh. */
export async function workOrderBaseline(woId: string): Promise<WoBaseline[]> {
  const data = await req<{
    baselines: Array<Record<string, unknown>>;
  }>(`${MASTER_BASE}/api/work-orders/${encodeURIComponent(woId)}/baseline`);
  return (data.baselines ?? []).map((r) => ({
    machineId: String(r.machine_id ?? ""),
    tagCode: String(r.tag_code ?? ""),
    baselineValue: Number(r.baseline_value ?? 0),
    lastRawValue: r.last_raw_value === null ? null : Number(r.last_raw_value),
    recordedAt: (r.recorded_at as string) ?? null,
  }));
}

/** OEE + san luong cua 1 lenh (state-api). */
export async function workOrderOee(
  woId: string,
  groupBy: "machine" | "line" = "machine",
): Promise<WoOee> {
  return req<WoOee>(
    `${STATE_BASE}/api/analytics/wo/${encodeURIComponent(woId)}?groupBy=${groupBy}`,
  );
}

// ── Hien thi ──────────────────────────────────────────────────────────────

export const WO_STATUS_LABEL: Record<WoStatus, string> = {
  DRAFT: "Nháp",
  RELEASED: "Đã phát hành",
  IN_PROGRESS: "Đang chạy",
  PAUSED: "Tạm dừng",
  COMPLETED: "Hoàn thành",
  CANCELLED: "Đã hủy",
};

/** Mau sac cho badge trang thai. */
export const WO_STATUS_TONE: Record<WoStatus, string> = {
  DRAFT: "draft",
  RELEASED: "released",
  IN_PROGRESS: "running",
  PAUSED: "paused",
  COMPLETED: "done",
  CANCELLED: "cancelled",
};

/** Action nao hop le cho trang thai hien tai (dung de an nut). */
export function allowedActions(status: WoStatus): WoAction[] {
  switch (status) {
    case "DRAFT":
      return ["release", "cancel"];
    case "RELEASED":
      return ["start", "cancel"];
    case "IN_PROGRESS":
      return ["pause", "complete", "cancel"];
    case "PAUSED":
      return ["resume", "complete", "cancel"];
    default:
      return [];
  }
}

export const WO_ACTION_LABEL: Record<WoAction, string> = {
  release: "Phát hành",
  start: "Bắt đầu",
  pause: "Tạm dừng",
  resume: "Tiếp tục",
  complete: "Hoàn thành",
  cancel: "Hủy",
};
