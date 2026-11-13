// ============================================================================
//  MÀN 4 — ALARM & EVENT CENTER
//  Phân biệt rõ 3 loại: ALARM (đang mở) / EVENT (sự kiện) / NOTIFICATION.
//
//  ⚠ Nguyên tắc (work.md): KHÔNG tự suy diễn severity. Mã alarm lấy từ tag
//    `AlarmCode` của máy; nghiêm trọng chỉ dùng để GỢI Ý, không gán cứng.
// ============================================================================

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  BellRing,
  ChevronRight,
  CircleDot,
  Info,
  Search,
} from "lucide-react";
import { useTelemetry } from "../store";
import { STATUS_META, type MachineStatus } from "../domain/state";
import { fmtClock } from "../domain/time";
import { EmptyState, SourceBadge, StatusBadge, fmtInt } from "../components/common";

/** Nhãn mức độ — không gán severity mới, chỉ hiển thị theo nguồn sự kiện. */
const SEV_LABEL: Record<"info" | "warn" | "crit", string> = {
  info: "Thông tin",
  warn: "Cảnh báo",
  crit: "Nghiêm trọng",
};

type Filter = "all" | "alarm" | "event";

type Row = {
  key: string;
  kind: "alarm" | "event";
  severity: "info" | "warn" | "crit";
  at: string;
  machineId: string;
  equipmentCode: string;
  /** Mã alarm từ thiết bị (null với sự kiện thường). */
  alarmCode: number | null;
  text: string;
  detail: MachineStatus | null;
};

