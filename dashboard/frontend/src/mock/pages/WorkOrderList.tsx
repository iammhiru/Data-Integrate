// ============================================================================
//  A1 — DANH SÁCH LỆNH SẢN XUẤT
//
//  Màn hình quản lý Work Order theo luồng chuẩn nhà máy (tham khảo Vinamilk):
//    · Lọc theo chuyền / SKU / trạng thái
//    · Bảng: mã WO, chuyền, sản phẩm, SL kế hoạch, SL thực tế, % tiến độ,
//             trạng thái, giờ bắt đầu – kết thúc
//    · Nút "Tạo phiếu" (A2) và "Mở màn thực thi" (A3)
//
//  Nguồn: master-api `/api/work-orders` (đọc thẳng PostgreSQL qua view
//  `work_order_progress` nên có sẵn số t��n độ).
// ============================================================================

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ClipboardList,
  Plus,
  RefreshCw,
  ChevronRight,
  AlertTriangle,
} from "lucide-react";
import {
  listWorkOrders,
  WO_STATUS_LABEL,
  WO_STATUS_TONE,
  type WorkOrder,
  type WoStatus,
} from "../work-order-api";
import { WorkOrderForm } from "./WorkOrderForm";

export type WorkOrderListProps = {
  onBack: () => void;
  onOpenExecution: (woId: string) => void;
  /** Danh sách chuyền để lọc — lấy từ master data của app. */
  lines: Array<{ lineId: string; displayName: string; sku: string | null; unit: string | null }>;
};

const STATUS_FILTERS: Array<{ value: "" | WoStatus; label: string }> = [
  { value: "", label: "Tất cả" },
  { value: "IN_PROGRESS", label: "Đang chạy" },
  { value: "PAUSED", label: "Tạm dừng" },
  { value: "RELEASED", label: "Đã phát hành" },
  { value: "DRAFT", label: "Nháp" },
  { value: "COMPLETED", label: "Hoàn thành" },
  { value: "CANCELLED", label: "Đã hủy" },
];

