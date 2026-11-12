// ============================================================================
//  Kế hoạch & tiến độ ca — nguồn kế hoạch: PG master (production_plan)
//
//  Quy tắc hiển thị (work.md §1.2.C — "còn 0 pcs" khi đã vượt kế hoạch):
//    - dưới kế hoạch  → hiện phần còn thiếu
//    - đạt/vượt kế hoạch → hiện phần vượt, KHÔNG hiện "còn 0 pcs"
//
//  ⚠ BỔ SUNG: kế hoạch là của CẢ CA, nhưng người vận hành cần biết "đến
//    thời điểm này nên đạt bao nhiêu" — nếu không, giữa ca luôn thấy "34%"
//    dù line chạy tốt. Vì vậy có thêm `paceProgress()` so với kế hoạch
//    NHÂN VỚI THỜI GIAN ĐÃ TRÔI (pace = kế hoạch tích luỹ tới giờ).
// ============================================================================

export type PlanProgress = {
  /** null khi chưa có nguồn kế hoạch. */
  ratio: number | null;
  /** Đạt được bao nhiêu % kế hoạch. */
  pct: number;
  /** Chênh lệch so với kế hoạch (dương = vượt, âm = thiếu). */
  delta: number;
  over: boolean;
  /** Nhãn chân thực: "còn X pcs" hoặc "vượt X pcs". */
  label: string;
};

export function planProgress(
  actual: number | null | undefined,
  plan: number | null | undefined,
  unit = "pcs",
): PlanProgress | null {
  if (actual == null || plan == null || plan <= 0) return null;
  const delta = actual - plan;
  const over = delta >= 0;
  return {
    ratio: actual / plan,
    pct: Math.round((actual / plan) * 100),
    delta: Math.abs(Math.round(delta)),
    over,
    label: over
      ? `vượt ${fmtPlain(Math.abs(Math.round(delta)))} ${unit}`
      : `còn ${fmtPlain(Math.round(-delta))} ${unit}`,
  };
}

/**
 * Tiến độ theo NHỊP (pace) — so với kế hoạch tích luỹ tới thời điểm hiện tại.
 *
 * @param actual      sản lượng thực tế đã tích luỹ trong ca
 * @param planTotal   kế hoạch cả ca
 * @param elapsedRatio phần ca đã trôi (0..1)
 */
export function paceProgress(
  actual: number | null | undefined,
  planTotal: number | null | undefined,
  elapsedRatio: number,
): PlanProgress | null {
  if (actual == null || planTotal == null || planTotal <= 0) return null;
  if (elapsedRatio <= 0 || elapsedRatio > 1) return null;
  const pace = planTotal * elapsedRatio;
  return planProgress(actual, pace);
}

function fmtPlain(n: number): string {
  return n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
}
