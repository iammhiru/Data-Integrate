// ============================================================================
//  MES DASHBOARD — Ứng dụng chính (vẫn dùng dữ liệu MOCK ở giai đoạn hiện tại).
//
//  Kiến trúc 4 màn:
//    ① Plant Overview   — tổng quan nhà máy
//    ② Line View        — sơ đồ dòng chảy của 1 dây chuyền
//    ③ Machine Detail   — popup (overlay) chi tiết thiết bị
//    ④ Alarm & Event    — trung tâm alarm & sự kiện
//
//  ⚠ ROUTING (12/11): `machine` KHÔNG còn thay thế nội dung trang như trước.
//    Trước đây mở máy → `{name:"machine"}` làm màn hình bị thay trọn → nền
//    phía sau "biến mất", và đóng popup → luôn về màn đầu tiên ("plant").
//    Nay:
//      • `page`   = màn nền (plant | line | alarms) — LUÔN được render.
//      • `drawer` = popup thiết bị (machineId | null) — overlay trên nền.
//    Đóng popup → về đúng màn nền đang ở trước đó (không nhảy về plant).
//
//  Nguồn dữ liệu: `mock-simulator.ts`. Khi tích hợp thật, chỉ thay lớp
//  `TelemetrySource` (xem store.ts) bằng SignalR client — toàn bộ `domain/*`
//  và `pages/*` giữ nguyên.
// ============================================================================

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Factory,
  LayoutDashboard,
  Activity,
  Bell,
  ChevronRight,
  Sun,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { MACHINES } from "./catalog.gen";
import { MockSimulator } from "./mock-simulator";
import { buildStore, TelemetryContext, type TelemetryStore } from "./store";
import { PlantOverview } from "./pages/PlantOverview";
import { LineView } from "./pages/LineView";
import { MachineDetail } from "./pages/MachineDetail";
import { AlarmCenter } from "./pages/AlarmCenter";
import { UserMenu } from "./components/UserMenu";
import { useTheme } from "./domain/use-theme";
import { shiftLabel } from "./domain/shift";
import "./tokens.css";
import "./app.css";

/** Màn nền — luôn được render, không bị popup che xóa. */
type Page = "plant" | "line" | "alarms";

/** Popup thiết bị đang mở (null = đóng). */
type Drawer = { machineId: string; fromLine?: string } | null;

export default function MockApp() {
  const sim = useMemo(() => new MockSimulator(MACHINES), []);
  const [store, setStore] = useState<TelemetryStore>(() => buildStore(sim));
  const [page, setPage] = useState<Page>("plant");
  const [lineId, setLineId] = useState<string>("LINE_01");
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [connected, setConnected] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { theme, toggle: toggleTheme } = useTheme();

  // Vòng cập nhật 1 Hz — tương đương SignalR push 1 snapshot/s.
  useEffect(() => {
    const t = setInterval(() => {
      setStore(buildStore(sim));
    }, 1000);
    return () => clearInterval(t);
  }, [sim]);

  // Ghi lịch sử cho sparkline.
  useEffect(() => {
    for (const m of store.machines) {
      for (const t of m.def.tags) {
        if (t.tagType !== "ANALOG") continue;
        const v = m.values[t.name];
        if (typeof v === "number") sim.pushHistory(m.def.machineId, t.name, v);
      }
    }
    // Lịch sử sản lượng theo line (để vẽ Production Trend).
    for (const l of store.lines) {
      sim.pushOutput(l.meta.lineId, l.output.good, l.output.total);
    }
  }, [store, sim]);

  const openLine = useCallback((id: string) => {
    setLineId(id);
    setPage("line");
    setDrawer(null);
  }, []);

  /**
   * Mở popup thiết bị — KHÔNG đổi màn nền.
   * `fromLine` nhớ line đang xem để breadcrumb của popup hiển thị đúng.
   */
  const openMachine = useCallback(
    (machineId: string) => {
      setDrawer({ machineId, fromLine: page === "line" ? lineId : undefined });
    },
    [page, lineId],
  );

  /** Đóng popup → quay về đúng màn nền đang ở (không nhảy về plant). */
  const closeDrawer = useCallback(() => setDrawer(null), []);

  const navigate = useCallback((p: Page) => {
    setPage(p);
    setDrawer(null);
  }, []);

  const currentLine = page === "line" ? lineId : undefined;

  return (
    <TelemetryContext.Provider value={store}>
      <div className={"shell" + (sidebarCollapsed ? " shell-collapsed" : "")}>
        <Sidebar
          page={page}
          lineId={lineId}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
          onNavigate={navigate}
          onOpenLine={openLine}
        />

        <div className="main">
          <TopBar
            store={store}
            connected={connected}
            onToggleConnection={() => setConnected((c) => !c)}
            currentLine={currentLine}
            onOpenAlarms={() => navigate("alarms")}
            theme={theme}
            onToggleTheme={toggleTheme}
          />
          <main className="content">
            {/*
              ⚠ MÀN NỀN LUÔN ĐƯỢC RENDER.
                Trước đây `{route.name === "machine" && <MachineDetail/>}` thay
                thế toàn bộ → nền bị xóa. Nay popup là overlay trên nền.
            */}
            {page === "plant" && <PlantOverview onOpenLine={openLine} />}
            {page === "line" && (
              <LineView
                lineId={lineId}
                onBack={() => navigate("plant")}
                onOpenMachine={openMachine}
                onSelectLine={openLine}
              />
            )}
            {page === "alarms" && (
              <AlarmCenter onBack={() => navigate("plant")} onOpenMachine={openMachine} />
            )}
          </main>
        </div>

        {/*
          POPUP THIẾT BỊ — overlay trên màn nền (không thay thế nội dung).
          Render ngoài `.main` để không bị giới hạn bởi layout của trang.
        */}
        {drawer && (
          <MachineDetail machineId={drawer.machineId} onClose={closeDrawer} />
        )}
      </div>
    </TelemetryContext.Provider>
  );
}

