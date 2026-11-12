// ============================================================================
//  Component dùng chung — trạng thái, KPI, sparkline, chất lượng dữ liệu
// ============================================================================

import { type ReactNode } from "react";
import { STATUS_META, type MachineStatus } from "../domain/state";

// ── StatusBadge: màu + icon + CHỮ (không dùng màu làm tín hiệu duy nhất) ──
export function StatusBadge({
  status,
  size = "md",
  showLabel = true,
}: {
  status: MachineStatus;
  size?: "sm" | "md";
  showLabel?: boolean;
}) {
  const m = STATUS_META[status];
  const pad = size === "sm" ? "3px 7px" : "5px 10px";
  const fontSize = size === "sm" ? 11 : 11.5;
  return (
    <span
      className="status-badge"
      style={{
        background: m.bg,
        color: m.fg,
        border: `1px solid ${m.color}55`,
        padding: pad,
        fontSize,
      }}
      title={`Trạng thái: ${m.label}`}
    >
      <span className="status-glyph" aria-hidden="true">
        {m.glyph}
      </span>
      {showLabel && <span>{m.label}</span>}
    </span>
  );
}

// ── Dot nhỏ dùng trong chú giải / danh sách ──────────────────────────────
export function StatusDot({ status, title }: { status: MachineStatus; title?: string }) {
  const m = STATUS_META[status];
  return (
    <span
      className="status-dot"
      style={{ background: m.color }}
      title={title ?? m.label}
      aria-label={title ?? m.label}
    />
  );
}

// ── Chú giải trạng thái ──────────────────────────────────────────────────
export function StatusLegend({ counts }: { counts: { status: MachineStatus; n: number }[] }) {
  const visible = counts.filter((c) => c.n > 0);
  return (
    <div className="legend">
      {visible.map((c) => {
        const m = STATUS_META[c.status];
        return (
          <span key={c.status} className="legend-item">
            <StatusDot status={c.status} />
            <span style={{ color: m.fg }}>{m.label}</span>
            <b className="num">{c.n}</b>
          </span>
        );
      })}
    </div>
  );
}

// ── KPI card ─────────────────────────────────────────────────────────────
export function KpiCard({
  label,
  value,
  unit,
  sub,
  tone = "default",
  bar,
  hint,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  sub?: ReactNode;
  tone?: "default" | "accent";
  /** 0..1 — hiển thị progress bar */
  bar?: number | null;
  hint?: string;
}) {
  return (
    <div className={`kpi${tone === "accent" ? " kpi-accent" : ""}`} title={hint}>
      <div className="kpi-label">
        {label}
        {hint && (
          <span className="kpi-hint" title={hint}>
            ⓘ
          </span>
        )}
      </div>
      <div className="kpi-value num">
        {value}
        {unit && <span className="kpi-unit">{unit}</span>}
      </div>
      {bar != null && (
        <div className="kpi-bar">
          <div
            className="kpi-bar-fill"
            style={{ width: `${Math.max(0, Math.min(1, bar)) * 100}%` }}
          />
        </div>
      )}
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

// ── Data quality dot: Good / Bad / Uncertain / Stale ─────────────────────
export function QualityDot({
  quality,
  stale,
}: {
  quality?: string;
  stale?: boolean;
}) {
  if (stale) {
    return (
      <span className="quality-mark quality-stale" title="Dữ liệu cũ — vượt ngưỡng freshness">
        ⧗ cũ
      </span>
    );
  }
  if (quality && quality !== "Good" && quality !== "Present") {
    return (
      <span className="quality-mark quality-bad" title={`Chất lượng nguồn: ${quality}`}>
        {quality}
      </span>
    );
  }
  return null;
}

// ── Sparkline (SVG thuần, không phụ thuộc thư viện) ──────────────────────
export function Sparkline({
  points,
  width = 120,
  height = 30,
  color = "var(--accent)",
  fill = true,
}: {
  points: number[];
  width?: number;
  height?: number;
  color?: string;
  fill?: boolean;
}) {
  if (points.length < 2) {
    return (
      <div className="spark-empty" style={{ width, height }}>
        chưa đủ dữ liệu
      </div>
    );
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const path = points
    .map((p, i) => {
      const x = i * step;
      const y = height - ((p - min) / span) * (height - 4) - 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const area = `${path} L${width},${height} L0,${height} Z`;
  const gid = `sg-${color.replace(/[^a-z0-9]/gi, "")}`;
  return (
    <svg width={width} height={height} className="spark" role="img" aria-label="Xu hướng">
      {fill && (
        <>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.30" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={area} fill={`url(#${gid})`} />
        </>
      )}
      <path d={path} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

// ── Empty state ──────────────────────────────────────────────────────────
export function EmptyState({
  title,
  desc,
  icon = "∅",
}: {
  title: string;
  desc?: string;
  icon?: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">
        {icon}
      </div>
      <h3>{title}</h3>
      {desc && <p>{desc}</p>}
    </div>
  );
}

// ── Badge MOCK — bắt buộc hiển thị khi dùng dữ liệu giả ────────────────
export function MockBadge() {
  return (
    <span className="mock-badge" title="Dữ liệu MOCK — chưa phải dữ liệu thật từ middleware">
      MOCK
    </span>
  );
}

// ── Định dạng ────────────────────────────────────────────────────────────
const nf = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return digits === 0 ? nf0.format(v) : nf.format(v);
}

export function fmtInt(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return nf0.format(v);
}

/** Hiển thị giá trị: null → "—" (KHÔNG bao giờ thay bằng 0). */
export function fmtValue(
  v: number | string | boolean | null | undefined,
  unit?: string | null,
): string {
  if (v == null) return "—";
  if (typeof v === "boolean") return v ? "Có" : "Không";
  if (typeof v === "number") return nf.format(v);
  return unit ? `${v} ${unit}` : String(v);
}
