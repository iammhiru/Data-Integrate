// ============================================================================
//  A3 — MÀN THỰC THI WORK ORDER
//
//  "Trái tim" của luồng MES: từ đây người vận hành bấm Bắt đầu / Tạm dừng /
//  Tiếp tục / Hoàn thành, và xem OEE + sản lượng TRỰC TIẾP của lệnh.
//
//  Bốn khối:
//    ① Panel hành động  — nút vòng đời + trạng thái hiện tại
//    ② Panel OEE        — A / P / Q / OEE của lệnh (PlannedTime = actual window)
//    ③ Panel sản lượng  — kế hoạch vs thực tế, Good / NG, tiến độ
//    ④ Panel nhật ký    — log hành động + baseline bộ đếm đã chụp
//
//  ⚠ Khi bấm "Bắt đầu", backend chụp BASELINE bộ đếm của mọi máy thuộc
//    chuyền (chuẩn Vinamilk) → sản lượng của lệnh = raw − baseline, đúng
//    cả khi bộ đếm máy là tích luỹ từ lúc bật nguồn.
// ============================================================================

import { useCallback, useEffect, useState } from "react";
import {
  ChevronRight,
  Play,
  Pause,
  Square,
  CheckCircle2,
  Send,
  XCircle,
  Gauge,
  Package,
  History,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import {
  workOrderAction,
  workOrderLog,
  workOrderBaseline,
  workOrderOee,
  allowedActions,
  WO_ACTION_LABEL,
  WO_STATUS_LABEL,
  WO_STATUS_TONE,
  type WoAction,
  type WoLogEntry,
  type WoBaseline,
  type WoOee,
  type WorkOrder,
} from "../work-order-api";

export type WorkOrderExecutionProps = {
  woId: string;
  onBack: () => void;
};

const ICONS: Record<WoAction, typeof Play> = {
  release: Send,
  start: Play,
  pause: Pause,
  resume: Play,
  complete: CheckCircle2,
  cancel: XCircle,
};

const ACTION_TONE: Record<WoAction, string> = {
  release: "btn-primary",
  start: "btn-primary",
  pause: "btn-warn",
  resume: "btn-primary",
  complete: "btn-ok",
  cancel: "btn-danger",
};

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

function fmtDuration(sec: number | null | undefined): string {
  if (!sec) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return h > 0 ? `${h}h ${m}m ${s}s` : `${m}m ${s}s`;
}

export function WorkOrderExecution({ woId, onBack }: WorkOrderExecutionProps) {
  const [wo, setWo] = useState<WorkOrder | null>(null);
  const [oee, setOee] = useState<WoOee | null>(null);
  const [logs, setLogs] = useState<WoLogEntry[]>([]);
  const [baselines, setBaselines] = useState<WoBaseline[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<WoAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const reload = useCallback(async () => {
    try {
      const [{ listWorkOrders }, logRows, baseRows] = await Promise.all([
        import("../work-order-api"),
        workOrderLog(woId),
        workOrderBaseline(woId),
      ]);
      const rows = await listWorkOrders();
      setWo(rows.find((w) => w.woId === woId) ?? null);
      setLogs(logRows);
      setBaselines(baseRows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [woId]);

  useEffect(() => {
    setLoading(true);
    reload();
  }, [reload]);

  /** Tai OEE cua lenh (poll 5s khi lenh dang chay). */
  const loadOee = useCallback(async () => {
    try {
      setOee(await workOrderOee(woId, "machine"));
    } catch {
      /* im lang — lenh chua bat dau -> chua co OEE */
    }
  }, [woId]);

  useEffect(() => {
    loadOee();
    const t = setInterval(loadOee, 5000);
    return () => clearInterval(t);
  }, [loadOee]);

  const doAction = async (action: WoAction) => {
    setBusy(action);
    setError(null);
    try {
      await workOrderAction(woId, action, {
        operator_id: wo?.operatorId ?? null,
        note: note.trim() || null,
      });
      setNote("");
      await reload();
      await loadOee();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="wo-page wo-loading">
        <Loader2 size={18} className="wo-spin" /> Đang tải lệnh sản xuất…
      </div>
    );
  }

  if (!wo) {
    return (
      <div className="wo-page">
        <div className="wo-error">
          <AlertTriangle size={14} /> Không tìm thấy lệnh {woId}
        </div>
        <button className="btn btn-ghost" onClick={onBack}>
          Quay lại
        </button>
      </div>
    );
  }

  const actions = allowedActions(wo.status);
  const started = !!wo.actualStartTime;
  const planned = wo.plannedQty ?? 0;
  // Backend luon tra khop cau truc, nhung van guard de khong crash React
  // khi API loi / phan hoi cu.
  const counts = oee?.counts ?? { total: 0, good: 0, defect: 0, reject: 0 };
  const time = oee?.time ?? { runSec: 0, stoppedSec: 0, faultedSec: 0, maintSec: 0 };
  const actual = counts.total || wo.actualQty || 0;
  const good = counts.good || wo.goodQty || 0;
  const defect = counts.defect || wo.defectQty || 0;
  const progress = planned > 0 ? actual / planned : wo.progressRatio;

  return (
    <div className="wo-page">
      <header className="wo-head">
        <div className="wo-head-left">
          <button className="wo-back" onClick={onBack} title="Quay lại">
            <ChevronRight size={16} style={{ transform: "rotate(180deg)" }} />
          </button>
          <div>
            <h1 className="wo-title">
              <span className="mono">{wo.woCode}</span>
              <span className={`wo-badge wo-badge-${WO_STATUS_TONE[wo.status]}`}>
                {WO_STATUS_LABEL[wo.status]}
              </span>
            </h1>
            <p className="wo-sub">
              {wo.lineId} · {wo.productId} ·{" "}
              {started ? `bắt đầu ${fmtTime(wo.actualStartTime)}` : "chưa bắt đầu"}
              {started ? ` · chạy ${fmtDuration(oee?.plannedSec ?? wo.elapsedSec)}` : ""}
            </p>
          </div>
        </div>
        <div className="wo-head-actions">
          {actions.map((a) => {
            const Icon = ICONS[a];
            return (
              <button
                key={a}
                className={`btn ${ACTION_TONE[a]}`}
                disabled={busy !== null}
                onClick={() => doAction(a)}
              >
                {busy === a ? (
                  <Loader2 size={14} className="wo-spin" />
                ) : (
                  <Icon size={14} />
                )}
                {WO_ACTION_LABEL[a]}
              </button>
            );
          })}
        </div>
      </header>

      {error && (
        <div className="wo-error">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {!started && (
        <div className="wo-hint-bar">
          Lệnh chưa bắt đầu. Bấm <strong>Phát hành</strong> trước, rồi <strong>Bắt đầu</strong>{" "}
          để chụp mốc bộ đếm và bắt đầu tính OEE cho lệnh này.
        </div>
      )}

      <div className="wo-grid">
        {/* ── ① OEE ─────────────────────────────────────────────────── */}
        <section className="wo-card">
          <h3 className="wo-card-title">
            <Gauge size={15} /> OEE của lệnh
            <small>PlannedTime = actual_start → (actual_end ?? now)</small>
          </h3>
          {oee?.started ? (
            <>
              <div className="wo-oee-main">
                <div className="wo-oee-big">
                  <span className="wo-oee-label">OEE</span>
                  <strong>{fmtPct(oee.oee)}</strong>
                </div>
                <div className="wo-oee-parts">
                  <div className="wo-oee-part">
                    <span>A — Khả dụng</span>
                    <strong>{fmtPct(oee.availability)}</strong>
                  </div>
                  <div className="wo-oee-part">
                    <span>P — Hiệu suất</span>
                    <strong>{fmtPct(oee.performance)}</strong>
                  </div>
                  <div className="wo-oee-part">
                    <span>Q — Chất lượng</span>
                    <strong>{fmtPct(oee.quality)}</strong>
                  </div>
                </div>
              </div>
              <dl className="wo-kv">
                <div>
                  <dt>Giờ chạy</dt>
                  <dd>{fmtDuration(time.runSec)}</dd>
                </div>
                <div>
                  <dt>Dừng (STOPPED)</dt>
                  <dd>{fmtDuration(time.stoppedSec)}</dd>
                </div>
                <div>
                  <dt>Lỗi (FAULTED)</dt>
                  <dd>{fmtDuration(time.faultedSec)}</dd>
                </div>
                <div>
                  <dt>Bảo trì</dt>
                  <dd>{fmtDuration(time.maintSec)}</dd>
                </div>
              </dl>
            </>
          ) : (
            <p className="wo-empty-inline">
              {oee?.message ?? "Chưa có dữ liệu OEE — lệnh chưa bắt đầu."}
            </p>
          )}
        </section>

        {/* ── ② Sản lượng ───────────────────────────────────────────── */}
        <section className="wo-card">
          <h3 className="wo-card-title">
            <Package size={15} /> Sản lượng
          </h3>
          <div className="wo-qty">
            <div className="wo-qty-block">
              <span>Kế hoạch</span>
              <strong>{fmtInt(planned)}</strong>
            </div>
            <div className="wo-qty-block">
              <span>Thực tế</span>
              <strong>{fmtInt(actual)}</strong>
            </div>
            <div className="wo-qty-block wo-qty-good">
              <span>Good</span>
              <strong>{fmtInt(good)}</strong>
            </div>
            <div className="wo-qty-block wo-qty-ng">
              <span>NG</span>
              <strong>{fmtInt(defect)}</strong>
            </div>
          </div>
          <div className="wo-progress wo-progress-lg">
            <div className="wo-progress-track">
              <div
                className="wo-progress-fill"
                style={{ width: `${Math.min(Math.max((progress ?? 0) * 100, 0), 100)}%` }}
                aria-hidden="true"
              />
            </div>
            <span className="wo-progress-text">{fmtPct(progress)}</span>
          </div>
          <dl className="wo-kv">
            <div>
              <dt>Tỉ lệ NG</dt>
              <dd>
                {actual > 0 ? fmtPct((total0(defect) / actual) as number) : "—"}
              </dd>
            </div>
            <div>
              <dt>Đơn vị</dt>
              <dd>{wo.unit ?? "—"}</dd>
            </div>
          </dl>
        </section>

        {/* ── ③ Hành động + nhật ký ─────────────────────────────────── */}
        <section className="wo-card">
          <h3 className="wo-card-title">
            <Square size={15} /> Ghi chú & nhật ký
          </h3>
          <label className="wo-field">
            <span>Ghi chú cho hành động</span>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="VD: đổi lô, dừng kỹ thuật…"
              disabled={actions.length === 0}
            />
          </label>

          <div className="wo-log">
            {logs.length === 0 && <p className="wo-empty-inline">Chưa có hành động nào.</p>}
            {logs.map((l) => (
              <div key={l.logId} className="wo-log-row">
                <span className="wo-log-time">{fmtTime(l.actionAt)}</span>
                <span className="wo-log-action">{l.action}</span>
                <span className="wo-log-transition">
                  {l.oldStatus ?? "—"} → {l.newStatus ?? "—"}
                </span>
                <span className="wo-log-by">{l.actionBy ?? ""}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── ④ Baseline bộ đếm ────────────────────────────────────── */}
        <section className="wo-card">
          <h3 className="wo-card-title">
            <History size={15} /> Mốc bộ đếm (baseline)
            <small>WO_VALUE = raw − baseline</small>
          </h3>
          {baselines.length === 0 ? (
            <p className="wo-empty-inline">
              Chưa chụp baseline — sẽ tự chụp khi bấm <strong>Bắt đầu</strong>.
            </p>
          ) : (
            <div className="wo-table-wrap wo-table-wrap-sm">
              <table className="wo-table">
                <thead>
                  <tr>
                    <th>Máy</th>
                    <th>Bộ đếm</th>
                    <th className="num">Mốc</th>
                  </tr>
                </thead>
                <tbody>
                  {baselines.map((b) => (
                    <tr key={`${b.machineId}-${b.tagCode}`}>
                      <td className="mono">{b.machineId}</td>
                      <td>{b.tagCode}</td>
                      <td className="num">{fmtInt(b.baselineValue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

/** Tránh NaN khi chia 0. */
function total0(v: number): number {
  return Number.isFinite(v) ? v : 0;
}
