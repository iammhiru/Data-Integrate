import { useEffect, useMemo, useState } from "react";
import { HubConnectionBuilder, LogLevel } from "@microsoft/signalr";
import {
  Activity,
  Boxes,
  ChevronRight,
  Factory,
  Gauge,
  LayoutDashboard,
  Radio,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Tag = {
  tagCode: string;
  tagName: string;
  valueType: string;
  unit: string | null;
  description: string;
};
type Machine = {
  machineId: string;
  machineName: string;
  machineType: string;
  lineId: string;
  tags: Tag[];
};
type Value = {
  machineId: string;
  tagCode: string;
  tagName: string;
  value: number | string | null;
  quality: string;
  eventTime: string;
  receivedAt: string;
  unit: string | null;
};
type Snapshot = {
  revision: number;
  mode: string;
  sourceStatus: string;
  topic: string;
  catalogSource: string;
  tags: Value[];
};
type Diag = {
  telemetry: {
    received: number;
    accepted: number;
    duplicate: number;
    late: number;
    invalid: number;
    missingFields: number;
    lastError: string | null;
    errors: { at: string; reason: string }[];
  };
  postgres: string;
};
type Dataset = {
  rows: Record<string, unknown>[];
  truncated: boolean;
  scope?: string;
};
type Analytics = { source: string; datasets: Record<string, Dataset> };
const states = ["Dừng", "Chờ", "Đang chạy"];
const fmt = (v: unknown): string =>
  v == null
    ? "—"
    : typeof v === "number"
      ? new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(v)
      : String(v);
const time = (v?: string) =>
  v ? new Date(v).toLocaleTimeString("vi-VN") : "Chưa nhận";
async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  const data = await r.json();
  if (!r.ok) throw new Error(data.message || `HTTP ${r.status}`);
  return data;
}

