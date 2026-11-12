// ============================================================================
//  Hệ số thời gian CHẠY THỰC TẾ của một máy so với thời gian sản xuất kế hoạch.
//
//  Mô hình của mock: máy được "đóng băng" ở trạng thái hiện tại, nhưng bộ đếm
//  được seed từ ĐẦU CA. Nếu máy đã dừng giữa ca thì bộ đếm phải phản ánh
//  việc nó chỉ chạy được một phần thời gian.
//
//  ⚠ RẤT QUAN TRỌNG: hệ số này được DÙNG CHUNG bởi
//     1. mock-simulator (seed bộ đếm sản lượng)
//     2. store.computeLineOee (tính Run Time → Availability, Performance)
//     Nếu 2 nơi lệch nhau → Performance bị kẹt ở 100% hoặc OEE sai.
//
//  Khi tích hợp thật: Run Time lấy từ Spark batch (sum duration theo status),
//  không cần hệ số này.
// ============================================================================

import type { MachineStatus } from "./state";

/**
 * Phần thời gian sản xuất mà máy thực sự chạy (0..1).
 *
 * - RUNNING      → toàn bộ thời gian sản xuất của ca
 * - STARTING     → phần lớn (máy đang khởi động giữa ca)
 * - STOPPED      → dừng giữa ca (chỉ chạy được phần đầu)
 * - FAULT        → lỗi giữa ca
 * - MAINTENANCE  → bảo trì dài (chỉ chạy được rất ít)
 * - OFF          → không chạy
 */
export function runFactorOf(status: MachineStatus): number {
  switch (status) {
    case "RUNNING":
      return 1;
    case "STARTING":
      return 0.85;
    case "STOPPED":
      return 0.4;
    case "FAULT":
      return 0.35;
    case "MAINTENANCE":
      return 0.25;
    case "STARVED":
    case "BLOCKED":
    case "WARNING":
      return 0.6;
    case "NO_DATA":
    case "OFF":
    default:
      return 0.15;
  }
}