export function AlarmCenter({
  onBack,
  onOpenMachine,
}: {
  onBack: () => void;
  onOpenMachine: (machineId: string) => void;
}) {
  const { machines, events, lines, source } = useTelemetry();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [lineFilter, setLineFilter] = useState<string>("all");

  // Alarm đang mở = máy có `AlarmCode` khác 0 (nguồn: tag, không suy diễn).
  const openAlarms = useMemo(
    () =>
      machines
        .filter((m) => {
          const c = m.values.AlarmCode;
          return typeof c === "number" && c !== 0;
        })
        .map((m) => ({
          machine: m,
          code: Number(m.values.AlarmCode),
        })),
    [machines],
  );

  const rows = useMemo<Row[]>(() => {
    const alarmRows: Row[] = openAlarms.map((a) => ({
      key: `a-${a.machine.def.machineId}`,
      kind: "alarm",
      severity: "crit",
      at: a.machine.receivedAt,
      machineId: a.machine.def.machineId,
      equipmentCode: a.machine.def.equipmentCode,
      alarmCode: a.code,
      text: `Alarm ${a.code} đang mở`,
      detail: a.machine.status,
    }));
    const eventRows: Row[] = events.map((e, i) => ({
      key: `e-${i}-${e.at}`,
      kind: e.kind === "alarm" ? "alarm" : "event",
      severity: e.severity,
      at: e.at,
      machineId: e.machineId,
      equipmentCode: e.equipmentCode,
      alarmCode: null,
      text: e.text,
      detail: null,
    }));
    const all = [...alarmRows, ...eventRows].sort(
      (a, b) => Date.parse(b.at) - Date.parse(a.at),
    );
    if (filter === "alarm") return all.filter((r) => r.kind === "alarm");
    if (filter === "event") return all.filter((r) => r.kind === "event");
    return all;
  }, [openAlarms, events, filter]);

  // ── Lọc theo dây chuyền + tìm kiếm ──────────────────────────────────
  const lineOf = useMemo(() => {
    const map = new Map<string, string>();
    for (const l of lines) for (const m of l.machines) map.set(m.def.machineId, l.meta.lineId);
    return map;
  }, [lines]);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (lineFilter !== "all" && lineOf.get(r.machineId) !== lineFilter) return false;
      if (!q) return true;
      return (
        r.equipmentCode.toLowerCase().includes(q) ||
        r.text.toLowerCase().includes(q) ||
        (r.alarmCode != null && String(r.alarmCode).includes(q))
      );
    });
  }, [rows, query, lineFilter, lineOf]);

  const critCount = openAlarms.length;

  // Kênh kết nối (connection thuộc KÊNH, không thuộc máy).
  const badChannels = useMemo(
    () => new Set(machines.filter((m) => m.connection !== "connected").map((m) => m.def.channel)),
    [machines],
  );
  const allChannels = useMemo(
    () => new Set(machines.map((m) => m.def.channel)),
    [machines],
  );

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Đường dẫn">
        <button onClick={onBack} className="crumb-back">
          <ArrowLeft size={14} aria-hidden="true" /> Nhà máy
        </button>
        <ChevronRight size={13} aria-hidden="true" />
        <span className="crumb-current">Alarm &amp; Sự kiện</span>
      </nav>

      <header className="page-head">
        <div>
          <div className="eyebrow">TRUNG TÂM ALARM &amp; SỰ KIỆN</div>
          <h1>Giám sát sự kiện</h1>
          <p className="page-sub">
            {openAlarms.length} alarm đang mở · {events.length} sự kiện trong phiên mô phỏng
          </p>
        </div>
        <div className="head-right">
          <SourceBadge kind={source.kind} />
        </div>
      </header>

      {/* ── Tóm tắt theo mức độ ─────────────────────────────────────── */}
      <section className="kpi-row" aria-label="Tóm tắt alarm">
        <div className="kpi">
          <div className="kpi-label">Alarm đang mở</div>
          <div className="kpi-value num" style={{ color: critCount ? "var(--state-fault-fg)" : undefined }}>
            {fmtInt(critCount)}
          </div>
          <div className="kpi-sub">
            {critCount > 0 ? "Cần người phụ trách xử lý" : "Không có alarm"}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Sự kiện</div>
          <div className="kpi-value num">{fmtInt(events.length)}</div>
          <div className="kpi-sub">Chuyển trạng thái · thông báo vận hành</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Máy đang lỗi</div>
          <div className="kpi-value num">
            {machines.filter((m) => m.status === "FAULT").length}
          </div>
          <div className="kpi-sub">Trạng thái máy = Lỗi</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Kênh mất kết nối</div>
          <div className="kpi-value num">
            {badChannels.size}/{allChannels.size}
          </div>
          <div className="kpi-sub">Kênh truyền — tách khỏi trạng thái máy</div>
        </div>
      </section>

      {/* ── Bộ lọc ───────────────────────────────────────────────────── */}
      <section className="section">
        <div className="section-head">
          <h2>Danh sách</h2>
          <div className="filter-row">
            <FilterChip active={filter === "all"} onClick={() => setFilter("all")}>
              Tất cả ({openAlarms.length + events.length})
            </FilterChip>
            <FilterChip active={filter === "alarm"} onClick={() => setFilter("alarm")}>
              <AlertTriangle size={12} aria-hidden="true" /> Alarm ({openAlarms.length})
            </FilterChip>
            <FilterChip active={filter === "event"} onClick={() => setFilter("event")}>
              <CircleDot size={12} aria-hidden="true" /> Sự kiện ({events.length})
            </FilterChip>
          </div>
        </div>

        {/* Ô tìm kiếm + lọc dây chuyền */}
        <div className="alarm-toolbar">
          <label className="alarm-search">
            <Search size={14} aria-hidden="true" />
            <input
              type="search"
              value={query}
              placeholder="Tìm theo thiết bị, mô tả hoặc mã alarm…"
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Tìm kiếm alarm và sự kiện"
            />
          </label>
          <label className="alarm-linefilter">
            <span>Dây chuyền</span>
            <select
              value={lineFilter}
              onChange={(e) => setLineFilter(e.target.value)}
              aria-label="Lọc theo dây chuyền"
            >
              <option value="all">Tất cả</option>
              {lines.map((l) => (
                <option key={l.meta.lineId} value={l.meta.lineId}>
                  {l.meta.lineId} — {l.meta.displayName}
                </option>
              ))}
            </select>
          </label>
          <span className="alarm-count">{filteredRows.length} bản ghi</span>
        </div>

        {/* Bảng có cấu trúc — dễ quét bằng mắt (ISA-18.2) */}
        <div className="panel alarm-table-panel">
          <table className="alarm-table">
            <thead>
              <tr>
                <th scope="col">Thời điểm</th>
                <th scope="col">Loại</th>
                <th scope="col">Mức độ</th>
                <th scope="col">Thiết bị</th>
                <th scope="col">Dây chuyền</th>
                <th scope="col">Mô tả</th>
                <th scope="col">Trạng thái máy</th>
                <th scope="col" aria-label="Mở chi tiết" />
              </tr>
            </thead>
            <tbody>
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="alarm-empty">
                    Không có mục nào khớp bộ lọc
                  </td>
                </tr>
              ) : (
                filteredRows.map((r) => (
                  <tr key={r.key} className={`sev-${r.severity}`}>
                    <td className="num alarm-time">{fmtClock(r.at)}</td>
                    <td>
                      <span className={`ev-kind ev-kind-${r.kind}`}>
                        {r.kind === "alarm" ? (
                          <AlertTriangle size={11} aria-hidden="true" />
                        ) : (
                          <Info size={11} aria-hidden="true" />
                        )}
                        {r.kind === "alarm" ? "ALARM" : "EVENT"}
                      </span>
                    </td>
                    <td>
                      <span className={`sev-badge sev-badge-${r.severity}`}>
                        {SEV_LABEL[r.severity]}
                      </span>
                    </td>
                    <td className="alarm-eq">{r.equipmentCode}</td>
                    <td className="num alarm-line">{lineOf.get(r.machineId) ?? "—"}</td>
                    <td className="alarm-text">{r.text}</td>
                    <td>{r.detail ? <StatusBadge status={r.detail} size="sm" /> : "—"}</td>
                    <td className="alarm-go">
                      <button
                        className="alarm-open"
                        onClick={() => onOpenMachine(r.machineId)}
                        aria-label={`Mở chi tiết ${r.equipmentCode}`}
                      >
                        <ChevronRight size={14} aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Giải thích phân loại ─────────────────────────────────────── */}
      <section className="section">
        <div className="panel legend-panel">
          <div className="legend-panel-title">
            <BellRing size={14} aria-hidden="true" /> Phân biệt 3 loại thông báo
          </div>
          <div className="legend-panel-grid">
            <div>
              <b>Alarm</b>
              <span>
                Tình trạng bất thường đang tồn tại, cần xử lý. Nguồn: tag{" "}
                <code>AlarmCode</code> — mã lấy trực tiếp từ thiết bị.
              </span>
            </div>
            <div>
              <b>Event</b>
              <span>
                Sự kiện đã xảy ra (chuyển trạng thái, đổi khuôn…). Nguồn: pipeline
                sự kiện downtime.
              </span>
            </div>
            <div>
              <b>Notification</b>
              <span>
                Thông báo vận hành (hết nguyên liệu, cần canh khuôn…). Chưa có nguồn
                riêng trong middleware — sẽ bổ sung ở giai đoạn backend.
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button className={`filter-chip${active ? " active" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}
