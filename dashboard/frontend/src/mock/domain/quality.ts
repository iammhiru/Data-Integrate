// ============================================================================
//  Data quality — TÁCH 3 CHIỀU ĐỘC LẬP (theo prompt.md §4)
//    1. Machine state  : trạng thái máy (RUNNING / FAULT / ...)
//    2. Connection     : kết nối tới thiết bị (đây là kênh, KHÔNG phải máy)
//    3. Data quality   : chất lượng giá trị (Good / Bad / Stale / Missing)
//
//  ⚠ KHÔNG được suy luận connection state từ machine state, và ngược lại.
//     Ví dụ: máy vẫn RUNNING nhưng kết nối PLC rớt 3 phút → trạng thái máy
//     là "không xác định", dữ liệu là "cũ", kết nối là "yếu".
// ============================================================================

export type ConnectionState = "connected" | "degraded" | "offline";

export type ConnectionMeta = {
  label: string;
  short: string;
  glyph: string;
  color: string;
  bg: string;
  fg: string;
};

export const CONNECTION_META: Record<ConnectionState, ConnectionMeta> = {
  connected: {
    label: "Đang kết nối",
    short: "Kết nối",
    glyph: "●",
    color: "var(--state-running)",
    bg: "var(--state-running-bg)",
    fg: "var(--state-running-fg)",
  },
  degraded: {
    label: "Kết nối yếu",
    short: "Yếu",
    glyph: "◐",
    color: "var(--state-warning)",
    bg: "var(--state-warning-bg)",
    fg: "var(--state-warning-fg)",
  },
  offline: {
    label: "Mất kết nối",
    short: "Mất kết nối",
    glyph: "○",
    color: "var(--state-fault)",
    bg: "var(--state-fault-bg)",
    fg: "var(--state-fault-fg)",
  },
};

/** Độ tươi của dữ liệu — dựa trên tuổi của bản ghi cuối cùng. */
export type Freshness = "live" | "stale" | "missing";

export type FreshnessMeta = {
  label: string;
  glyph: string;
  color: string;
  fg: string;
};

export const FRESHNESS_META: Record<Freshness, FreshnessMeta> = {
  live: { label: "Mới", glyph: "●", color: "var(--state-running)", fg: "var(--state-running-fg)" },
  stale: { label: "Cũ", glyph: "⧗", color: "var(--state-warning)", fg: "var(--state-warning-fg)" },
  missing: {
    label: "Không có",
    glyph: "—",
    color: "var(--state-nodata)",
    fg: "var(--state-nodata-fg)",
  },
};

/** Ngưỡng dữ liệu cũ (giây) — vượt ngưỡng thì coi là STALE. */
export const STALE_AFTER_SEC = 30;

/**
 * Suy ra độ tươi của dữ liệu.
 * @param receivedAtIso thời điểm nhận bản ghi cuối cùng (ISO)
 * @param nowMs         thời điểm hiện tại (ms)
 */
export function freshnessOf(
  receivedAtIso: string | undefined,
  nowMs: number,
): Freshness {
  if (!receivedAtIso) return "missing";
  const t = Date.parse(receivedAtIso);
  if (!Number.isFinite(t)) return "missing";
  const ageSec = (nowMs - t) / 1000;
  if (ageSec > STALE_AFTER_SEC * 4) return "missing";
  if (ageSec > STALE_AFTER_SEC) return "stale";
  return "live";
}