function fmtInt(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return Math.round(v).toLocaleString("vi-VN");
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Thoi gian chay cua lenh (actual_start -> actual_end ?? now). */
function fmtDuration(sec: number | null | undefined): string {
  if (!sec) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function WorkOrderList({ onBack, onOpenExecution, lines }: WorkOrderListProps) {
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lineFilter, setLineFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<"" | WoStatus>("");
  const [formOpen, setFormOpen] = useState(false);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const rows = await listWorkOrders({
        lineId: lineFilter || undefined,
        status: statusFilter || undefined,
      });
      setItems(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [lineFilter, statusFilter]);

  useEffect(() => {
    setLoading(true);
    reload();
  }, [reload]);

  /** Tien do: uu tien ratio tu view, fallback so sanh voi ke hoach. */
  const progressOf = (w: WorkOrder): number | null => {
    if (w.progressRatio !== null) return w.progressRatio;
    if (w.plannedQty && w.actualQty !== null) return w.actualQty / w.plannedQty;
    return null;
  };

  const counts = useMemo(() => {
    const running = items.filter((w) => w.status === "IN_PROGRESS").length;
    const paused = items.filter((w) => w.status === "PAUSED").length;
    const draft = items.filter((w) => w.status === "DRAFT").length;
    return { running, paused, draft, total: items.length };
  }, [items]);

  return (
    <div className="wo-page">
      <header className="wo-head">
        <div className="wo-head-left">
          <button className="wo-back" onClick={onBack} title="Quay lại">
            <ChevronRight size={16} style={{ transform: "rotate(180deg)" }} />
          </button>
          <div>
            <h1 className="wo-title">
              <ClipboardList size={18} aria-hidden="true" /> Lệnh sản xuất
            </h1>
            <p className="wo-sub">
              {counts.total} lệnh · {counts.running} đang chạy · {counts.paused} tạm dừng ·{" "}
              {counts.draft} nháp
            </p>
          </div>
        </div>
        <div className="wo-head-actions">
          <button className="btn btn-ghost" onClick={reload} title="Tải lại">
            <RefreshCw size={14} /> Tải lại
          </button>
          <button className="btn btn-primary" onClick={() => setFormOpen(true)}>
            <Plus size={14} /> Tạo phiếu
          </button>
        </div>
      </header>

      <div className="wo-filters">
        <label className="wo-filter">
          <span>Chuyền</span>
          <select value={lineFilter} onChange={(e) => setLineFilter(e.target.value)}>
            <option value="">Tất cả chuyền</option>
            {lines.map((l) => (
              <option key={l.lineId} value={l.lineId}>
                {l.lineId} — {l.displayName}
              </option>
            ))}
          </select>
        </label>
        <label className="wo-filter">
          <span>Trạng thái</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as "" | WoStatus)}
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <div className="wo-error">
          <AlertTriangle size={14} /> Không đọc được danh sách lệnh: {error}
        </div>
      )}

      <div className="wo-table-wrap">
        <table className="wo-table">
          <thead>
            <tr>
              <th>Mã lệnh</th>
              <th>Chuyền</th>
              <th>Sản phẩm</th>
              <th className="num">SL kế hoạch</th>
              <th className="num">SL thực tế</th>
              <th className="num">Good / NG</th>
              <th style={{ width: 160 }}>Tiến độ</th>
              <th>Trạng thái</th>
              <th>Bắt đầu → Kết thúc</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={10} className="wo-empty">
                  Đang tải…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={10} className="wo-empty">
                  Chưa có lệnh sản xuất nào khớp bộ lọc.
                </td>
              </tr>
            )}
            {items.map((w) => {
              const p = progressOf(w);
              const pct = p === null ? 0 : Math.min(Math.max(p * 100, 0), 100);
              return (
                <tr key={w.woId}>
                  <td className="mono strong">{w.woCode}</td>
                  <td>{w.lineId}</td>
                  <td>
                    <span className="wo-sku">{w.productId}</span>
                    {w.unit ? <small className="wo-unit"> ({w.unit})</small> : null}
                  </td>
                  <td className="num">{fmtInt(w.plannedQty)}</td>
                  <td className="num">{fmtInt(w.actualQty)}</td>
                  <td className="num">
                    <span className="wo-good">{fmtInt(w.goodQty)}</span>
                    <span className="wo-sep">/</span>
                    <span className="wo-ng">{fmtInt(w.defectQty)}</span>
                  </td>
                  <td>
                    <div className="wo-progress">
                      <div className="wo-progress-track">
                        <div
                          className="wo-progress-fill"
                          style={{ width: `${pct}%` }}
                          aria-hidden="true"
                        />
                      </div>
                      <span className="wo-progress-text">{fmtPct(p)}</span>
                    </div>
                  </td>
                  <td>
                    <span className={`wo-badge wo-badge-${WO_STATUS_TONE[w.status]}`}>
                      {WO_STATUS_LABEL[w.status]}
                    </span>
                  </td>
                  <td className="wo-time">
                    <span>{fmtTime(w.actualStartTime)}</span>
                    <small>
                      {w.actualEndTime
                        ? `→ ${fmtTime(w.actualEndTime)}`
                        : w.actualStartTime
                          ? `→ đang chạy (${fmtDuration(w.elapsedSec)})`
                          : "chưa chạy"}
                    </small>
                  </td>
                  <td className="wo-row-actions">
                    <button
                      className="btn btn-sm"
                      onClick={() => onOpenExecution(w.woId)}
                      title="Mở màn thực thi lệnh"
                    >
                      Mở
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {formOpen && (
        <WorkOrderForm
          lines={lines}
          onClose={() => setFormOpen(false)}
          onCreated={() => {
            setFormOpen(false);
            reload();
          }}
        />
      )}
    </div>
  );
}
