// ============================================================================
//  MachineGlyph — MINH HỌA MÁY (sticker) dạng SVG.
//
//  ⚠ YÊU CẦU (12/11): card máy trong sơ đồ dòng chảy và popup thiết bị đang
//    trống/không có hình ảnh → người dùng khó hình dung thiết bị. Nay mỗi loại
//    máy có một MINH HỌA SVG riêng (vẽ tay, không phụ thuộc asset ngoài).
//
//  Vẽ theo nguyên tắc:
//    - Dùng `currentColor` → tự đổi màu theo trạng thái máy (ISA-101).
//    - Nét đơn giản, dễ đọc ở kích thước 40–120px.
//    - Không mô tả chi tiết kỹ thuật quá mức — chỉ cần "hình dáng" thiết bị.
// ============================================================================

import type { MachineStatus } from "../domain/state";

export type GlyphKind =
  | "feeder"
  | "blowmoulder"
  | "rinser"
  | "conveyor"
  | "filler"
  | "capper"
  | "labeler"
  | "coder"
  | "casepacker"
  | "depalletizer"
  | "seamer"
  | "inspector"
  | "cip";

const TYPE_TO_GLYPH: Record<string, GlyphKind> = {
  PREFORM_FEEDER: "feeder",
  STRETCH_BLOW_MOULDER: "blowmoulder",
  BOTTLE_RINSER: "rinser",
  CAN_RINSER: "rinser",
  AIR_CONVEYOR: "conveyor",
  CARBONATED_FILLER: "filler",
  STILL_FILLER: "filler",
  CAN_FILLER: "filler",
  SCREW_CAPPER: "capper",
  BOTTLE_LABELER: "labeler",
  DATE_CODER: "coder",
  CASE_PACKER: "casepacker",
  CAN_DEPALLETTIZER: "depalletizer",
  CAN_SEAMER: "seamer",
  CAN_INSPECTION: "inspector",
  CIP_SKID: "cip",
};

export function glyphOf(machineType: string): GlyphKind {
  return TYPE_TO_GLYPH[machineType] ?? "conveyor";
}

/**
 * Minh họa máy.
 *
 * @param size     kích thước cạnh (px)
 * @param status   trạng thái → quyết định màu (xanh = chạy, đỏ = lỗi…)
 * @param muted    dùng màu trung tính (cho vùng trang trí, không mang ý nghĩa
 *                 trạng thái — ví dụ minh họa trong drawer thiết bị)
 */
export function MachineGlyph({
  machineType,
  size = 48,
  status,
  muted = false,
  className,
}: {
  machineType: string;
  size?: number;
  status?: MachineStatus;
  muted?: boolean;
  className?: string;
}) {
  const kind = glyphOf(machineType);
  const color = muted ? "var(--text-secondary)" : statusColor(status);

  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      stroke={color}
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label={`Minh họa thiết bị ${machineType}`}
    >
      {renderGlyph(kind, color)}
    </svg>
  );
}

function statusColor(status?: MachineStatus): string {
  switch (status) {
    case "RUNNING":
      return "var(--state-running)";
    case "FAULT":
      return "var(--state-fault)";
    case "MAINTENANCE":
      return "var(--state-maintenance)";
    case "STOPPED":
      return "var(--state-stopped)";
    case "STARTING":
      return "var(--state-starting)";
    case "STARVED":
      return "var(--state-starved)";
    case "BLOCKED":
      return "var(--state-blocked)";
    case "WARNING":
      return "var(--state-warning)";
    case "OFF":
      return "var(--state-off)";
    case "NO_DATA":
      return "var(--state-nodata)";
    default:
      return "var(--text-secondary)";
  }
}

/** Màu nền nền của "sticker" — dùng cho ô minh họa. */
export function glyphBg(status?: MachineStatus, muted = false): string {
  if (muted) return "var(--bg-raised)";
  switch (status) {
    case "RUNNING":
      return "var(--state-running-bg)";
    case "FAULT":
      return "var(--state-fault-bg)";
    case "MAINTENANCE":
      return "var(--state-maintenance-bg)";
    case "STOPPED":
      return "var(--state-stopped-bg)";
    case "STARTING":
      return "var(--state-starting-bg)";
    case "STARVED":
      return "var(--state-starved-bg)";
    case "BLOCKED":
      return "var(--state-blocked-bg)";
    case "WARNING":
      return "var(--state-warning-bg)";
    default:
      return "var(--bg-raised)";
  }
}

