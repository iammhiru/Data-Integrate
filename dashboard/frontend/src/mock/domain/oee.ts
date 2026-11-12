// ============================================================================
//  OEE & KPI — công thức lấy từ docs/architecture.txt §6 (đã được duyệt)
//    Availability    = Run Time / Planned Production Time
//    Performance     = (Ideal Cycle Time x Total Count) / Run Time
//    Quality         = Good Count / Total Count
//    OEE             = Availability x Performance x Quality
//    Reject Rate     = Reject Quantity / Total Quantity x 100%
//
//  ⚠ Trong mock, OEE được TÍNH SẴN từ counter của các máy để demo.
//    Khi tích hợp thật, OEE phải lấy từ API (Spark/PG) — không tính lại ở UI.
// ============================================================================

export type OeeComponents = {
  availability: number; // 0..1
  performance: number; // 0..1
  quality: number; // 0..1
  oee: number; // 0..1
};

/**
 * Planned Production Time (giây) — architecture.txt §6:
 *   PlannedProductionTime = shift.planned_minutes − shift.planned_break_minutes
 */
export function plannedProductionSeconds(
  plannedMinutes: number,
  breakMinutes = 0,
): number {
  return Math.max(0, plannedMinutes - breakMinutes) * 60;
}

/**
 * Availability = Run Time / Planned Production Time
 *
 * Với một line gồm N máy: RunTime của line = TỔNG run time của các máy,
 * còn Planned Production Time của line = planned time × N (mỗi máy cần
 * đủ thời gian kế hoạch). Như vậy Availability ≤ 1 và phản ánh đúng việc
 * có bao nhiêu máy thực sự chạy trong thời gian kế hoạch.
 */
export function availabilityOf(
  runTimeSec: number,
  plannedSec: number,
  machineCount: number,
): number {
  if (plannedSec <= 0 || machineCount <= 0) return 0;
  return clamp01(runTimeSec / (plannedSec * machineCount));
}

/**
 * Performance = (Ideal Cycle Time × Total Count) / Run Time
 *
 * @param idealCycleSec chu kỳ lý tưởng (giây/sản phẩm) — nguồn PG master
 *        (`production_run.idealCycleTime`); mock suy ra từ DesignSpeed.
 * @param totalCount     tổng số lượng đã xử lý trong kỳ.
 * @param runTimeSec     thời gian chạy thực tế của máy tham chiếu.
 */
export function performanceOf(
  idealCycleSec: number | null,
  totalCount: number | null,
  runTimeSec: number,
): number | null {
  if (idealCycleSec == null || !Number.isFinite(idealCycleSec) || idealCycleSec <= 0) return null;
  if (totalCount == null || !Number.isFinite(totalCount) || totalCount <= 0) return null;
  if (!Number.isFinite(runTimeSec) || runTimeSec <= 0) return null;
  return clamp01((idealCycleSec * totalCount) / runTimeSec);
}

/** Chu kỳ lý tưởng (giây/sản phẩm) suy ra từ tốc độ thiết kế. */
export function idealCycleFromDesignSpeed(designSpeed: number | null): number | null {
  if (designSpeed == null || !Number.isFinite(designSpeed) || designSpeed <= 0) return null;
  return 60 / designSpeed;
}

export function computeOee(a: number, p: number, q: number): OeeComponents {
  const availability = clamp01(a);
  const performance = clamp01(p);
  const quality = clamp01(q);
  return {
    availability,
    performance,
    quality,
    oee: availability * performance * quality,
  };
}

export function clamp01(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(1, v));
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

/** Yield = Good / Total. Trả null nếu không đủ dữ liệu (không trả 0). */
export function yieldRate(good: number | null, total: number | null): number | null {
  if (good == null || total == null || total <= 0) return null;
  return good / total;
}

export function rejectRate(defect: number | null, total: number | null): number | null {
  if (defect == null || total == null || total <= 0) return null;
  return defect / total;
}
