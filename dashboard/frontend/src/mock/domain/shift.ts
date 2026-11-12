// ============================================================================
//  Ca sản xuất — nguồn: PG master (shift)
//    Planned Production Time = shift.planned_minutes − shift.planned_break_minutes
//    (docs/architecture.txt §6)
//
//  ⚠ BUG ĐÃ SỬA: trước đây mock GHI CỨNG "Ca A · 06:00–14:00" trong khi đồng
//    hồ topbar là 16:16 → thông tin tự mâu thuẫn (work.md §1.2.C: "Timestamp
//    không nhất quán"). Giờ ca được SUY RA từ đồng hồ hệ thống.
//    Khi tích hợp thật: ca do backend trả về trong envelope.
// ============================================================================

export type ShiftId = "A" | "B" | "C";

export type Shift = {
  id: ShiftId;
  label: string;
  /** Giờ bắt đầu (0–23). Ca C qua đêm nên endHour < startHour. */
  startHour: number;
  endHour: number;
  /** Tổng phút của ca. */
  plannedMinutes: number;
  /** Phút nghỉ giải lao, không tính vào Planned Production Time. */
  breakMinutes: number;
};

export const SHIFTS: Shift[] = [
  { id: "A", label: "Ca A", startHour: 6, endHour: 14, plannedMinutes: 480, breakMinutes: 30 },
  { id: "B", label: "Ca B", startHour: 14, endHour: 22, plannedMinutes: 480, breakMinutes: 30 },
  { id: "C", label: "Ca C", startHour: 22, endHour: 6, plannedMinutes: 480, breakMinutes: 30 },
];

/** Ca đang chạy tại thời điểm `date` (theo giờ địa phương của nhà máy). */
export function shiftOf(date: Date = new Date()): Shift {
  const h = date.getHours();
  for (const s of SHIFTS) {
    if (s.startHour < s.endHour) {
      if (h >= s.startHour && h < s.endHour) return s;
    } else if (h >= s.startHour || h < s.endHour) {
      return s; // ca qua đêm
    }
  }
  return SHIFTS[0];
}

/**
 * Số phút ĐÃ TRÔI QUA kể từ đầu ca (0..plannedMinutes).
 * Nếu ca qua đêm và đang ở ngày hôm sau → cộng thêm 24h.
 */
export function shiftElapsedMinutes(date: Date = new Date()): number {
  const s = shiftOf(date);
  const h = date.getHours();
  const m = date.getMinutes();
  let elapsed = h * 60 + m - s.startHour * 60;
  if (s.startHour >= s.endHour && h < s.endHour) elapsed += 24 * 60;
  return Math.max(0, Math.min(s.plannedMinutes, elapsed));
}

/**
 * Phút sản xuất THỰC (đã trừ giờ nghỉ) — đây mới là Planned Production Time
 * dùng làm mẫu số cho Availability.
 */
export function plannedElapsedMinutes(date: Date = new Date()): number {
  const s = shiftOf(date);
  const elapsed = shiftElapsedMinutes(date);
  return Math.max(0, elapsed - Math.min(s.breakMinutes, elapsed));
}

/** Nhãn ca để hiển thị: "Ca B · 14:00–22:00". */
export function shiftLabel(date: Date = new Date()): string {
  const s = shiftOf(date);
  const end = s.endHour;
  return `${s.label} · ${String(s.startHour).padStart(2, "0")}:00–${String(end).padStart(2, "0")}:00`;
}

/**
 * Phần ca đã trôi (0..1) — dùng để tính kế hoạch tích luỹ ("nhịp" / pace).
 * Dùng thời gian SẢN XUẤT THỰC (đã trừ giờ nghỉ) để nhịp khớp thực tế.
 */
export function shiftElapsedRatio(date: Date = new Date()): number {
  const s = shiftOf(date);
  if (s.plannedMinutes <= 0) return 0;
  return Math.min(1, plannedElapsedMinutes(date) / (s.plannedMinutes - s.breakMinutes));
}
