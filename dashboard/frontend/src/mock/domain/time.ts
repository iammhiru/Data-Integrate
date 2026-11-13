// ============================================================================
//  Thời gian — nguồn: dữ liệu middleware là ISO-8601 theo UTC (hệt giờ).
//  UI PHẢI hiển thị theo giờ địa phương của nhà máy, nếu không sẽ lệch 7h
//  so với đồng hồ trên topbar (góp ý work.md §1.2.C — "Timestamp không nhất quán").
//
//  Quy ước: mọi hàm nhận ISO string và trả về chuỗi đã quy đổi sang local time.
// ============================================================================

function toDate(iso: string | undefined | null): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** HH:mm:ss theo giờ địa phương. */
export function fmtClock(iso: string | undefined | null): string {
  const d = toDate(iso);
  if (!d) return "—";
  return d.toLocaleTimeString("vi-VN", { hour12: false });
}

/** HH:mm theo giờ địa phương. */
export function fmtHm(iso: string | undefined | null): string {
  const d = toDate(iso);
  if (!d) return "—";
  return d.toLocaleTimeString("vi-VN", { hour12: false, hour: "2-digit", minute: "2-digit" });
}

/** dd/MM HH:mm theo giờ địa phương. */
export function fmtDateTime(iso: string | undefined | null): string {
  const d = toDate(iso);
  if (!d) return "—";
  const date = d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
  const time = d.toLocaleTimeString("vi-VN", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${date} ${time}`;
}

/** Số giây đã trôi qua kể từ bản ghi cuối cùng (null nếu không có). */
export function ageSeconds(iso: string | undefined | null, nowMs: number): number | null {
  const d = toDate(iso);
  if (!d) return null;
  return Math.max(0, Math.round((nowMs - d.getTime()) / 1000));
}

/** "vừa xong" / "12s trước" / "3 phút trước". */
export function fmtAge(iso: string | undefined | null, nowMs: number): string {
  const s = ageSeconds(iso, nowMs);
  if (s == null) return "—";
  if (s < 5) return "vừa xong";
  if (s < 60) return `${s}s trước`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} phút trước`;
  return `${Math.floor(m / 60)} giờ trước`;
}
