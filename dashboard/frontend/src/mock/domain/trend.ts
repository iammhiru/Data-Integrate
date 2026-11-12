// ============================================================================
//  Trend sản lượng — dựng chung cho Plant Overview và Line View.
//
//  ⚠ BUG ĐÃ SỬA (12/11): "Xu hướng sản lượng" hiện ra HAI ĐƯỜNG THẲNG NGANG
//    HÀNG. Nguyên nhân: trục Y lấy theo "kế hoạch cả ca" (một con số tĩnh)
//    trong khi đường "thực tế" là sản lượng TÍCH LUỸ hiện tại — tỷ lệ
//    giữa hai giá trị quá lớn nên đường thực tế bị nén sát đáy, trông như
//    đường ngang.
//
//  Cách sửa: vẽ CÙNG một trục ngữ nghĩa — trục X = THỜI GIAN ĐÃ TRÔI
//  của ca (0..1), trục Y = SẢN LƯỢNG TÍCH LUỸ (pcs).
//    - "Actual"  = đường thực tế (đi qua các mốc đo thật + gốc đầu ca)
//    - "Plan"    = đường kế hoạch (ramp thẳng từ 0 tới kế hoạch cả ca)
//  Hai đường này LỆCH nhau rõ rệt → người dùng thấy ngay line đang
//  vượt/khác kế hoạch, thay vì hai đường nằm chồng nhau.
// ============================================================================

import { shiftElapsedRatio } from "./shift";

export type TrendPoint = {
  /** 0..1 — phần ca đã trôi. */
  x: number;
  /** Sản lượng tích luỹ (pcs). */
  y: number;
};

/**
 * Chuyển chuỗi mốc đo thô thành điểm trend trên trục "phần ca đã trôi".
 *
 * @param samples  các mốc đo đã sắp xếp tăng dần theo thời gian
 * @param startY   sản lượng tích luỹ tại thời điểm bắt đầu (thường = 0)
 *                 — dùng để nối liền mạch từ đầu ca
 */
export function buildTrendPoints(
  samples: { at: number; good: number }[],
  startY = 0,
): TrendPoint[] {
  const byX = new Map<number, number>();

  for (const s of samples) {
    const ratio = shiftElapsedRatio(new Date(s.at));
    if (ratio <= 0) continue;
    // Nhiều mốc trong cùng một giây → giữ mốc MỚI NHẤT (giá trị mới nhất).
    byX.set(Math.round(ratio * 10000) / 10000, s.good);
  }

  const pts = [...byX.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([x, y]) => ({ x, y }));

  // Nối liền từ đầu ca (0, startY) để đường thực tế có dạng ramp rõ ràng
  // thay vì một đoạn lơ lửng giữa không trung.
  if (pts.length > 0 && (pts[0].x > 0 || startY > 0)) {
    pts.unshift({ x: 0, y: startY });
  }
  return pts;
}

/** Đường kế hoạch: ramp thẳng từ (0,0) tới (1, plan). */
export function planRamp(plan: number): TrendPoint[] {
  return [
    { x: 0, y: 0 },
    { x: 1, y: plan },
  ];
}

/** Giá trị Y tại một điểm X của đường kế hoạch (dùng cho marker "plan to date"). */
export function planAt(plan: number, x: number): number {
  return plan * Math.max(0, Math.min(1, x));
}
