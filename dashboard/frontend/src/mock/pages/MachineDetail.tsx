// ============================================================================
//  MÀN 3 — MACHINE DETAIL (slide-over)
//  Nội dung thông số DỰNG ĐỘNG theo machineType (không hard-code theo máy).
//
//  Thay đổi 12/11:
//    ① Bên TRÁI có MINH HỌA THIẾT BỊ (SVG) + thông tin danh tính → tránh UI
//       bị trống ở cột trái.
//    ② Cột trái có thể mở rộng: hiển thị TOÀN BỘ LINE dạng sơ đồ nhỏ, TÔ
//       ĐẬM thiết bị đang chọn → người dùng thấy vị trí máy trong dòng.
// ============================================================================

import { useEffect, useState } from "react";
import { X, AlertTriangle, ChevronRight, Activity, Gauge, Timer } from "lucide-react";
import { useTelemetry } from "../store";
import type { MachineDef } from "../catalog.gen";
import {
  MACHINE_MODE_LABEL,
  MACHINE_STATE_LABEL,
  STATUS_META,
  displayUnit,
  findTag,
  speedUnitLabel,
  type MachineMode,
  type MachineState,
} from "../domain/state";
import {
  counterTagFor,
  counterTagLabel,
  profileFor,
  type MetricDef,
} from "../domain/metric-profiles";
import { pct, yieldRate } from "../domain/oee";
import { fmtAge, fmtClock, fmtDateTime } from "../domain/time";
import { CONNECTION_META, FRESHNESS_META } from "../domain/quality";
import { MachineGlyph, glyphBg } from "../components/MachineGlyph";
import {
  EmptyState,
  QualityDot,
  Sparkline,
  StatusBadge,
  fmtInt,
  fmtNum,
  fmtValue,
} from "../components/common";

type Tab = "overview" | "tags" | "chart" | "events";

