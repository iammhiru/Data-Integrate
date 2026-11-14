// ============================================================================
//  MÀN 1 — PLANT OVERVIEW (danh sách line)
//  Mục tiêu: người vận hành thấy ngay toàn nhà máy đang ổn hay không.
//
//  Thay đổi 12/11 (theo góp ý):
//    ① Thuật ngữ chuẩn tiếng Anh (OEE / Plan Attainment / Production Pace…).
//    ② Line card nổi bật + affordance rõ ràng (nút "View Detail", hover lift).
//    ③ Chú giải trạng thái gộp vào component `StatusSummary` (đã BỎ khỏi
//       header) — render ở đây vì màn này là nơi người dùng cần đọc trạng
//       thái tổng quan.
//    ④ Toàn bộ nội dung vừa MỘT màn hình 1080p — không phải scroll.
//    ⑤ Chart "Xu hướng sản lượng" vẽ Actual vs Plan trên CÙNG trục ngữ
//       nghĩa (thời gian đã trôi của ca × sản lượng tích luỹ) → 2 đường
//       lệch nhau rõ rệt thay vì 2 đường thẳng ngang hàng.
// ============================================================================

import { useMemo } from "react";
import { Cpu, ChevronRight, AlertTriangle, TrendingUp } from "lucide-react";
import { useTelemetry, countByStatus, type LineView } from "../store";
import { pct } from "../domain/oee";
import { STATUS_META } from "../domain/state";
import { planProgress, paceProgress } from "../domain/plan";
import { fmtClock } from "../domain/time";
import { CONNECTION_META } from "../domain/quality";
import { shiftLabel, shiftElapsedRatio } from "../domain/shift";
import { buildTrendPoints, planAt, type TrendPoint } from "../domain/trend";
import { t, tip } from "../domain/terms";
import { StatusSummary } from "../components/StatusSummary";
import {
  KpiCard,
  SourceBadge,
  StatusBadge,
  fmtInt,
} from "../components/common";