function renderGlyph(kind: GlyphKind, color: string) {
  switch (kind) {
    case "feeder":
      // Phễu chứa preform + băng tải nối
      return (
        <>
          <path d="M12 10h24l-8 12v6h-8v-6L12 10Z" />
          <path d="M24 28v8" />
          <path d="M16 38h16" />
          <circle cx="18" cy="18" r="1.6" />
          <circle cx="26" cy="18" r="1.6" />
        </>
      );
    case "blowmoulder":
      // Khuôn + ba cánh tay
      return (
        <>
          <rect x="15" y="8" width="18" height="22" rx="3" />
          <path d="M24 30v6" />
          <path d="M17 38h14" />
          <path d="M24 12v14" />
          <path d="M18 19h12" />
          <circle cx="24" cy="19" r="4" />
        </>
      );
    case "rinser":
      // Bồn rửa + vòi nước
      return (
        <>
          <path d="M10 16h28v18a3 3 0 0 1-3 3H13a3 3 0 0 1-3-3V16Z" />
          <path d="M8 16h32" />
          <path d="M18 16V10" />
          <path d="M18 10c0 3 3 3 3 6" />
          <path d="M30 16V10" />
          <path d="M30 10c0 3 3 3 3 6" />
        </>
      );
    case "conveyor":
      // Băng tải + chai trên băng
      return (
        <>
          <circle cx="13" cy="32" r="4" />
          <circle cx="35" cy="32" r="4" />
          <path d="M13 28h22" />
          <path d="M9 28V22h30v6" />
          <path d="M18 22v-6h5v6" />
          <path d="M26 22v-5h5v5" />
        </>
      );
    case "filler":
      // Máy chiết: bình + vòi chiết
      return (
        <>
          <path d="M14 26h20v10a3 3 0 0 1-3 3H17a3 3 0 0 1-3-3V26Z" />
          <path d="M19 26v-5h10v5" />
          <path d="M24 8v8" />
          <path d="M21 8h6" />
          <path d="M24 16c0 3-2 4-2 7" />
          <path d="M12 22h6" />
          <path d="M30 22h6" />
        </>
      );
    case "capper":
      // Máy vặn nắp: bàn xoay + nắp
      return (
        <>
          <circle cx="24" cy="30" r="10" />
          <path d="M18 30h12" />
          <path d="M24 30V20" />
          <path d="M20 20h8" />
          <path d="M19 24h10" />
          <path d="M14 38h20" />
        </>
      );
    case "labeler":
      // Máy dán nhãn: cuộn nhãn + chai
      return (
        <>
          <circle cx="14" cy="16" r="7" />
          <circle cx="14" cy="16" r="2.4" />
          <path d="M21 16h12" />
          <path d="M33 12v8" />
          <path d="M20 28h12v12H20z" />
          <path d="M22 28v-5h8v5" />
        </>
      );
    case "coder":
      // Máy in date: khung in + nét
      return (
        <>
          <path d="M12 14h24v20H12z" />
          <path d="M17 20h14" />
          <path d="M17 26h9" />
          <path d="M24 8v6" />
          <path d="M19 8h10" />
          <path d="M17 34v6" />
        </>
      );
    case "casepacker":
      // Máy đóng thùng: thùng + tay gấp
      return (
        <>
          <path d="M12 22h24v16H12z" />
          <path d="M12 22l4-8h16l4 8" />
          <path d="M20 30h8" />
          <path d="M24 8v8" />
          <path d="M20 12l4-4 4 4" />
        </>
      );
    case "depalletizer":
      // Robot cấp hàng: tay robot + pallet
      return (
        <>
          <path d="M8 36h32" />
          <path d="M12 36v-5h12v5" />
          <path d="M24 31V20" />
          <path d="M24 20h9" />
          <path d="M33 20v-6" />
          <path d="M30 14h6" />
          <path d="M16 16h8v8h-8z" />
        </>
      );
    case "seamer":
      // Máy hàn seam: hai trục + lon
      return (
        <>
          <path d="M20 14h8v20h-8z" />
          <path d="M14 24h20" />
          <path d="M16 14h16" />
          <path d="M20 34h8v6h-8z" />
          <path d="M26 24l6-4" />
        </>
      );
    case "inspector":
      // Camera kiểm tra + tia laser
      return (
        <>
          <rect x="8" y="16" width="14" height="16" rx="2" />
          <circle cx="15" cy="24" r="4" />
          <path d="M28 18v12" />
          <path d="M32 18v12" />
          <path d="M22 24h6" />
        </>
      );
    case "cip":
      // Xe CIP: bể + vòi
      return (
        <>
          <path d="M10 16h28v18H10z" />
          <path d="M14 16v-4h20v4" />
          <path d="M16 24h16" />
          <path d="M38 16V9" />
          <path d="M38 9c0 4 4 4 4 8" />
          <circle cx="16" cy="38" r="3" />
          <circle cx="32" cy="38" r="3" />
        </>
      );
    default:
      return <rect x="12" y="14" width="24" height="20" rx="2" />;
  }
}
