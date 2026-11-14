// ============================================================================
//  MÀN 2 — LINE VIEW
//  Line Header (trạng thái chung) → Line Flow (lưới dòng chảy KHÔNG scroll ngang)
//  → Machine Status Panel + Alarm Panel + Production Trend.
//
//  Nguyên tắc: KHÔNG dùng thanh trượt ngang cho sơ đồ dòng chảy. Sơ đồ dàn
//  theo lưới co giãn (components/ProcessFlow.tsx), tự tính số cột từ bề rộng
//  thật của container.
//
//  Thay đổi 12/11 (theo góp ý):
//    ① Thêm DROPDOWN chuyển nhanh giữa các LINE (LINE_01/02/03).
//    ② Card máy trong sơ đồ: chỉ còn TÊN + TRẠNG THÁI (màu) + vài thông tin cơ
//       bản + MINH HỌA máy (sticker). Mọi thông số chi tiết (tốc độ, bộ đếm,
//       alarm…) nằm trong POPOVER hiện khi hover.
//    ③ Thuật ngữ chuẩn tiếng Anh.
// ============================================================================

import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ChevronRight,
  ChevronDown,
  Cpu,
  Factory,
  Wrench,
} from "lucide-react";
import { useTelemetry, type MachineStateView } from "../store";
import {
  MACHINE_TYPE_LABEL,
  PROCESS_LABEL,
  processOrder,
  speedUnitLabel,
  STATUS_META,
} from "../domain/state";
import { pct, yieldRate } from "../domain/oee";
import { planProgress, paceProgress } from "../domain/plan";
import { fmtClock, fmtAge } from "../domain/time";
import { CONNECTION_META, FRESHNESS_META } from "../domain/quality";
import { shiftLabel, shiftOf, shiftElapsedRatio } from "../domain/shift";
import { buildTrendPoints, planAt, type TrendPoint } from "../domain/trend";
import { t, tip } from "../domain/terms";
import { ProcessFlow } from "../components/ProcessFlow";
import { MachineGlyph, glyphBg } from "../components/MachineGlyph";
import {
  EmptyState,
  KpiCard,
  SourceBadge,
  StatusBadge,
  StatusDot,
  fmtInt,
  fmtNum,
} from "../components/common";

