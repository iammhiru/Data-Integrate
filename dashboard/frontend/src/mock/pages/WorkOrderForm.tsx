// ============================================================================
//  A2 — FORM TẠO / SỬA PHIẾU LỆNH SẢN XUẤT
//
//  Mô phỏng "tạo phiếu" của luồng Vinamilk: chọn chuyền → chọn SKU →
//  kế hoạch số lượng → thời gian dự kiến → ghi chú.
//
//  ⚠ Chỉ tạo được ở trạng thái DRAFT. Muốn chạy phải:
//        Tạo phiếu → Phát hành → Bắt đầu
//    (Phát hành / Bắt đầu nằm ở màn thực thi A3.)
// ============================================================================

import { useMemo, useState } from "react";
import { X, Plus, AlertTriangle } from "lucide-react";
import { createWorkOrder, type CreateWoInput } from "../work-order-api";

export type WorkOrderFormProps = {
  lines: Array<{
    lineId: string;
    displayName: string;
    sku: string | null;
    unit: string | null;
  }>;
  onClose: () => void;
  onCreated: (woId: string) => void;
};

export function WorkOrderForm({ lines, onClose, onCreated }: WorkOrderFormProps) {
  const [lineId, setLineId] = useState<string>(lines[0]?.lineId ?? "");
  const [productId, setProductId] = useState<string>(lines[0]?.sku ?? "");
  const [plannedQty, setPlannedQty] = useState<string>("");
  const [plannedStart, setPlannedStart] = useState<string>("");
  const [plannedEnd, setPlannedEnd] = useState<string>("");
  const [woCode, setWoCode] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [operator, setOperator] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const line = useMemo(() => lines.find((l) => l.lineId === lineId), [lines, lineId]);
  const unit = line?.unit ?? null;

  /** Khi đổi chuyền -> SKU mặc định theo chuyền. */
  const onLineChange = (id: string) => {
    setLineId(id);
    const l = lines.find((x) => x.lineId === id);
    setProductId(l?.sku ?? "");
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!lineId) return setError("Chọn chuyền chạy.");
    if (!productId) return setError("Chọn SKU sản phẩm.");

    const payload: CreateWoInput = {
      line_id: lineId,
      product_id: productId,
      planned_qty: plannedQty ? Number(plannedQty) : null,
      planned_start: plannedStart ? new Date(plannedStart).toISOString() : null,
      planned_end: plannedEnd ? new Date(plannedEnd).toISOString() : null,
      wo_code: woCode.trim() || null,
      unit,
      note: note.trim() || null,
      operator_id: operator.trim() || null,
    };

    setBusy(true);
    try {
      const wo = await createWorkOrder(payload);
      onCreated(wo.woId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wo-modal-scrim" role="dialog" aria-modal="true" aria-label="Tạo phiếu lệnh sản xuất">
      <form className="wo-modal" onSubmit={submit}>
        <header className="wo-modal-head">
          <h2>
            <Plus size={16} /> Tạo phiếu lệnh sản xuất
          </h2>
          <button type="button" className="wo-back" onClick={onClose} title="Đóng">
            <X size={16} />
          </button>
        </header>

        <div className="wo-modal-body">
          <p className="wo-hint">
            Phiếu mới tạo ở trạng thái <strong>Nháp</strong>. Sau khi lưu, sang màn thực thi để{" "}
            <strong>Phát hành</strong> rồi <strong>Bắt đầu</strong> sản xuất.
          </p>

          <div className="wo-form-grid">
            <label className="wo-field">
              <span>Chuyền chạy *</span>
              <select value={lineId} onChange={(e) => onLineChange(e.target.value)} required>
                {lines.map((l) => (
                  <option key={l.lineId} value={l.lineId}>
                    {l.lineId} — {l.displayName}
                  </option>
                ))}
              </select>
            </label>

            <label className="wo-field">
              <span>SKU sản phẩm *</span>
              <select value={productId} onChange={(e) => setProductId(e.target.value)} required>
                <option value="">— chọn SKU —</option>
                {line?.sku ? <option value={line.sku}>{line.sku}</option> : null}
                {lines
                  .map((l) => l.sku)
                  .filter((s): s is string => !!s && s !== line?.sku)
                  .map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
              </select>
            </label>

            <label className="wo-field">
              <span>SL kế hoạch {unit ? `(${unit})` : ""}</span>
              <input
                type="number"
                min={0}
                value={plannedQty}
                onChange={(e) => setPlannedQty(e.target.value)}
                placeholder="VD: 57400"
              />
            </label>

            <label className="wo-field">
              <span>Mã lệnh (tự sinh nếu để trống)</span>
              <input
                type="text"
                value={woCode}
                onChange={(e) => setWoCode(e.target.value)}
                placeholder="VD: WO-261114-0001"
              />
            </label>

            <label className="wo-field">
              <span>Bắt đầu dự kiến</span>
              <input
                type="datetime-local"
                value={plannedStart}
                onChange={(e) => setPlannedStart(e.target.value)}
              />
            </label>

            <label className="wo-field">
              <span>Kết thúc dự kiến</span>
              <input
                type="datetime-local"
                value={plannedEnd}
                onChange={(e) => setPlannedEnd(e.target.value)}
              />
            </label>

            <label className="wo-field">
              <span>Người thao tác</span>
              <input
                type="text"
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                placeholder="VD: operator01"
              />
            </label>

            <label className="wo-field wo-field-wide">
              <span>Ghi chú</span>
              <textarea
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Ghi chú cho lệnh sản xuất…"
              />
            </label>
          </div>

          {error && (
            <div className="wo-error">
              <AlertTriangle size={14} /> {error}
            </div>
          )}
        </div>

        <footer className="wo-modal-foot">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Hủy
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Đang lưu…" : "Lưu phiếu"}
          </button>
        </footer>
      </form>
    </div>
  );
}