// ── Sidebar ──────────────────────────────────────────────────────────────
function Sidebar({
  page,
  lineId,
  collapsed,
  onToggleCollapse,
  onNavigate,
  onOpenLine,
}: {
  page: Page;
  lineId: string;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onNavigate: (p: Page) => void;
  onOpenLine: (lineId: string) => void;
}) {
  const items = [
    { key: "plant", icon: LayoutDashboard, label: "Tổng quan nhà máy", go: () => onNavigate("plant") },
    { key: "line", icon: Factory, label: "Dây chuyền", go: () => onOpenLine(lineId) },
    { key: "alarms", icon: Bell, label: "Alarm & Sự kiện", go: () => onNavigate("alarms") },
  ];

  return (
    <aside className={"sidebar" + (collapsed ? " sidebar-collapsed" : "")}>
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <Factory size={18} />
        </span>
        <span className="brand-text">
          MES
          <small>Manufacturing Execution</small>
        </span>
      </div>

      <nav className="nav" aria-label="Điều hướng chính">
        <div className="nav-label">Vận hành</div>
        {items.map((it) => (
          <button
            key={it.key}
            className={`nav-item${page === it.key ? " active" : ""}`}
            onClick={it.go}
            aria-current={page === it.key ? "page" : undefined}
            title={collapsed ? it.label : undefined}
          >
            <it.icon size={16} aria-hidden="true" />
            <span className="nav-item-label">{it.label}</span>
          </button>
        ))}
      </nav>

      <div className="side-foot">
        {/*
          ⚠ YÊU CẦU (12/11): khối thông tin user đã chuyển lên GÓC TRÊN BÊN
          PHẢI header (component `UserMenu`). Ở sidebar chỉ giữ thông tin phạm
          vi dữ liệu của phiên mock.
        */}
        <div className="side-foot-row">
          <span>PLANT_01</span>
          <span className="num">{MACHINES.length}</span>
        </div>
        <small>26 máy · 404 tag · 4 channel</small>
      </div>

      {/* Nút thu gọn sidebar — luôn ở góc dưới, dễ bấm. */}
      <button
        className="sidebar-collapse"
        onClick={onToggleCollapse}
        aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
        title={collapsed ? "Mở rộng" : "Thu gọn"}
      >
        {collapsed ? <PanelLeftOpen size={16} aria-hidden="true" /> : <PanelLeftClose size={16} aria-hidden="true" />}
      </button>
    </aside>
  );
}

// ── Topbar: context toàn cục ────────────────────────────────────────────
function TopBar({
  store,
  connected,
  onToggleConnection,
  currentLine,
  onOpenAlarms,
  theme,
  onToggleTheme,
}: {
  store: TelemetryStore;
  connected: boolean;
  onToggleConnection: () => void;
  currentLine?: string;
  onOpenAlarms: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}) {
  const alarmCount = store.machines.filter((m) => m.values.AlarmCode).length;

  return (
    <header className="topbar">
      <div className="topbar-context">
        <span className="ctx-plant">PLANT_01</span>
        {currentLine && (
          <>
            <ChevronRight size={13} aria-hidden="true" />
            <span className="ctx-line">{currentLine}</span>
          </>
        )}
        <ChevronRight size={13} aria-hidden="true" />
        <span className="ctx-shift">{shiftLabel()}</span>
      </div>

      {/*
        ⚠ YÊU CẦU (12/11): bảng đếm trạng thái máy ("Đang chạy 20 · Dừng 2 …")
        ĐÃ BỎ khỏi topbar. Topbar chỉ giữ: điều hướng ngữ cảnh, kết nối,
        đồng hồ, thông báo, đổi theme và menu người dùng.
        Chú giải trạng thái → component `StatusSummary`, render ở màn cần.
      */}
        <div className="topbar-right">
          {/*
            ⚠ 12/11: liên kết tới trang CHẨN ĐOÁN PIPELINE (Factory Pulse) —
            app cũ, hữu ích cho mục tiêu tích hợp dữ liệu (Kafka → backend →
            SignalR, độ trễ, chất lượng dữ liệu, truy vấn PostgreSQL).
          */}
          <a
            className="diag-link"
            href="/diagnostics.html"
            title="Trang chẩn đoán pipeline dữ liệu (Factory Pulse)"
          >
            Chẩn đoán dữ liệu
          </a>
          <button
            className="theme-toggle"
            onClick={onToggleTheme}
            title={theme === "light" ? "Chuyển theme tối" : "Chuyển theme sáng"}
            aria-label={theme === "light" ? "Chuyển theme tối" : "Chuyển theme sáng"}
          >
            {theme === "light" ? <Moon size={15} aria-hidden="true" /> : <Sun size={15} aria-hidden="true" />}
          </button>
        <div className="topbar-divider" />
        <button
          className={`conn${connected ? " ok" : " bad"}`}
          onClick={onToggleConnection}
          title="Nhấn để mô phỏng mất kết nối / kết nối lại"
        >
          {connected ? "Đang kết nối" : "Mất kết nối"}
        </button>
        <button className="bell" onClick={onOpenAlarms} aria-label={`${alarmCount} alarm đang mở`}>
          <Bell size={16} aria-hidden="true" />
          {alarmCount > 0 && <span className="bell-count num">{alarmCount}</span>}
        </button>
        <span className="clock num">
          {new Date().toLocaleTimeString("vi-VN", { hour12: false })}
        </span>
        <div className="topbar-divider" />
        <UserMenu />
      </div>
    </header>
  );
}
