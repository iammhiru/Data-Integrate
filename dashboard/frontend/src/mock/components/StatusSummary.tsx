// ============================================================================
//  StatusSummary — component CHÚ THÍCH trạng thái máy.
//
//  ⚠ YÊU CẦU (12/11): bảng "Đang chạy 20 · Dừng 2 · Lỗi 1 …" KHÔNG được
//    đặt ở HEADER (topbar) — topbar là nơi dành cho điều hướng và trạng thái
//    hệ thống (kết nối, đồng hồ, thông báo). Chú giải trạng thái là thông tin
//    của NỘI DUNG màn hình → nay nằm trong component này.
//
//  ⚠ YÊU CẦU (12/11) — LỖI HÌNH THỨC ĐÃ SỬA:
//    Phiên bản cũ render tất cả trạng thái nằm chung MỘT HÀNG ngang, dot
//    chỉ 8px → nhìn như "lỗi font" (các mảng chữ lệch baseline) và không
//    đọc được. Nay:
//      • Dot TO (10px) + vòng sáng (ring) để nổi bật trên nền sáng.
//      • Layout LƯỚI nhiều cột (`grid`) thay vì một hàng dài.
//      • Mỗi ô là một "thẻ trạng thái" có nhãn + số + mô tả ý nghĩa.
//      • Dùng CHỮ + KÝ HIỆU + MÀU (không chỉ màu) → an toàn cho colorblind.
//
//  Cách dùng:
//    <StatusSummary counts={counts} />              → lưới thẻ trạng thái
//    <StatusSummary counts={counts} variant="compact" /> → dải chip 1 hàng
//    <StatusSummary counts={counts} variant="panel" />   → bảng chú giải đầy đủ
// ============================================================================

import { STATUS_META, type MachineStatus } from "../domain/state";

export type StatusCount = { status: MachineStatus; n: number };

/**
 * Lưới thẻ trạng thái — mặc định.
 *
 * Mỗi thẻ: [dot lớn] [nhãn trạng thái] ......... [số máy]
 *           [mô tả ý nghĩa nghiệp vụ]
 *
 * Lưới co giãn theo bề rộng (`auto-fill` + `minmax`) → không bao giờ tràn
 * ngang, tự xuống hàng khi hẹp.
 */
export function StatusSummary({
  counts,
  variant = "grid",
  title = "Chú giải trạng thái máy",
}: {
  counts: StatusCount[];
  variant?: "grid" | "compact" | "panel";
  title?: string;
}) {
  const visible = counts.filter((c) => c.n > 0);

  if (variant === "compact") {
    return (
      <div className="status-summary status-summary-compact" role="list" aria-label={title}>
        {visible.map((c) => {
          const m = STATUS_META[c.status];
          return (
            <span key={c.status} className="status-summary-chip" role="listitem">
              <i className="status-dot" style={{ background: m.color }} aria-hidden="true" />
              <span>{m.label}</span>
              <b className="num">{c.n}</b>
            </span>
          );
        })}
      </div>
    );
  }

  if (variant === "panel") {
    return (
      <div className="status-legend-panel">
        <div className="status-legend-title">{title}</div>
        <table className="status-legend-table">
          <thead>
            <tr>
              <th scope="col">Trạng thái</th>
              <th scope="col">Số máy</th>
              <th scope="col">Ý nghĩa</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((c) => {
              const m = STATUS_META[c.status];
              return (
                <tr key={c.status}>
                  <td>
                    <span className="status-summary-chip">
                      <i className="status-dot" style={{ background: m.color }} aria-hidden="true" />
                      {m.label}
                    </span>
                  </td>
                  <td className="num">{c.n}</td>
                  <td className="status-legend-desc">{m.hint ?? m.label}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  // ── Mặc định: LƯỚI THẺ TRẠNG THÁI ──────────────────────────────────
  if (visible.length === 0) {
    return (
      <div className="status-summary status-summary-empty">
        <span>Chưa có máy nào trong phạm vi</span>
      </div>
    );
  }

  return (
    <div className="status-summary" role="list" aria-label={title}>
      {visible.map((c) => {
        const m = STATUS_META[c.status];
        return (
          <div
            key={c.status}
            className="status-card"
            role="listitem"
            title={m.hint ?? m.label}
            style={{ ["--st-color" as string]: m.color }}
          >
            <div className="status-card-top">
              {/*
                Dot LỚN + vòng sáng. Vòng sáng (ring) giúp dot nổi bật trên
                nền sáng mà vẫn giữ màu trạng thái làm tín hiệu chính.
              */}
              <i className="status-card-dot" aria-hidden="true">
                <span className="status-card-glyph">{m.glyph}</span>
              </i>
              <span className="status-card-label">{m.label}</span>
              <b className="status-card-count num">{c.n}</b>
            </div>
            <p className="status-card-hint">{m.hint ?? m.label}</p>
          </div>
        );
      })}
    </div>
  );
}