export function MachineDetail({
  machineId,
  onClose,
}: {
  machineId: string;
  onClose: () => void;
}) {
  const { byId, sim } = useTelemetry();
  const [tab, setTab] = useState<Tab>("overview");
  const machine = byId(machineId);

  // ── Drawer là OVERLAY: khoá scroll nền nhưng GIỮ NỀN hiển thị ──────
  //
  // ⚠ YÊU CẦU (12/11): trước đây popup là NỘI DUNG TRANG thay thế → nền
  //   phía sau bị xóa sạch. Nay drawer là lớp phủ `position:fixed`, nền vẫn
  //   hiện (phủ mờ) và đóng popup sẽ trở về đúng màn đang xem.
  //
  //   Khoá scroll của `<body>` để không cuộn được nền khi drawer mở — nhưng
  //   KHÔNG ẩn nền (không dùng `display:none`), nên người dùng vẫn thấy
  //   bố cục phía sau.
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, []);

  // Đóng bằng phím Escape — tiêu chuẩn cho drawer/dialog.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!machine) {
    return (
      <div className="drawer-backdrop" onClick={onClose}>
        <div className="drawer" onClick={(e) => e.stopPropagation()}>
          <EmptyState title="Không tìm thấy máy" desc={machineId} />
        </div>
      </div>
    );
  }

  const { def, values, quality, status, connection, freshness, receivedAt } = machine;
  const groups = profileFor(def.machineType);
  const alarmCode = values.AlarmCode;

  const yieldPct = yieldRate(machine.good, machine.total);
  const speedRatio =
    machine.speed.current != null && machine.speed.design
      ? machine.speed.current / machine.speed.design
      : null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        className="drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Chi tiết máy ${def.equipmentCode}`}
      >
        {/* ── Header ─────────────────────────────────────────────────── */}
        <header className="dr-head">
          <div className="dr-head-main">
            <div className="dr-eyebrow">
              {def.lineId} <ChevronRight size={11} aria-hidden="true" /> {def.processId}
            </div>
            <h2>{def.equipmentCode}</h2>
            <div className="dr-sub">{def.machineType}</div>
            <div className="dr-meta-row">
              <span className="dr-meta" title={`Kết nối kênh ${def.channel}`}>
                <i style={{ background: CONNECTION_META[connection].color }} />
                {CONNECTION_META[connection].label}
              </span>
              <span
                className="dr-meta"
                title={`Bản ghi cuối: ${fmtDateTime(receivedAt)}`}
              >
                <i style={{ background: FRESHNESS_META[freshness].color }} />
                {FRESHNESS_META[freshness].label} · {fmtClock(receivedAt)}
              </span>
            </div>
          </div>
          <div className="dr-head-right">
            <StatusBadge status={status} />
            <button className="dr-close" onClick={onClose} aria-label="Đóng chi tiết thiết bị">
              <X size={18} />
            </button>
          </div>
        </header>

        {/* ── Tabs ───────────────────────────────────────────────────── */}
        <nav className="dr-tabs" role="tablist">
          {(
            [
              ["overview", "Tổng quan"],
              ["tags", `Thông số (${def.tags.length})`],
              ["chart", "Biểu đồ"],
              ["events", "Sự kiện"],
            ] as [Tab, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              role="tab"
              aria-selected={tab === id}
              className={`dr-tab${tab === id ? " active" : ""}`}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="dr-body">
          {/*
            ⚠ YÊU CẦU (12/11): cột trái trống → thêm MINH HỌA THIẾT BỊ +
            sơ đồ toàn line (highlight máy đang chọn). Ở tab "Thông số /
            Biểu đồ / Sự kiện" thì ẩn cột trái để bảng có đủ bề ngang.
          */}
          {tab === "overview" && (
            <div className="dr-split">
              <aside className="dr-side">
                <MachineIllustration machine={machine} />
                <LineContext machine={machine} />
              </aside>
              <div className="dr-main">
                <OverviewTab
                  machine={machine}
                  groups={groups}
                  alarmCode={alarmCode}
                  yieldPct={yieldPct}
                  speedRatio={speedRatio}
                />
              </div>
            </div>
          )}
          {tab === "tags" && <TagsTab machine={machine} />}
          {tab === "chart" && <ChartTab machine={machine} />}
          {tab === "events" && <EventsTab machineId={machineId} />}
        </div>
      </aside>
    </div>
  );
}

// ── Minh họa thiết bị (cột trái) ───────────────────────────────────────
function MachineIllustration({
  machine,
}: {
  machine: ReturnType<typeof useTelemetry>["machines"][number];
}) {
  const { def, status } = machine;
  return (
    <section className="dr-illustration" aria-label="Minh họa thiết bị">
      <div className="dr-illustration-stage" style={{ background: glyphBg(status) }}>
        <MachineGlyph machineType={def.machineType} size={132} status={status} />
      </div>
      <div className="dr-illustration-cap">
        <b>{def.equipmentCode}</b>
        <span>{def.machineType}</span>
      </div>
      <dl className="dr-idfacts">
        <div>
          <dt>Line</dt>
          <dd>{def.lineId}</dd>
        </div>
        <div>
          <dt>Process</dt>
          <dd>{def.processId}</dd>
        </div>
        <div>
          <dt>Channel</dt>
          <dd>{def.channel}</dd>
        </div>
        <div>
          <dt>Machine ID</dt>
          <dd className="dr-idfacts-mono">{def.machineId}</dd>
        </div>
      </dl>
    </section>
  );
}

// ── Sơ đồ toàn line, highlight máy đang chọn ───────────────────────────
function LineContext({
  machine,
}: {
  machine: ReturnType<typeof useTelemetry>["machines"][number];
}) {
  const { lines } = useTelemetry();
  const line = lines.find((l) => l.meta.lineId === machine.def.lineId);
  if (!line) return null;

  return (
    <section className="dr-linecontext">
      <div className="dr-linecontext-head">
        <span>Line context</span>
        <b>{line.meta.lineId}</b>
      </div>
      <ol className="dr-linecontext-list">
        {line.machines.map((m) => {
          const isSel = m.def.machineId === machine.def.machineId;
          return (
            <li
              key={m.def.machineId}
              className={`dr-linecontext-item${isSel ? " selected" : ""}`}
              title={`${m.def.equipmentCode} — ${STATUS_META[m.status].label}`}
            >
              <span
                className="dr-linecontext-dot"
                style={{ background: m.def.machineId === machine.def.machineId ? "var(--accent)" : undefined }}
                data-status={m.status}
              />
              <span className="dr-linecontext-code">{m.def.equipmentCode}</span>
              {isSel && <span className="dr-linecontext-flag">Đang xem</span>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

// ── Tab: Tổng quan ──────────────────────────────────────────────────────
function OverviewTab({
  machine,
  groups,
  alarmCode,
  yieldPct,
  speedRatio,
}: {
  machine: ReturnType<typeof useTelemetry>["machines"][number];
  groups: ReturnType<typeof profileFor>;
  alarmCode: number | string | boolean | null;
  yieldPct: number | null;
  speedRatio: number | null;
}) {
  const { values, quality, def } = machine;
  const state = values.MachineState as MachineState | null;
  const mode = values.MachineMode as MachineMode | null;

  // Máy không có `GoodCounter` (vd DATE_CODER chỉ có `PrintCount`) → dùng bộ
  // đếm đặc trưng của loại máy, và KHÔNG hiện Yield (không có cơ sở tính).
  const counterTag = counterTagFor(def.machineType);
  const counterValue =
    counterTag != null && typeof values[counterTag] === "number"
      ? (values[counterTag] as number)
      : null;
  const hasYield = machine.good != null;

  return (
    <div className="dr-stack">
      {/* Trạng thái */}
      <section className="dr-card">
        <h3 className="dr-card-title">
          <Activity size={14} aria-hidden="true" /> Trạng thái
        </h3>
        <div className="dr-grid dr-grid-2">
          <DrField label="Trạng thái máy" value={state != null ? MACHINE_STATE_LABEL[state] : "—"} />
          <DrField label="Chế độ" value={mode != null ? MACHINE_MODE_LABEL[mode] : "—"} />
          <DrField
            label="Dừng khẩn"
            value={values.EmergencyStop === true ? "CÓ" : values.EmergencyStop === false ? "Không" : "—"}
            tone={values.EmergencyStop === true ? "crit" : undefined}
          />
          <DrField
            label="Mã alarm"
            value={alarmCode ? String(alarmCode) : "0"}
            tone={alarmCode ? "warn" : undefined}
          />
          <DrField
            label="Thiếu nguyên liệu"
            value={values.Starved === true ? "CÓ" : values.Starved === false ? "Không" : "—"}
            tone={values.Starved === true ? "warn" : undefined}
          />
          <DrField
            label="Tắc nghẽn"
            value={values.Blocked === true ? "CÓ" : values.Blocked === false ? "Không" : "—"}
            tone={values.Blocked === true ? "warn" : undefined}
          />
        </div>
      </section>

      {/* Sản lượng — chỉ hiện với máy có bộ đếm sản phẩm (CIP chỉ đếm chu kỳ) */}
      {machine.total != null && def.machineType !== "CIP_SKID" && (
        <section className="dr-card">
          <h3 className="dr-card-title">
            <Gauge size={14} aria-hidden="true" /> Sản lượng
          </h3>
          <div className="dr-grid dr-grid-3">
            <DrField label="Tổng xử lý" value={fmtInt(machine.total)} unit="pcs" />
            <DrField
              label={counterTagLabel(def.machineType)}
              value={fmtInt(counterValue)}
              unit="pcs"
            />
            <DrField
              label="Lỗi"
              value={machine.defect != null ? fmtInt(machine.defect) : "—"}
              unit="pcs"
            />
            {hasYield && <DrField label="Yield" value={pct(yieldPct, 2)} />}
            <DrField
              label="Tốc độ"
              value={machine.speed.current != null ? fmtNum(machine.speed.current, 1) : "—"}
              unit={speedUnitLabel(def)}
            />
            <DrField
              label="Thiết kế"
              value={machine.speed.design != null ? fmtNum(machine.speed.design, 1) : "—"}
              unit={speedUnitLabel(def)}
            />
          </div>
        </section>
      )}

      {/* Thông số đặc trưng — dựng động theo machineType */}
      {groups.map((g) => (
        <section className="dr-card" key={g.title}>
          <h3 className="dr-card-title">
            <Timer size={14} aria-hidden="true" /> {g.title}
          </h3>
          <div className="dr-metrics">
            {g.metrics.map((m) => (
              <MetricCell
                key={m.label}
                metric={m}
                values={values}
                quality={quality}
                def={def}
              />
            ))}
          </div>
        </section>
      ))}

      {/* Hiệu suất — chỉ có ý nghĩa khi máy có CurrentSpeed/DesignSpeed */}
      {machine.speed.current != null && machine.speed.design != null && (
        <section className="dr-card">
          <h3 className="dr-card-title">Hiệu suất</h3>
          <div className="dr-ratio">
            <div className="dr-ratio-head">
              <span>Tốc độ thực / thiết kế</span>
              <b className="num">{pct(speedRatio)}</b>
            </div>
            <div className="dr-ratio-bar">
              <div
                className="dr-ratio-fill"
                style={{
                  width: `${speedRatio != null ? Math.min(100, speedRatio * 100) : 0}%`,
                }}
              />
              <div className="dr-ratio-target" style={{ left: "85%" }} />
            </div>
            <div className="dr-ratio-foot">
              <span>0%</span>
              <span>mục tiêu 85%</span>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

// ── 1 ô thông số ────────────────────────────────────────────────────────
function MetricCell({
  metric,
  values,
  quality,
  def,
}: {
  metric: MetricDef;
  values: Record<string, number | string | boolean | null>;
  quality: Record<string, string>;
  def: MachineDef;
}) {
  const [t0, t1] = metric.tags;
  const v0 = values[t0];
  const v1 = values[t1];

  if (metric.kind === "ratio") {
    const ratio = typeof v0 === "number" && typeof v1 === "number" && v1 !== 0 ? v0 / v1 : null;
    return (
      <div className="metric-cell" title={metric.hint}>
        <div className="metric-label">{metric.label}</div>
        <div className="metric-value num">
          {typeof v0 === "number" ? fmtNum(v0, 1) : "—"}
          {typeof v1 === "number" && (
            <span className="metric-target"> / {fmtNum(v1, 1)}</span>
          )}
        </div>
        {ratio != null && (
          <div className="metric-bar">
            <div
              className="metric-bar-fill"
              style={{
                width: `${Math.min(100, ratio * 100)}%`,
                background: ratio >= 0.85 ? "var(--state-running)" : "var(--state-starved)",
              }}
            />
          </div>
        )}
      </div>
    );
  }

  if (metric.kind === "flag") {
    const isBool = typeof v0 === "boolean";
    const isAlarm = t0 === "AlarmCode";
    const active = isBool ? v0 === true : typeof v0 === "number" && v0 !== 0;
    return (
      <div className="metric-cell" title={metric.hint}>
        <div className="metric-label">
          {metric.label} <QualityDot quality={quality[t0]} />
        </div>
        <div
          className="metric-value"
          style={{
            color: active ? (isAlarm ? "var(--state-fault-fg)" : "var(--state-starved-fg)") : undefined,
          }}
        >
          {isBool ? (v0 === true ? "CÓ" : v0 === false ? "Không" : "—") : active ? String(v0) : "0"}
        </div>
      </div>
    );
  }

  const unit = typeof v0 === "number" ? unitOf(t0, def) : null;
  return (
    <div className="metric-cell" title={metric.hint}>
      <div className="metric-label">
        {metric.label} <QualityDot quality={quality[t0]} />
      </div>
      <div className="metric-value num">
        {typeof v0 === "number" ? fmtNum(v0, 1) : "—"}
        {unit && <span className="metric-unit">{unit}</span>}
      </div>
    </div>
  );
}

/**
 * Suy đơn vị từ catalog — đơn vị là thuộc tính của TAG, không phải của giá trị.
 * Tra cứu trực tiếp trong `def.tags` để không phải hard-code ở từng profile.
 */
function unitOf(tagName: string, def: MachineDef): string | null {
  const tag = findTag(def.tags, tagName);
  if (!tag?.unit) return null;
  return displayUnit(tag.unit);
}

function DrField({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: string;
  unit?: string;
  tone?: "crit" | "warn";
}) {
  return (
    <div className="dr-field">
      <span className="dr-field-label">{label}</span>
      <span className={`dr-field-value num${tone ? ` tone-${tone}` : ""}`}>
        {value}
        {unit && <span className="dr-field-unit"> {unit}</span>}
      </span>
    </div>
  );
}

// ── Tab: Toàn bộ thông số ───────────────────────────────────────────────
function TagsTab({
  machine,
}: {
  machine: ReturnType<typeof useTelemetry>["machines"][number];
}) {
  return (
    <div className="dr-stack">
      <div className="dr-note">
        Toàn bộ {machine.def.tags.length} tag của máy, lấy trực tiếp từ catalog.
        <code>{machine.def.machineId}</code>
      </div>
      <div className="panel">
        <table className="tag-table">
          <thead>
            <tr>
              <th>Tag</th>
              <th>Giá trị</th>
              <th>Đơn vị</th>
              <th>Chất lượng</th>
            </tr>
          </thead>
          <tbody>
            {machine.def.tags.map((t) => {
              const v = machine.values[t.name];
              const bad = machine.quality[t.name] && machine.quality[t.name] !== "Good";
              return (
                <tr key={t.name}>
                  <td>
                    <code className="tag-code">{t.name}</code>
                    <span className="tag-meaning">{t.meaning}</span>
                  </td>
                  <td className="tag-value num">{fmtValue(v)}</td>
                  <td className="tag-unit">{t.unit ? displayUnit(t.unit) ?? "—" : "—"}</td>
                  <td>
                    {bad ? (
                      <span className="quality-mark quality-bad">{machine.quality[t.name]}</span>
                    ) : (
                      <span className="quality-ok">Good</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Tab: Biểu đồ ────────────────────────────────────────────────────────
function ChartTab({
  machine,
}: {
  machine: ReturnType<typeof useTelemetry>["machines"][number];
}) {
  const { sim } = useTelemetry();
  const candidates = machine.def.tags.filter(
    (t) => t.dataType === "Float" && t.tagType === "ANALOG",
  );
  const [selected, setSelected] = useState<string[]>(
    candidates.slice(0, 2).map((t) => t.name),
  );

  const toggle = (name: string) => {
    setSelected((prev) =>
      prev.includes(name)
        ? prev.filter((n) => n !== name)
        : [...prev.slice(-2), name],
    );
  };

  return (
    <div className="dr-stack">
      <div className="dr-note">
        Chọn tối đa 3 tag số thực để vẽ. Dữ liệu lịch sử trong phiên mô phỏng.
      </div>

      <div className="chart-picker">
        {candidates.map((t) => (
          <button
            key={t.name}
            className={`chip${selected.includes(t.name) ? " active" : ""}`}
            onClick={() => toggle(t.name)}
          >
            {t.name}
          </button>
        ))}
      </div>

      {selected.length === 0 ? (
        <EmptyState title="Chưa chọn tag" desc="Chọn ít nhất một thông số để xem xu hướng" />
      ) : (
        selected.map((name) => {
          const hist = sim.historyOf(machine.def.machineId, name);
          const points = hist.map((h) => h.value);
          const tag = machine.def.tags.find((t) => t.name === name);
          return (
            <section className="dr-card" key={name}>
              <h3 className="dr-card-title">
                {name}
                {tag?.unit && <span className="metric-unit">{tag.unit}</span>}
              </h3>
              {points.length >= 2 ? (
                <>
                  <Sparkline points={points} width={620} height={110} color="var(--accent)" />
                  <div className="chart-range">
                    <span>
                      Min <b className="num">{fmtNum(Math.min(...points), 2)}</b>
                    </span>
                    <span>
                      Max <b className="num">{fmtNum(Math.max(...points), 2)}</b>
                    </span>
                    <span>
                      Hiện tại <b className="num">{fmtNum(points[points.length - 1], 2)}</b>
                    </span>
                  </div>
                </>
              ) : (
                <div className="chart-empty">Đang tích lũy dữ liệu…</div>
              )}
            </section>
          );
        })
      )}
    </div>
  );
}

// ── Tab: Sự kiện ────────────────────────────────────────────────────────
function EventsTab({ machineId }: { machineId: string }) {
  const { events } = useTelemetry();
  const list = events.filter((e) => e.machineId === machineId);
  if (!list.length) {
    return (
      <EmptyState
        title="Chưa có sự kiện"
        desc={`Chưa ghi nhận sự kiện nào cho ${machineId}`}
        icon="◷"
      />
    );
  }
  return (
    <div className="panel">
      <table className="tag-table">
        <thead>
          <tr>
            <th>Thời điểm</th>
            <th>Loại</th>
            <th>Nội dung</th>
          </tr>
        </thead>
        <tbody>
          {list.map((e, i) => (
            <tr key={i}>
              <td className="num">{fmtDateTime(e.at)}</td>
              <td>
                <span className={`event-kind sev-${e.severity}`}>
                  {e.kind === "alarm" && <AlertTriangle size={11} aria-hidden="true" />}
                  {e.kind}
                </span>
              </td>
              <td>{e.text}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