export function PlantOverview({ onOpenLine }: { onOpenLine: (lineId: string) => void }) {
  const { lines, shared, machines, events, source, dashboard } = useTelemetry();
  // KPI tổng toàn nhà máy.
  // Sản lượng = TỔNG các line (mỗi line đếm riêng sản phẩm của nó).
  // OEE = trung bình GIA QUYỀN theo sản lượng từng line (không cộng trung bình cộng).
  const agg = lines.reduce(
    (acc, l) => {
      acc.availability += l.oee.availability * l.output.total;
      acc.performance += l.oee.performance * l.output.total;
      acc.quality += l.oee.quality * l.output.total;
      acc.output += l.output.good;
      acc.plan += l.plan ?? 0;
      return acc;
    },
    { availability: 0, performance: 0, quality: 0, output: 0, plan: 0 },
  );
  const totalWeight = lines.reduce((s, l) => s + l.output.total, 0);
  const avg =
    totalWeight > 0
      ? {
          availability: agg.availability / totalWeight,
          performance: agg.performance / totalWeight,
          quality: agg.quality / totalWeight,
        }
      : { availability: 0, performance: 0, quality: 0 };
  const plantOee = avg.availability * avg.performance * avg.quality;

  /**
   * ⚠ ƯU TIÊN SỐ TỪ PostgreSQL (14/11/2026).
   *   Backend đã tính sẵn OEE nhà máy (gia quyền theo sản lượng, mỗi line
   *   theo WORK ORDER đang chạy) → lấy thẳng, khỏi tự cộng lại ở browser.
   *   Chỉ fallback về số tự tính khi PG chưa sẵn sàng.
   */
  const plantPg = dashboard?.plant ?? null;
  const plantOeeShown = plantPg?.oee ?? plantOee;
  const plantAShown = plantPg?.availability ?? avg.availability;
  const plantPShown = plantPg?.performance ?? avg.performance;
  const plantQShown = plantPg?.quality ?? avg.quality;
  const plantOutShown = plantPg ? plantPg.production.good : agg.output;

  const plantPlan = planProgress(agg.output, agg.plan);
  // Production Pace: so với kế hoạch tích luỹ tới giờ hiện tại.
  const elapsedRatio = shiftElapsedRatio();
  const plantPace = paceProgress(agg.output, agg.plan, elapsedRatio);

  const totalAlarms = machines.filter((m) => {
    const c = m.values.AlarmCode;
    return typeof c === "number" && c !== 0;
  }).length;
  const running = machines.filter((m) => m.status === "RUNNING").length;
  const faulted = machines.filter((m) => m.status === "FAULT").length;
  // ⚠ BUG ĐÃ SỬA: trước đây đếm MÁY mất kết nối → "7 máy mất kết nối" dù
  //   thực tế chỉ 1 CHÂN (LINE_03) bị yếu, cả 7 máy trên kênh đó cùng mất
  //   kết nối → con số gây hoảng loạn giả. Connection thuộc KÊNH, nên báo
  //   cáo theo kênh: "1/4 kênh yếu".
  const badChannels = new Set(
    machines.filter((m) => m.connection !== "connected").map((m) => m.def.channel),
  );
  const allChannels = new Set(machines.map((m) => m.def.channel));

  // Đếm trạng thái TOÀN NHÀ MÁY → cho component chú giải (StatusSummary).
  const plantStatusCounts = useMemo(() => countByStatus(machines.map((m) => m.status)), [machines]);

  // Xu hướng sản lượng toàn nhà máy = tổng các line theo thời gian.
  const plantTrend = buildPlantTrend(lines, source);

  return (
    <div className="page page-plant">
      <header className="page-head">
        <div>
          <div className="eyebrow">PLANT OVERVIEW</div>
          <h1>PLANT_01</h1>
          <p className="page-sub">
            {lines.length} production lines · {machines.length} machines · {shiftLabel()} · live
          </p>
        </div>
        <div className="head-right">
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
        </div>
      </header>

      {/*
        ⚠ YÊU CẦU (12/11): chú giải trạng thái KHÔNG được nhét vào header
        (header chỉ có tiêu đề + badge). Nay nó là một PANEL riêng, dạng LƯỚI
        thẻ — đọc nhanh, không còn cảm giác "lỗi font" như bản 1 hàng.
      */}
      <section className="panel status-panel" aria-label="Chú giải trạng thái máy">
        <div className="section-head">
          <h2>Trạng thái máy</h2>
          <span className="section-hint">
            {machines.length} máy · {allChannels.size} kênh truyền
          </span>
        </div>
        <StatusSummary counts={plantStatusCounts} />
      </section>

      {/* ── KPI tổng ─────────────────────────────────────────────────── */}
      <section className="kpi-row" aria-label="Plant KPI">
        <KpiCard
          label={t("oee")}
          value={pct(plantOeeShown)}
          tone="accent"
          hint={tip("oee")}
          sub={
            <>
              A {pct(plantAShown)} · P {pct(plantPShown)} · Q{" "}
              {pct(plantQShown)}
              {plantPg ? (
                <> · theo Work Order đang chạy</>
              ) : source.kind === "live" ? (
                <> · cửa sổ: {source.windowLabel()}</>
              ) : null}
            </>
          }
        />
        <KpiCard
          label={t("planAttainment")}
          value={plantPlan ? `${plantPlan.pct}%` : "—"}
          tone="accent"
          hint={tip("planAttainment")}
          bar={plantPlan ? plantPlan.ratio : null}
          sub={
            plantPlan ? (
              <>
                {fmtInt(plantOutShown)} / {fmtInt(agg.plan)} pcs ·{" "}
                <span className={plantPlan.over ? "over" : undefined}>{plantPlan.label}</span>
              </>
            ) : (
              "chưa có nguồn kế hoạch"
            )
          }
        />
        <KpiCard
          label={t("productionPace")}
          value={plantPace ? `${plantPace.pct}%` : "—"}
          tone={plantPace && plantPace.over ? "accent" : "default"}
          hint={tip("productionPace")}
          bar={plantPace ? plantPace.ratio : null}
          sub={
            plantPace ? (
              <>
                vs plan-to-date ·{" "}
                <span className={plantPace.over ? "over" : undefined}>{plantPace.label}</span>
              </>
            ) : (
              "chưa có dữ liệu nhịp"
            )
          }
        />
        <KpiCard
          label={t("runningMachines")}
          value={`${running}/${machines.length}`}
          hint={`${t("runningMachines")} — số máy đang chạy / tổng số máy`}
          sub={
            badChannels.size > 0
              ? `${faulted} faulted · ${badChannels.size}/${allChannels.size} kênh bị suy giảm`
              : `${faulted} faulted · ${allChannels.size}/${allChannels.size} kênh kết nối tốt`
          }
        />
        <KpiCard
          label={t("activeAlarms")}
          value={fmtInt(totalAlarms)}
          tone={totalAlarms > 0 ? "accent" : "default"}
          hint={`${t("activeAlarms")} — số alarm đang mở (mã lấy từ tag AlarmCode)`}
          sub={totalAlarms > 0 ? "Cần người phụ trách xử lý" : "Không có alarm"}
        />
      </section>

      {/* ── Danh sách line ───────────────────────────────────────────── */}
      <section className="section">
        <div className="section-head">
          <h2>Production Lines</h2>
          <span className="section-hint">Chọn một dây chuyền để xem chi tiết</span>
        </div>

        <div className="line-grid">
          {lines.map((line) => (
            <LineCard key={line.meta.lineId} line={line} onOpen={() => onOpenLine(line.meta.lineId)} />
          ))}
          <SharedCard />
        </div>
      </section>

      {/* ── Xu hướng + sự kiện ───────────────────────────────────────── */}
      <section className="plant-lower">
        <div className="panel trend-panel">
          <div className="section-head">
            <h2>Production Trend</h2>
            <span className="section-hint">
              <TrendingUp size={12} aria-hidden="true" /> Plant · Actual vs Plan (cumulative)
            </span>
          </div>
          {plantTrend.length >= 2 ? (
            <PlantTrend points={plantTrend} plan={agg.plan} />
          ) : (
            <div className="chart-empty">Đang tích luỹ dữ liệu…</div>
          )}
        </div>

        <div className="panel events-panel">
          <div className="section-head">
            <h2>Recent Events</h2>
            <span className="section-hint">Nguồn: pipeline telemetry</span>
          </div>
          {events.length === 0 ? (
            <div className="events-empty">Chưa có sự kiện nào trong phiên mô phỏng</div>
          ) : (
            events.slice(0, 6).map((e, i) => (
              <div key={i} className={`event-row sev-${e.severity}`}>
                <span className="event-time num">{fmtClock(e.at)}</span>
                <span className="event-eq">{e.equipmentCode}</span>
                <span className="event-text">{e.text}</span>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

// ── Xu hưởng toàn nhà máy ───────────────────────────────────────────────
function buildPlantTrend(
  lines: LineView[],
  source: ReturnType<typeof useTelemetry>["source"],
): TrendPoint[] {
  // Gom điểm theo mốc thời gian (giây) của từng line rồi cộng lại.
  const buckets = new Map<number, number>();
  for (const l of lines) {
    for (const p of source.outputHistoryOf(l.meta.lineId)) {
      const key = Math.floor(p.at / 1000);
      buckets.set(key, (buckets.get(key) ?? 0) + p.good);
    }
  }
  const samples = [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([sec, good]) => ({ at: sec * 1000, good }));
  return buildTrendPoints(samples, 0);
}

function PlantTrend({ points, plan }: { points: TrendPoint[]; plan: number }) {
  const w = 560;
  const h = 130;
  const pad = 10;
  const max = Math.max(...points.map((p) => p.y), plan, 1);
  const min = Math.min(...points.map((p) => p.y), 0);
  const span = max - min || 1;
  const step = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0;

  const path = points
    .map((p, i) => {
      const x = pad + p.x * (w - pad * 2);
      const y = h - pad - ((p.y - min) / span) * (h - pad * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const planY = h - pad - ((plan - min) / span) * (h - pad * 2);
  // Vị trí hiện tại trên đường kế hoạch (đường chéo từ (0,0) tới (1,plan)).
  const nowX = pad + Math.max(0, Math.min(1, points[points.length - 1].x)) * (w - pad * 2);

  const last = points[points.length - 1];
  const actualNow = last.y;
  const planNow = planAt(plan, last.x);

  return (
    <div className="trend-wrap">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="trend-svg"
        preserveAspectRatio="none"
        role="img"
        aria-label="Xu hướng sản lượng toàn nhà máy — Actual vs Plan"
      >
        <defs>
          <linearGradient id="plantTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Lưới ngang mốc 25/50/75% */}
        {[0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={pad}
            x2={w - pad}
            y1={h - pad - f * (h - pad * 2)}
            y2={h - pad - f * (h - pad * 2)}
            stroke="var(--border-subtle)"
            strokeWidth="1"
          />
        ))}
        <path
          d={`${path} L${w - pad},${h} L${pad},${h} Z`}
          fill="url(#plantTrendFill)"
        />
        {/* Đường KẾ HOẠCH: ramp chéo từ (0,0) tới (1, plan) — KHÔNG phải
            đường ngang ở mức "kế hoạch cả ca" (nguyên nhân 2 đường thẳng
            ngang hàng trước đây). */}
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
        {/* Marker "kế hoạch tới thời điểm hiện tại" */}
        <line
          x1={nowX}
          x2={nowX}
          y1={h - pad - ((planNow - min) / span) * (h - pad * 2)}
          y2={h - pad}
          stroke="var(--state-running)"
          strokeWidth="1"
          strokeDasharray="3 3"
          opacity="0.55"
        />
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2.25" />
        <circle
          cx={nowX}
          cy={h - pad - ((actualNow - min) / span) * (h - pad * 2)}
          r="3.5"
          fill="var(--accent)"
          stroke="var(--bg-surface)"
          strokeWidth="2"
        />
      </svg>
      <div className="trend-legend">
        <span>
          <i style={{ background: "var(--accent)" }} /> Actual{" "}
          <b className="num">{fmtInt(actualNow)}</b> pcs
        </span>
        <span>
          <i className="dash" style={{ background: "var(--state-running)" }} /> Plan{" "}
          <b className="num">{fmtInt(plan)}</b> pcs
        </span>
        <span>
          <i style={{ background: "transparent" }} /> Plan-to-date{" "}
          <b className="num">{fmtInt(planNow)}</b> pcs
        </span>
      </div>
    </div>
  );
}

// ── Line card ────────────────────────────────────────────────────────────
function LineCard({ line, onOpen }: { line: LineView; onOpen: () => void }) {
  const { meta, machines, status, connection, oee, output, plan } = line;
  const counts = line.statusCounts;
  const progress = planProgress(output.good, plan);
  // Production Pace: so với kế hoạch tích luỹ tới thời điểm hiện tại.
  const pace = paceProgress(output.good, plan, shiftElapsedRatio());

  // Phân bố trạng thái dạng stacked bar (không dùng pie).
  const total = machines.length || 1;
  const conn = CONNECTION_META[connection];

  return (
    <button className="line-card" onClick={onOpen} aria-label={`Mở chi tiết ${meta.lineId}`}>
      <div className="line-card-top">
        <div>
          <div className="line-id">{meta.lineId}</div>
          <div className="line-name">{meta.displayName}</div>
        </div>
        <div className="line-card-badges">
          {connection !== "connected" && (
            <span
              className="status-badge"
              style={{
                background: conn.bg,
                color: conn.fg,
                border: `1px solid ${conn.color}55`,
                fontSize: 11,
                padding: "3px 7px",
              }}
              title={`Kết nối: ${conn.label}`}
            >
              <span className="status-glyph" aria-hidden="true">
                {conn.glyph}
              </span>
              {conn.short}
            </span>
          )}
          <StatusBadge status={status} />
        </div>
      </div>

      {/* Chỉ số chính: OEE */}
      <div className="line-oee">
        <div className="line-oee-main">
          <span className="line-oee-label">OEE</span>
          <span className="line-oee-value num">{pct(oee.oee)}</span>
        </div>
        <div className="line-oee-parts">
          <span title={tip("availability")}>
            A <b className="num">{pct(oee.availability, 0)}</b>
          </span>
          <span title={tip("performance")}>
            P <b className="num">{pct(oee.performance, 0)}</b>
          </span>
          <span title={tip("quality")}>
            Q <b className="num">{pct(oee.quality, 0)}</b>
          </span>
        </div>
      </div>

      {/* Output: actual / target + progress */}
      <div className="line-output">
        <div className="line-output-row">
          <span className="meta-key">Output</span>
          <span className="num">
            {fmtInt(output.good)} {plan ? `/ ${fmtInt(plan)}` : ""} pcs
          </span>
        </div>
        {progress && (
          <>
            <div className="line-progress">
              <div
                className="line-progress-fill"
                style={{ width: `${Math.min(100, progress.ratio! * 100)}%` }}
              />
            </div>
            <div className="line-progress-foot">
              <span>
                Plan Attainment <b className="num">{progress.pct}%</b>
              </span>
              <span className={progress.over ? "over" : undefined}>{progress.label}</span>
            </div>
          </>
        )}
        {!plan && <div className="line-note">chưa có nguồn kế hoạch</div>}
      </div>

      {/* Production Pace so với kế hoạch tích luỹ tới giờ này */}
      {pace && (
        <div className="line-pace">
          <div className="line-output-row">
            <span className="meta-key">Production Pace</span>
            <span className="num">
              {pace.pct}%{" "}
              <span className={pace.over ? "over" : undefined}>{pace.label}</span>
            </span>
          </div>
          <div className="line-progress line-progress-sm">
            <div
              className="line-progress-fill"
              style={{
                width: `${Math.min(100, pace.ratio! * 100)}%`,
                background: pace.over ? "var(--state-running)" : "var(--state-starved)",
              }}
            />
          </div>
        </div>
      )}

      {/* Machine summary */}
      <div className="line-statusbar" aria-hidden="true">
        {counts.map(({ status, n }) => (
          <span
            key={status}
            style={{
              width: `${(n / total) * 100}%`,
              background: STATUS_META[status].color,
            }}
            title={`${STATUS_META[status].label}: ${n}`}
          />
        ))}
      </div>

      {/*
        ⚠ AFFORDANCE (12/11): trước đây chỉ có mũi tên nhỏ ở góc phải → người
        dùng không nhận ra đây là vùng bấm được. Nay có NHÃN CTA rõ ràng
        "View Detail" + mũi tên, và card nổi bật hơn (nền trắng, viền rõ,
        hover nâng card + viền xanh).
      */}
      <div className="line-card-foot">
        <StatusSummary counts={counts} variant="compact" />
        <span className="line-go-label">
          View Detail <ChevronRight size={14} className="line-go" aria-hidden="true" />
        </span>
      </div>
    </button>
  );
}

// ── Card thiết bị dùng chung ─────────────────────────────────────────────
function SharedCard() {
  const { shared } = useTelemetry();
  if (!shared.length) return null;
  const m = shared[0];
  return (
    <div className="line-card shared-card">
      <div className="line-card-top">
        <div>
          <div className="line-id">SHARED</div>
          <div className="line-name">Hệ CIP dùng chung</div>
        </div>
        <StatusBadge status={m.status} />
      </div>
      <div className="line-meta">
        <span>
          <span className="meta-key">Máy</span>
          <span className="meta-val">{m.def.equipmentCode}</span>
        </span>
        <span>
          <span className="meta-key">Phục vụ</span>
          <span className="meta-val">LINE_01 · LINE_02 · LINE_03</span>
        </span>
      </div>
      <div className="shared-note">
        <Cpu size={14} aria-hidden="true" />
        Thiết bị dùng chung — được hiển thị ở từng line qua kết nối nét đứt.
      </div>
    </div>
  );
}