export default function App() {
  const [catalog, setCatalog] = useState<Machine[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot>({
    revision: -1,
    mode: "",
    sourceStatus: "starting",
    topic: "realtime-metrics",
    catalogSource: "",
    tags: [],
  });
  const [connection, setConnection] = useState("Đang kết nối");
  const [error, setError] = useState("");
  const [page, setPage] = useState("overview");
  const [line, setLine] = useState("ALL");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<Machine | null>(null);
  const [diag, setDiag] = useState<Diag | null>(null);
  useEffect(() => {
    let alive = true;
    let retry: ReturnType<typeof setTimeout>;
    const hub = new HubConnectionBuilder()
      .withUrl("/hubs/telemetry")
      .withAutomaticReconnect([0, 1500, 5000, 10000])
      .configureLogging(LogLevel.Error)
      .build();
    const sync = async () => {
      const [c, s] = await Promise.all([
        get<Machine[]>("/api/catalog"),
        get<Snapshot>("/api/snapshot"),
      ]);
      if (alive) {
        setCatalog(c);
        setSnapshot(s);
        setError("");
      }
    };
    hub.on("Snapshot", (s: Snapshot) => {
      if (alive) setSnapshot(s);
    });
    hub.onreconnecting(() => alive && setConnection("Đang nối lại"));
    hub.onreconnected(() => {
      if (alive) {
        setConnection("Đã kết nối");
        void sync().catch((e) => setError(String(e)));
      }
    });
    const start = async () => {
      try {
        await hub.start();
        if (!alive) {
          await hub.stop();
          return;
        }
        setConnection("Đã kết nối");
        await sync();
      } catch (e) {
        if (alive) {
          setConnection("Mất kết nối");
          setError(String(e));
          retry = setTimeout(
            () =>
              hub.state === "Disconnected"
                ? void start()
                : void sync().catch((e) => setError(String(e))),
            3000,
          );
        }
      }
    };
    hub.onclose(() => {
      if (alive) {
        setConnection("Mất kết nối");
        retry = setTimeout(start, 3000);
      }
    });
    void start();
    const refresh = setInterval(() => {
      void get<Machine[]>("/api/catalog")
        .then((c) => {
          if (alive) setCatalog(c);
        })
        .catch(() => {});
    }, 30000);
    return () => {
      alive = false;
      clearTimeout(retry);
      clearInterval(refresh);
      void hub.stop();
    };
  }, []);
  useEffect(() => {
    let alive = true;
    const load = () =>
      get<Diag>("/api/diagnostics")
        .then((d) => alive && setDiag(d))
        .catch(() => {});
    void load();
    const timer = setInterval(load, 2500);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);
  const map = useMemo(
    () => new Map(snapshot.tags.map((t) => [t.machineId + "/" + t.tagName, t])),
    [snapshot],
  );
  const tag = (m: Machine, name: string) => map.get(m.machineId + "/" + name);
  const state = (m: Machine) => {
    const value = tag(m, "status")?.value;
    return value === "RUNNING"
      ? 2
      : value === "IDLE"
        ? 1
        : value === "STOPPED"
          ? 0
          : -1;
  };
  const scoped = catalog.filter((m) => line === "ALL" || m.lineId === line);
  const knownStatus = scoped.filter((m) => state(m) !== -1);
  const unknownCount = scoped.length - knownStatus.length;
  const coverageNote = knownStatus.length
    ? `${knownStatus.length}/${scoped.length} máy có trạng thái đã nhận`
    : "Chưa nhận dữ liệu trạng thái";
  const visible = scoped.filter(
    (m) =>
      (m.machineId + " " + m.machineName + " " + m.machineType)
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (status === "all" || String(state(m)) === status),
  );
  const latest = snapshot.tags.reduce(
    (s, t) => (t.receivedAt > s ? t.receivedAt : s),
    "",
  );
  const present = snapshot.tags.filter((t) => t.value != null).length;
  const nav = [
    { id: "overview", label: "Tổng quan", icon: LayoutDashboard },
    { id: "machines", label: "Giám sát máy", icon: Factory },
    { id: "analytics", label: "Phân tích & OEE", icon: Gauge },
    { id: "quality", label: "Chất lượng dữ liệu", icon: ShieldCheck },
  ];
  return (
    <div className="app">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("overview");
          }}
        >
          <span className="brand-icon">
            <Activity size={23} />
          </span>
          <span>
            factory<span className="brand-light">pulse</span>
            <small>SMART MANUFACTURING</small>
          </span>
        </a>
        <div className="workspace">
          <Factory size={20} />
          <div>
            Smart Factory
            <small>
              {snapshot.mode === "Mock"
                ? "DỮ LIỆU MÔ PHỎNG"
                : "HỆ THỐNG NHÓM 18"}
            </small>
          </div>
        </div>
        <p className="nav-label">KHÔNG GIAN LÀM VIỆC</p>
        <nav>
          {nav.map((n) => (
            <button
              key={n.id}
              className={"nav-item " + (page === n.id ? "active" : "")}
              onClick={() => setPage(n.id)}
            >
              <n.icon size={19} />
              {n.label}
              {n.id === "machines" && (
                <span className="nav-count">{catalog.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="side-bottom">
          <div className="pipeline-label">
            <span className="dot green" /> {snapshot.sourceStatus}
            <small>{snapshot.topic}</small>
            <small>PostgreSQL: {diag?.postgres || "…"}</small>
          </div>
          <div className="profile">
            <div className="avatar">18</div>
            <div>
              Nhóm 18<small>Data-Integrate</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <span className="muted">Không gian làm việc</span>
            <ChevronRight size={13} />
            <strong>{nav.find((n) => n.id === page)?.label}</strong>
          </div>
          <div>
            <span
              className={
                "connection " + (connection === "Đã kết nối" ? "ok" : "warn")
              }
            >
              <span className="dot" />
              {connection}
            </span>
            <span className="top-avatar">N18</span>
          </div>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <div className="eyebrow">DATA-INTEGRATE / VẬN HÀNH NHÀ MÁY</div>
              <h1>
                {page === "overview"
                  ? "Nhịp sản xuất, trong tầm mắt."
                  : nav.find((n) => n.id === page)?.label}
              </h1>
              <p className="subheading">
                Thông số sau Spark và kết quả phân tích từ PostgreSQL.
              </p>
            </div>
            <div className="live-label">
              <Radio size={15} /> CẬP NHẬT{" "}
              <small>Nhận gần nhất {time(latest)}</small>
            </div>
          </div>
          <div className="mode-banner">
            <span>
              <span className="dot amber" />
              <strong>
                {snapshot.mode === "Mock"
                  ? "MÔ PHỎNG"
                  : snapshot.mode || "ĐANG TẢI"}
              </strong>
              <span>
                {snapshot.mode === "Mock"
                  ? "Metric mô phỏng theo schema Spark của repo · Dữ liệu giả lập."
                  : `${snapshot.topic} → backend → SignalR · Luôn xem thời gian nguồn để nhận biết dữ liệu cũ.`}
              </span>
            </span>
            <span className="contract">
              {catalog.length} máy ·{" "}
              {snapshot.catalogSource === "postgres-master"
                ? "Master từ PostgreSQL"
                : "Danh mục theo SQL seed"}
            </span>
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          {catalog.length > 0 && unknownCount > 0 && page !== "analytics" && (
            <div
              className="mode-banner"
              role="status"
              data-testid="telemetry-coverage"
            >
              <span>
                <strong>
                  {knownStatus.length ? "DỮ LIỆU CHƯA ĐỦ" : "ĐANG CHỜ DỮ LIỆU"}
                </strong>
                <span>
                  Đã nhận trạng thái {knownStatus.length}/{scoped.length} máy
                  trong phạm vi. {unknownCount} máy chưa rõ trạng thái; không
                  coi là máy dừng.
                  {snapshot.mode === "Kafka" &&
                    " Kafka đã đăng ký topic chưa đồng nghĩa với nguồn đang phát dữ liệu mới."}
                </span>
              </span>
            </div>
          )}
          {page === "analytics" ? (
            <AnalyticsPanel catalog={catalog} />
          ) : (
            <>
              <section className="metrics">
                <Metric
                  label="Thiết bị trong phạm vi"
                  value={scoped.length}
                  unit="máy"
                  note="Danh mục master theo repo"
                />
                <Metric
                  label="Đang vận hành"
                  value={
                    knownStatus.length
                      ? knownStatus.filter((m) => state(m) === 2).length
                      : "—"
                  }
                  unit="máy"
                  note={coverageNote}
                  green
                />
                <Metric
                  label="Đang dừng"
                  value={
                    knownStatus.length
                      ? knownStatus.filter((m) => state(m) === 0).length
                      : "—"
                  }
                  unit="máy"
                  note={coverageNote}
                />
                <Metric
                  label="Trường hiện có giá trị"
                  value={
                    snapshot.tags.length
                      ? ((present / snapshot.tags.length) * 100).toFixed(1)
                      : "—"
                  }
                  unit="%"
                  note="Không phải chất lượng OPC UA"
                />
              </section>
              {page === "quality" ? (
                <section className="panel diagnostic">
                  <h2>Sức khỏe nhánh dashboard</h2>
                  <p className="muted">
                    Thống kê trong phiên, gồm bootstrap từ PostgreSQL nếu có.
                    Chất lượng pipeline xem trang Phân tích.
                  </p>
                  <div className="diag-grid">
                    {Object.entries({
                      "Đã nhận": diag?.telemetry.received,
                      "Chấp nhận": diag?.telemetry.accepted,
                      "Trùng đã bỏ": diag?.telemetry.duplicate,
                      "Cũ / cùng thời điểm": diag?.telemetry.late,
                      "Không hợp lệ": diag?.telemetry.invalid,
                      "Trường thiếu": diag?.telemetry.missingFields,
                    }).map(([k, v]) => (
                      <div key={k}>
                        <small>{k}</small>
                        <strong>{v ?? "—"}</strong>
                      </div>
                    ))}
                  </div>
                  {diag?.telemetry.lastError && (
                    <p className="error">{diag.telemetry.lastError}</p>
                  )}
                  {diag?.telemetry.errors.map((e, i) => (
                    <p className="log" key={i}>
                      {time(e.at)} — {e.reason}
                    </p>
                  ))}
                </section>
              ) : (
                <section className="panel fleet-panel">
                  <div className="section-head">
                    <div>
                      <h2>
                        Toàn cảnh dây chuyền{" "}
                        <span className="count">{scoped.length}</span>
                      </h2>
                      <p>
                        Trạng thái mới nhất đã nhận. Chưa có dữ liệu được giữ là
                        chưa rõ.
                      </p>
                    </div>
                  </div>
                  <div className="toolbar">
                    <div className="tabs">
                      {[
                        "ALL",
                        ...Array.from(new Set(catalog.map((m) => m.lineId))),
                      ].map((l) => (
                        <button
                          key={l}
                          onClick={() => setLine(l)}
                          className={"tab " + (line === l ? "selected" : "")}
                        >
                          {l === "ALL"
                            ? "Tất cả"
                            : "Dây chuyền " + l.replace("LINE-", "")}
                        </button>
                      ))}
                    </div>
                    <div className="filter-tools">
                      <label className="search">
                        <Search size={15} />
                        <input
                          aria-label="Tìm máy"
                          placeholder="Tìm thiết bị..."
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                      </label>
                      <select
                        aria-label="Lọc trạng thái"
                        value={status}
                        onChange={(e) => setStatus(e.target.value)}
                      >
                        <option value="all">Mọi trạng thái</option>
                        {states.map((s, i) => (
                          <option key={s} value={i}>
                            {s}
                          </option>
                        ))}
                        <option value="-1">Chưa rõ</option>
                      </select>
                    </div>
                  </div>
                  <div className="machine-grid">
                    {visible.map((m) => {
                      const s = state(m);
                      const speed = tag(m, "speed");
                      return (
                        <button
                          className={"machine-card state-" + s}
                          key={m.machineId}
                          onClick={() => setSelected(m)}
                        >
                          <div className="machine-top">
                            <span className="machine-icon">
                              <Factory size={19} />
                            </span>
                            <span className={"state-pill s" + s}>
                              <span className="dot" />
                              {states[s] || "Chưa rõ"}
                            </span>
                          </div>
                          <h3>
                            {m.machineName} · {m.machineType}
                          </h3>
                          <p className="machine-code">{m.machineId}</p>
                          <div className="machine-values">
                            <div>
                              <small>Tốc độ theo nguồn</small>
                              <strong>
                                {fmt(speed?.value)} <span>{speed?.unit}</span>
                              </strong>
                            </div>
                            <ChevronRight size={18} />
                          </div>
                          <div className="machine-footer">
                            <span>{m.lineId}</span>
                            <span>
                              Nguồn {time(tag(m, "status")?.eventTime)}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  {visible.length === 0 && (
                    <div className="no-results">
                      {catalog.length
                        ? "Không có máy phù hợp bộ lọc."
                        : "Đang lấy danh mục..."}
                    </div>
                  )}
                  <div className="panel-foot">
                    <span>Hiển thị {visible.length} thiết bị</span>
                    <span>
                      Snapshot theo timestamp · Chưa có heartbeat thiết bị
                    </span>
                  </div>
                </section>
              )}
            </>
          )}
          <footer>
            FACTORY PULSE <span>Nhóm 18 · Data-Integrate</span>
            <span>Realtime metrics</span>
          </footer>
        </div>
      </main>
      {selected && (
        <Detail
          machine={selected}
          tags={snapshot.tags.filter((t) => t.machineId === selected.machineId)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
function Metric({
  label,
  value,
  unit,
  note,
  green,
}: {
  label: string;
  value: string | number;
  unit: string;
  note: string;
  green?: boolean;
}) {
  return (
    <article className={"metric " + (green ? "highlight" : "")}>
      <div className="metric-label">
        {label}
        <span>
          <Boxes size={18} />
        </span>
      </div>
      <div className="metric-value">
        {value}
        <small>{unit}</small>
      </div>
      <p>{note}</p>
    </article>
  );
}
function Detail({
  machine,
  tags,
  onClose,
}: {
  machine: Machine;
  tags: Value[];
  onClose: () => void;
}) {
  const numeric = machine.tags.filter((t) => t.valueType === "Double");
  const [chartTag, setChartTag] = useState("speed");
  const [points, setPoints] = useState<
    { time: string; value: number | null }[]
  >([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    setPoints([]);
    const load = () =>
      get<{ points: { time: string; value: unknown }[] }>(
        `/api/machines/${machine.machineId}/series?tagCode=${chartTag}`,
      )
        .then((r) => {
          if (alive) {
            setPoints(
              r.points.map((p) => ({
                time: time(p.time),
                value: typeof p.value === "number" ? p.value : null,
              })),
            );
            setError("");
          }
        })
        .catch(() => alive && setError("Không tải được biểu đồ."));
    void load();
    const t = setInterval(load, 2000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [machine.machineId, chartTag]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);
  return (
    <div className="overlay" onClick={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={"Chi tiết " + machine.machineId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="detail-head">
          <div>
            <div className="eyebrow">
              {machine.lineId} / {machine.machineId}
            </div>
            <h2>{machine.machineName}</h2>
            <p className="muted">
              {machine.machineType} · Thông số telemetry trong repo
            </p>
          </div>
          <button
            className="close"
            aria-label="Đóng chi tiết"
            onClick={onClose}
          >
            <X />
          </button>
        </div>
        <div className="chart-head">
          <strong>Xu hướng trong phiên</strong>
          <select
            aria-label="Thông số biểu đồ"
            value={chartTag}
            onChange={(e) => setChartTag(e.target.value)}
          >
            {numeric.map((t) => (
              <option key={t.tagCode} value={t.tagCode}>
                {t.tagName} {t.unit}
              </option>
            ))}
          </select>
        </div>
        <p className="chart-note">
          Tối đa 180 cập nhật / trường · Không thay thế kho lịch sử · Null hiển
          thị khoảng đứt
        </p>
        <div className="chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="time" minTickGap={70} tick={{ fontSize: 11 }} />
              <YAxis width={48} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                dataKey="value"
                name={chartTag}
                stroke="#248366"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Thông số</th>
                <th>Giá trị</th>
                <th>Hiện diện</th>
                <th>Thời gian nguồn</th>
              </tr>
            </thead>
            <tbody>
              {machine.tags.map((t) => {
                const v = tags.find((v) => v.tagCode === t.tagCode);
                return (
                  <tr key={t.tagCode}>
                    <td>
                      <strong>{t.tagName}</strong>
                      <small>{t.description}</small>
                    </td>
                    <td className="value-cell">
                      {fmt(v?.value)} <small>{t.unit}</small>
                    </td>
                    <td>
                      <span
                        className={
                          "quality " + (v?.value != null ? "Good" : "unknown")
                        }
                      >
                        {v
                          ? v.value == null
                            ? "Thiếu"
                            : "Có giá trị"
                          : "Chưa nhận"}
                      </span>
                    </td>
                    <td>{time(v?.eventTime)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
function AnalyticsPanel({ catalog }: { catalog: Machine[] }) {
  const today = new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);
  const [machine, setMachine] = useState("M001");
  const [result, setResult] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const load = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(
        await get<Analytics>(
          `/api/analytics?from=${from}&to=${to}&machineId=${encodeURIComponent(machine)}`,
        ),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const names: Record<string, string> = {
    production_metric: "Sản lượng theo máy / sản phẩm / ca / giờ",
    quality_metric: "Chất lượng sản phẩm",
    data_quality_metric: "Chất lượng dữ liệu toàn pipeline",
    downtime_event: "Khoảng dừng máy",
    oee_metric: "OEE và các thành phần A / P / Q",
    machine_metric_1m: "Thông số máy theo cửa sổ 1 phút",
  };
  return (
    <section className="analytics">
      <div className="panel diagnostic">
        <h2>Phân tích từ PostgreSQL</h2>
        <p className="muted">
          Đọc các bảng của Spark; không tự tính lại OEE. Thời gian lọc theo UTC,
          tối đa 31 ngày.
        </p>
        <div className="analytics-filters">
          <label>
            Từ ngày
            <input
              aria-label="Từ ngày"
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </label>
          <label>
            Đến ngày
            <input
              aria-label="Đến ngày"
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
          <label>
            Máy
            <select
              aria-label="Máy phân tích"
              value={machine}
              onChange={(e) => setMachine(e.target.value)}
            >
              <option value="">Tất cả máy</option>
              {catalog.map((m) => (
                <option key={m.machineId} value={m.machineId}>
                  {m.machineId}
                </option>
              ))}
            </select>
          </label>
          <button
            className="primary"
            onClick={() => void load()}
            disabled={loading}
          >
            {loading ? "Đang tải…" : "Truy vấn"}
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <p className="muted">
          Chỉ hiển thị kết quả upstream đã ghi. Bảng rỗng không được hiểu là OEE
          = 0.
        </p>
      </div>
      {result &&
        Object.entries(result.datasets).map(([key, dataset]) => (
          <div className="panel diagnostic dataset" key={key}>
            <h2>
              {names[key] || key}{" "}
              <span className="count">{dataset.rows.length}</span>
            </h2>
            {dataset.scope === "pipeline-all-machines" && (
              <p className="muted">
                Bảng này không có machine_id; bộ lọc máy không áp dụng.
              </p>
            )}
            {dataset.truncated && (
              <p className="error">
                Kết quả giới hạn 1.000 dòng. Hãy thu hẹp bộ lọc; không dùng tập
                bị cắt để tính tổng.
              </p>
            )}
            {dataset.rows.length ? (
              <DataTable rows={dataset.rows} />
            ) : (
              <p className="muted">Chưa có dữ liệu trong khoảng đã chọn.</p>
            )}
          </div>
        ))}
    </section>
  );
}
function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = Object.keys(rows[0]);
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c}>{fmt(r[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