export function LineView({
  lineId,
  onBack,
  onOpenMachine,
  onSelectLine,
  onOpenWoExecution,
}: {
  lineId: string;
  onBack: () => void;
  onOpenMachine: (machineId: string) => void;
  onSelectLine?: (lineId: string) => void;
  /** Mở màn thực thi Work Order (A3). */
  onOpenWoExecution?: (woId: string) => void;
}) {
  const { lines, shared, events, source, dashboard } = useTelemetry();
  const line = lines.find((l) => l.meta.lineId === lineId);

  if (!line) {
    return (
      <div className="page">
        <EmptyState title="Không tìm thấy dây chuyền" desc={lineId} />
      </div>
    );
  }

  const { meta, machines, status, connection, oee, output, plan, statusCounts } = line;
  const progress = planProgress(output.good, plan);
  // Production Pace so với kế hoạch tích luỹ tới thời điểm hiện tại.
  const pace = paceProgress(output.good, plan, shiftElapsedRatio());
  const alarms = machines.filter((m) => {
    const c = m.values.AlarmCode;
    return typeof c === "number" && c !== 0;
  });

  /**
   * KPI của line từ PostgreSQL — TÍNH THEO WORK ORDER đang chạy.
   * `scope === "work_order"` → số thuộc lệnh; "shift" → fallback theo ca.
   */
  const dashLine = dashboard?.lines.find((l) => l.lineId === lineId) ?? null;
  const activeWo = dashLine?.workOrder ?? null;

  // Sắp xếp theo thứ tự công đoạn — suy ra từ processId trong catalog.
  const ordered = [...machines].sort(
    (a, b) =>
      processOrder(a.def.processId, a.def.lineId) - processOrder(b.def.processId, b.def.lineId),
  );

  const trend = buildTrendPoints(
    source.outputHistoryOf(meta.lineId).map((p) => ({ at: p.at, good: p.good })),
    0,
  );
  const nowMs = Date.now();

  return (
    <div className="page">
      {/* ── Breadcrumb + header ──────────────────────────────────────── */}
      <nav className="crumbs" aria-label="Đường dẫn">
        <button onClick={onBack} className="crumb-back">
          <ArrowLeft size={14} aria-hidden="true" /> Plant
        </button>
        <ChevronRight size={13} aria-hidden="true" />
        <span className="crumb-current">{meta.lineId}</span>
      </nav>

      <header className="page-head line-head">
        <div>
          <div className="eyebrow">LINE VIEW</div>
          <h1>
            {meta.lineId} <span className="line-sub">{meta.displayName}</span>
          </h1>
          <p className="page-sub">
            {meta.productName ?? "—"} · SKU {meta.sku ?? "—"} · {shiftLabel()}
            {/* Work order đang chạy — nguồn: PostgreSQL (work order đang chạy). */}
            {activeWo && (
              <>
                {" · "}
                <span title={`Kế hoạch: ${activeWo.plannedQty ?? "—"}`}>
                  WO {activeWo.woCode}
                </span>
              </>
            )}
          </p>
        </div>
        <div className="head-right">
          {/*
            ⚠ YÊU CẦU (12/11): cần cách NHANH CHÓNG chuyển giữa các line.
            Nay có DROPDOWN chuyển line ở header màn Line View (kèm trạng
            thái OEE của từng line để chọn đúng ngay).
          */}
          <LineSwitcher
            lines={lines}
            currentId={meta.lineId}
            onSelect={(id) => onSelectLine?.(id)}
          />
          <SourceBadge kind={source.kind} />
          {/* Badge nguồn KPI — OEE đọc từ PostgreSQL (batch), cập nhật 1 phút. */}
          {dashboard && (
            <span
              className="mock-badge live"
              title={`OEE/A/P/Q đọc từ PostgreSQL (machine_kpi_1m) · tính theo Work Order đang chạy · cập nhật mỗi 1 phút · dữ liệu đến ${dashboard.dataUntil ?? "—"}`}
            >
              PG
            </span>
          )}
          <ConnectionBadge connection={connection} />
          <StatusBadge status={status} size="md" />
        </div>
      </header>

      {/* ── Panel trạng thái chung của line ──────────────────────────── */}
      <section className="line-header-panel" aria-label="Thông số chung của dây chuyền">
        <div className="lh-kpis">
          <KpiCard
            label={`${t("oee")} — Line`}
            value={pct(oee.oee)}
            tone="accent"
            hint={tip("oee")}
            sub={
              dashLine ? (
                <span title="Nguồn: PostgreSQL — tính theo Work Order đang chạy">
                  {dashLine.scope === "work_order"
                    ? `theo WO ${activeWo?.woCode ?? ""}`
                    : "theo ca (chưa có lệnh)"}
                </span>
              ) : undefined
            }
          />
          <KpiCard
            label={t("availability")}
            value={pct(oee.availability)}
            hint={tip("availability")}
            sub="Run Time / Planned Production Time"
          />
          <KpiCard
            label={t("performance")}
            value={pct(oee.performance)}
            hint={tip("performance")}
            sub="(Ideal Cycle Time × Total Count) / Run Time"
          />
          <KpiCard
            label={t("quality")}
            value={pct(oee.quality)}
            hint={tip("quality")}
            sub="Good Count / Total Count"
          />
        </div>

        {/* ── Work Order đang chạy (nhấn để xem chi tiết) ────────────── */}
        <ActiveWorkOrderPanel
          lineId={lineId}
          workOrder={activeWo}
          counts={dashLine?.counts ?? null}
          progressRatio={dashLine?.progressRatio ?? null}
          elapsedSec={dashLine?.plannedSec ?? null}
          onOpen={onOpenWoExecution}
        />

        <div className="lh-progress">
          <div className="lh-progress-head">
            <span>Shift Output</span>
            <b className="num">
              {fmtInt(output.good)}
              {plan ? ` / ${fmtInt(plan)}` : ""} pcs
            </b>
          </div>
          {progress ? (
            <>
              <div className="lh-progress-bar">
                <div
                  className="lh-progress-fill"
                  style={{ width: `${Math.min(100, progress.ratio! * 100)}%` }}
                />
              </div>
              <div className="lh-progress-foot">
                <span>
                  Plan Attainment <b className="num">{progress.pct}%</b>
                </span>
                <span className={progress.over ? "over" : undefined}>{progress.label}</span>
              </div>
            </>
          ) : (
            <div className="lh-progress-empty">chưa có nguồn kế hoạch sản lượng</div>
          )}

          {/*
            Production Pace — so với kế hoạch TÍCH LUỸ tới giờ hiện tại.
            Giữa ca, "đạt 31% kế hoạch" dễ gây hiểu nhầm là line chạy kém;
            nhịp mới là con số người vận hành cần (đã có ở Plant Overview).
          */}
          {pace && (
            <div className="lh-pace">
              <div className="lh-pace-foot">
                <span>
                  Production Pace: <b className="num">{pace.pct}%</b>
                </span>
                <span className={pace.over ? "over" : undefined}>{pace.label}</span>
              </div>
              <div className="lh-progress-bar lh-progress-bar-sm">
                <div
                  className="lh-progress-fill"
                  style={{
                    width: `${Math.min(100, pace.ratio! * 100)}%`,
                    background: pace.over ? "var(--state-running)" : "var(--state-starved)",
                  }}
                />
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="line-body">
        {/* ── Sơ đồ dòng ────────────────────────────────────────────── */}
        <section className="flow-section">
          <div className="section-head">
            <h2>Process Flow</h2>
            <span className="section-hint">
              {machines.length} máy · theo thứ tự công đoạn · hover để xem chi tiết
            </span>
          </div>

          <ProcessFlow
            machines={ordered}
            renderCard={(m) => (
              <MachineCard machine={m} onOpen={() => onOpenMachine(m.def.machineId)} />
            )}
          />

          {/* Thiết bị dùng chung */}
          {shared.length > 0 && (
            <div className="shared-lane">
              <div className="shared-lane-label">
                <Wrench size={13} aria-hidden="true" />
                Shared Equipment
              </div>
              <div className="shared-lane-track">
                {shared.map((m) => (
                  <MachineCard
                    key={m.def.machineId}
                    machine={m}
                    compact
                    onOpen={() => onOpenMachine(m.def.machineId)}
                  />
                ))}
              </div>
            </div>
          )}
        </section>

        {/* ── Right rail ─────────────────────────────────────────────── */}
        <aside className="rail" aria-label="Thông tin bên phải">
          <RailPanel title="Active Alarms" count={alarms.length} icon={<AlertTriangle size={14} />}>
            {alarms.length === 0 ? (
              <div className="rail-empty">Không có alarm</div>
            ) : (
              alarms.map((m) => (
                <button
                  key={m.def.machineId}
                  className="rail-row"
                  onClick={() => onOpenMachine(m.def.machineId)}
                >
                  <span className="rail-row-eq">{m.def.equipmentCode}</span>
                  <span className="rail-row-text">
                    Alarm {String(m.values.AlarmCode)}
                  </span>
                </button>
              ))
            )}
          </RailPanel>

          <RailPanel title="Machines by Status" icon={<Cpu size={14} />}>
            {/*
              ⚠ BỐ CỤC ĐÃ SỬA: trước đây panel này LIỆT KÊ LẠI toàn bộ danh
              sách máy, trùng với sơ đồ dòng chảy + bảng "Các công đoạn" →
              cùng một thông tin hiện ở 3 nơi. Nay chỉ hiện TÓM TẮT đếm số
              máy theo trạng thái (thông tin chưa có ở đâu khác), kèm tổng
              số máy.
            */}
            <div className="rail-summary">
              {statusCounts.map(({ status: st, n }) => (
                <div key={st} className="rail-summary-row">
                  <StatusDot status={st} />
                  <span className="rail-summary-label">
                    {STATUS_META[st].label}
                  </span>
                  <span className="rail-summary-value num">{n}</span>
                </div>
              ))}
              <div className="rail-summary-row rail-summary-total">
                <span className="rail-summary-label">Tổng số máy</span>
                <span className="rail-summary-value num">{machines.length}</span>
              </div>
            </div>
          </RailPanel>

          <RailPanel title="Recent Events" icon={<ChevronRight size={14} />}>
            {events.length === 0 ? (
              <div className="rail-empty">Chưa có sự kiện</div>
            ) : (
              events.slice(0, 6).map((e, i) => (
                <div key={i} className={`rail-event sev-${e.severity}`}>
                  <span className="rail-event-time num">{fmtClock(e.at)}</span>
                  <span className="rail-event-text">{e.text}</span>
                </div>
              ))
            )}
          </RailPanel>
        </aside>
      </div>

      {/* ── Xu hướng sản lượng + tóm tắt công đoạn ───────────────────── */}
      <section className="line-lower">
        <div className="panel trend-panel">
          <div className="section-head">
            <h2>Production Trend</h2>
            <span className="section-hint">
              Actual vs Plan · cumulative trong ca {meta.shift}
            </span>
          </div>
          {trend.length >= 2 ? (
            <OutputTrend points={trend} plan={plan} />
          ) : (
            <div className="chart-empty">Đang tích luỹ dữ liệu…</div>
          )}
        </div>

        <div className="panel stage-panel">
          <div className="section-head">
            <h2>Process Steps</h2>
            <span className="section-hint">Theo thứ tự vận hành</span>
          </div>
          <div className="stage-list">
            {ordered.map((m, i) => (
              <button
                key={m.def.machineId}
                className="stage-row"
                onClick={() => onOpenMachine(m.def.machineId)}
              >
                <span className="stage-idx num">{i + 1}</span>
                <span className="stage-code">{m.def.equipmentCode}</span>
                <span className="stage-name">
                  {PROCESS_LABEL[m.def.processId] ?? m.def.processId}
                </span>
                <StatusDot status={m.status} />
                <span className="stage-time num" title={fmtAge(m.receivedAt, nowMs)}>
                  {fmtClock(m.receivedAt)}
                </span>
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

// ── Work Order đang chạy của line ───────────────────────────────────────
/**
 * Panel hiển thị lệnh sản xuất ĐANG CHẠY của chuyền + số liệu của lệnh.
 *
 * ⚠ VÌ SAO CẦN:
 *   Người vận hành ở màn Line phải thấy ngay "chuyền này đang chạy lệnh nào,
 *   lệnh đó đã đạt bao nhiêu" — và bấm vào để mở màn thực thi (A3).
 *
 *   Số liệu lấy từ PostgreSQL, TÍNH THEO LỆNH (khoảng
 *   [actual_start, actual_end ?? now)) → đổi lệnh là số đổi theo.
 */
function ActiveWorkOrderPanel({
  lineId,
  workOrder,
  counts,
  progressRatio,
  elapsedSec,
  onOpen,
}: {
  lineId: string;
  workOrder: {
    woId: string;
    woCode: string;
    productId: string;
    status: string;
    plannedQty: number | null;
    actualStartTime: string | null;
  } | null;
  counts: { total: number; good: number; defect: number; reject: number } | null;
  progressRatio: number | null;
  elapsedSec: number | null;
  onOpen?: (woId: string) => void;
}) {
  if (!workOrder) {
    return (
      <div className="lh-wo lh-wo-empty">
        <div className="lh-wo-head">
          <span className="lh-wo-title">Work Order</span>
        </div>
        <div className="lh-wo-empty-text">
          Chuyền {lineId} chưa có lệnh sản xuất đang chạy — OEE hiển thị theo ca.
        </div>
      </div>
    );
  }

  const actual = counts?.total ?? 0;
  const planned = workOrder.plannedQty ?? 0;
  const ratio = progressRatio ?? (planned > 0 ? actual / planned : null);
  const reject = counts?.reject ?? 0;

  return (
    <button
      className="lh-wo"
      onClick={() => onOpen?.(workOrder.woId)}
      disabled={!onOpen}
      aria-label={`Mở chi tiết Work Order ${workOrder.woCode}`}
    >
      <div className="lh-wo-head">
        <span className="lh-wo-title">Work Order đang chạy</span>
        <span className="lh-wo-code mono">{workOrder.woCode}</span>
      </div>
      <div className="lh-wo-body">
        <div className="lh-wo-qty">
          <div className="lh-wo-qty-block">
            <span>Thực tế</span>
            <strong className="num">{fmtInt(actual)}</strong>
          </div>
          <div className="lh-wo-qty-block">
            <span>Kế hoạch</span>
            <strong className="num">{fmtInt(planned)}</strong>
          </div>
          <div className="lh-wo-qty-block lh-wo-good">
            <span>Good</span>
            <strong className="num">{fmtInt(counts?.good ?? 0)}</strong>
          </div>
          <div className="lh-wo-qty-block lh-wo-ng">
            <span>NG</span>
            <strong className="num">{fmtInt(reject)}</strong>
          </div>
        </div>
        {ratio != null && (
          <div className="lh-wo-progress">
            <div className="lh-wo-progress-track">
              <div
                className="lh-wo-progress-fill"
                style={{ width: `${Math.min(100, Math.max(0, ratio * 100))}%` }}
              />
            </div>
            <span className="lh-wo-progress-text num">{pct(ratio, 1)}</span>
          </div>
        )}
        <div className="lh-wo-foot">
          <span>
            Bắt đầu {fmtClock(workOrder.actualStartTime)} · chạy{" "}
            {elapsedSec ? fmtDurationShort(elapsedSec) : "—"}
          </span>
          <span className="lh-wo-go">
            Xem chi tiết <ChevronRight size={13} aria-hidden="true" />
          </span>
        </div>
      </div>
    </button>
  );
}

/** Thời lượng ngắn gọn: 2h05 hoặc 45m. */
function fmtDurationShort(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h > 0 ? `${h}h${String(m).padStart(2, "0")}` : `${m}m`;
}

// ── Line switcher (dropdown chuyển line) ────────────────────────────────
function LineSwitcher({
  lines,
  currentId,
  onSelect,
}: {
  lines: {
    meta: { lineId: string; displayName: string };
    oee: { oee: number };
  }[];
  currentId: string;
  onSelect: (lineId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = lines.find((l) => l.meta.lineId === currentId);

  return (
    <div className="line-switcher">
      <button
        className="line-switcher-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Chuyển dây chuyền"
      >
        <span className="line-switcher-icon" aria-hidden="true">
          <Factory size={14} />
        </span>
        <span className="line-switcher-text">
          <b>{currentId}</b>
          <small>{current?.meta.displayName ?? ""}</small>
        </span>
        <ChevronDown
          size={14}
          aria-hidden="true"
          style={{ transform: open ? "rotate(180deg)" : undefined }}
        />
      </button>

      {open && (
        <>
          <div className="line-switcher-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="line-switcher-menu" role="listbox" aria-label="Chọn dây chuyền">
            {lines.map((l) => {
              const isCur = l.meta.lineId === currentId;
              return (
                <button
                  key={l.meta.lineId}
                  role="option"
                  aria-selected={isCur}
                  className={`line-switcher-item${isCur ? " active" : ""}`}
                  onClick={() => {
                    setOpen(false);
                    if (!isCur) onSelect(l.meta.lineId);
                  }}
                >
                  <span className="line-switcher-item-main">
                    <b>{l.meta.lineId}</b>
                    <small>{l.meta.displayName}</small>
                  </span>
                  <span className="line-switcher-item-oee num" title="OEE">
                    {pct(l.oee.oee, 0)}
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ── Rail panel ───────────────────────────────────────────────────────────
function RailPanel({
  title,
  count,
  icon,
  children,
}: {
  title: string;
  count?: number;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rail-panel">
      <div className="rail-head">
        <span className="rail-title">
          {icon}
          {title}
        </span>
        {count != null && count > 0 && <span className="rail-count">{count}</span>}
      </div>
      <div className="rail-body">{children}</div>
    </div>
  );
}

// ── Connection badge ─────────────────────────────────────────────────────
function ConnectionBadge({ connection }: { connection: "connected" | "degraded" | "offline" }) {
  const m = CONNECTION_META[connection];
  return (
    <span
      className="status-badge"
      style={{ background: m.bg, color: m.fg, border: `1px solid ${m.color}55` }}
      title={`Trạng thái kết nối: ${m.label}`}
    >
      <span className="status-glyph" aria-hidden="true">
        {m.glyph}
      </span>
      {m.label}
    </span>
  );
}

// ── Xu hướng sản lượng ──────────────────────────────────────────────────
function OutputTrend({ points, plan }: { points: TrendPoint[]; plan: number | null }) {
  const w = 560;
  const h = 120;
  const pad = 8;
  const max = Math.max(...points.map((p) => p.y), plan ?? 0, 1);
  const min = Math.min(...points.map((p) => p.y), 0);
  const span = max - min || 1;

  const path = points
    .map((p, i) => {
      const x = pad + p.x * (w - pad * 2);
      const y = h - pad - ((p.y - min) / span) * (h - pad * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const planY = plan != null ? h - pad - ((plan - min) / span) * (h - pad * 2) : null;
  const last = points[points.length - 1];
  const planNow = plan != null ? planAt(plan, last.x) : 0;

  return (
    <div className="trend-wrap">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="trend-svg"
        preserveAspectRatio="none"
        role="img"
        aria-label="Xu hướng sản lượng thực tế — Actual vs Plan"
      >
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${path} L${w - pad},${h} L${pad},${h} Z`} fill="url(#trendFill)" />
        {planY != null && (
          /* Đường kế hoạch RAMP CHÉO (0,0) → (1,plan) — không phải đường ngang. */
          <line
            x1={pad}
            y1={h - pad}
            x2={w - pad}
            y2={planY}
            stroke="var(--state-running)"
            strokeWidth="2"
            strokeDasharray="6 4"
            opacity="0.9"
          />
        )}
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2.25" />
      </svg>
      <div className="trend-legend">
        <span>
          <i style={{ background: "var(--accent)" }} /> Actual{" "}
          <b className="num">{fmtInt(points[points.length - 1].y)}</b> pcs
        </span>
        {plan != null && (
          <>
            <span>
              <i className="dash" style={{ background: "var(--state-running)" }} /> Plan{" "}
              <b className="num">{fmtInt(plan)}</b> pcs
            </span>
            <span>
              <i style={{ background: "transparent" }} /> Plan-to-date{" "}
              <b className="num">{fmtInt(planNow)}</b> pcs
            </span>
          </>
        )}
      </div>
    </div>
  );
}

// ── Machine card — GỌN + MINH HỌA, chi tiết ở popover khi hover ────────
export function MachineCard({
  machine,
  onOpen,
  compact = false,
}: {
  machine: MachineStateView;
  onOpen: () => void;
  compact?: boolean;
}) {
  const { def, status, values, speed, good, defect } = machine;
  const speedRatio =
    speed.current != null && speed.design ? speed.current / speed.design : null;
  const yieldPct = yieldRate(good, machine.total);
  const counterValue = counterOf(def.machineType, values);
  const feature = pickFeature(def.machineType, values);
  const alarmCode = values.AlarmCode;
  const fresh = FRESHNESS_META[machine.freshness];
  const statusColor = STATUS_META[status].color;

  return (
    <button
      className={`mcard mcard-simple${compact ? " mcard-compact" : ""}`}
      onClick={onOpen}
      // Viền trái mã hóa trạng thái máy (ISA-101): đỏ = lỗi, xanh = đang chạy…
      style={{ borderLeftColor: statusColor }}
    >
      <div className="mcard-top">
        {/*
          MINH HỌA MÁY (sticker) — thay cho khối panel số liệu dày.
          Màu theo trạng thái → nhìn sơ đồ là biết máy nào đang lỗi.
        */}
        <span className="mcard-sticker" style={{ background: glyphBg(status) }}>
          <MachineGlyph machineType={def.machineType} size={compact ? 34 : 42} status={status} />
        </span>
        <div className="mcard-id">
          <span className="mcard-code">{def.equipmentCode}</span>
          <span className="mcard-type">
            {PROCESS_LABEL[def.processId] ?? MACHINE_TYPE_LABEL[def.machineType] ?? def.machineType}
          </span>
        </div>
      </div>

      {/* Trạng thái — hiển thị bằng MÀU + chữ (không chỉ dùng màu) */}
      <div className="mcard-status">
        <span className="mcard-status-dot" style={{ background: statusColor }} aria-hidden="true" />
        <span className="mcard-status-label">{STATUS_META[status].label}</span>
        {alarmCode ? (
          <span className="mcard-alarm" title={`Mã alarm: ${String(alarmCode)}`}>
            <AlertTriangle size={11} aria-hidden="true" /> {String(alarmCode)}
          </span>
        ) : null}
      </div>

      {/* 1–2 thông tin cơ bản (phần còn lại nằm ở popover) */}
      <div className="mcard-basic">
        {def.machineType === "CIP_SKID" ? (
          <span>
            pH <b className="num">{typeof values.pH === "number" ? fmtNum(values.pH, 1) : "—"}</b>
          </span>
        ) : (
          <span>
            Speed{" "}
            <b className="num">
              {speed.current != null ? fmtNum(speed.current, 0) : "—"}
              {speed.design != null ? ` / ${fmtNum(speed.design, 0)}` : ""}
            </b>{" "}
            {speedUnitLabel(def)}
          </span>
        )}
        {feature && (
          <span>
            {feature.label}{" "}
            <b className="num">
              {fmtNum(feature.value, 1)}
              {feature.unit ? ` ${feature.unit}` : ""}
            </b>
          </span>
        )}
      </div>

      {/*
        POPOVER CHI TIẾT — hiện khi HOVER (yêu cầu 12/11: card gọn, chi tiết
        hiện khi hover). Nội dung = toàn bộ thông số đang hiện ở card cũ.
      */}
      <span className="mcard-pop" role="tooltip">
        <span className="mcard-pop-head">
          <b>{def.equipmentCode}</b>
          <span
            className="status-badge"
            style={{
              background: STATUS_META[status].bg,
              color: STATUS_META[status].fg,
              border: `1px solid ${STATUS_META[status].color}55`,
              fontSize: 10.5,
              padding: "2px 6px",
            }}
          >
            <span className="status-glyph" aria-hidden="true">
              {STATUS_META[status].glyph}
            </span>
            {STATUS_META[status].label}
          </span>
        </span>
        <span className="mcard-pop-grid">
          <span>
            <i>Speed</i>
            <b className="num">
              {speed.current != null ? fmtNum(speed.current, 1) : "—"}
              {speed.design != null ? ` / ${fmtNum(speed.design, 1)}` : ""} {speedUnitLabel(def)}
            </b>
          </span>
          <span>
            <i>Yield</i>
            <b className="num">{yieldPct != null ? pct(yieldPct, 1) : "—"}</b>
          </span>
          <span>
            <i>Good Count</i>
            <b className="num">{fmtInt(good)}</b>
          </span>
          <span>
            <i>Defects</i>
            <b className="num">{fmtInt(defect)}</b>
          </span>
          <span>
            <i>Total Count</i>
            <b className="num">{fmtInt(machine.total)}</b>
          </span>
          <span>
            <i>Last Update</i>
            <b className="num">{fmtClock(machine.receivedAt)}</b>
          </span>
        </span>
        <span className="mcard-pop-foot">
          {speedRatio != null && (
            <span>
              Speed vs design: <b className="num">{pct(speedRatio, 0)}</b>
            </span>
          )}
          {counterValue != null && (
            <span>
              {counterLabel(def.machineType)}: <b className="num">{fmtInt(counterValue)}</b>
            </span>
          )}
          {machine.freshness !== "live" && (
            <span style={{ color: fresh.fg }}>
              {fresh.glyph} {fresh.label}
            </span>
          )}
          <span className="mcard-pop-hint">Click để mở chi tiết →</span>
        </span>
      </span>
    </button>
  );
}

/** Bộ đếm đặc trưng khi máy không có GoodCounter (vd DATE_CODER chỉ có PrintCount). */
function counterOf(
  machineType: string,
  values: Record<string, number | string | boolean | null>,
): number | null {
  const table: Record<string, [string, string]> = {
    DATE_CODER: ["PrintCount", "Lượt in"],
    BOTTLE_LABELER: ["LabelApplyCount", "Lượt dán"],
    CAN_INSPECTION: ["InspectionCount", "Lượt kiểm tra"],
    CIP_SKID: ["TotalCounter", "Chu kỳ CIP"],
  };
  const spec = table[machineType];
  if (!spec) return null;
  const v = values[spec[0]];
  return typeof v === "number" ? v : null;
}

function counterLabel(machineType: string): string {
  const table: Record<string, string> = {
    DATE_CODER: "Lượt in",
    BOTTLE_LABELER: "Lượt dán",
    CAN_INSPECTION: "Lượt kiểm tra",
    CIP_SKID: "Chu kỳ CIP",
  };
  return table[machineType] ?? "Output";
}

/** Chọn thông số đặc trưng nhất của loại máy để hiển thị trên card. */
function pickFeature(
  machineType: string,
  values: Record<string, number | string | boolean | null>,
): { label: string; value: number; unit: string } | null {
  const table: Record<string, [string, string, string]> = {
    PREFORM_FEEDER: ["HopperLevel", "Mực phễu", "%"],
    STRETCH_BLOW_MOULDER: ["MoldTemp", "Nhiệt độ khuôn", "°C"],
    AIR_CONVEYOR: ["AirPressure", "Áp suất khí", "bar"],
    BOTTLE_RINSER: ["RinseWaterTemp", "Nhiệt nước rửa", "°C"],
    CAN_RINSER: ["RinseWaterTemp", "Nhiệt nước rửa", "°C"],
    CARBONATED_FILLER: ["FillLevel", "Mức chiết", "%"],
    STILL_FILLER: ["FillLevel", "Mức chiết", "%"],
    CAN_FILLER: ["FillLevel", "Mức chiết", "%"],
    SCREW_CAPPER: ["Torque", "Mô-men", "Nm"],
    BOTTLE_LABELER: ["LabelRollRemaining", "Cuộn nhãn còn", "m"],
    DATE_CODER: ["InkLevel", "Mực còn", "%"],
    CASE_PACKER: ["FilmRemaining", "Màng còn", "m"],
    CAN_DEPALLETIZER: ["PalletCount", "Số pallet", ""],
    CAN_SEAMER: ["SeamPressure", "Áp suất seam", "bar"],
    CAN_INSPECTION: ["DefectRate", "Tỷ lệ lỗi", "%"],
    CIP_SKID: ["TankTemp", "Nhiệt bể", "°C"],
  };
  const spec = table[machineType];
  if (!spec) return null;
  const v = values[spec[0]];
  if (typeof v !== "number") return null;
  return { label: spec[1], value: v, unit: spec[2] };
}
