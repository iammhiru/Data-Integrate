// ============================================================================
//  ProcessFlow — sơ đồ dòng chảy KHÔNG thanh trượt ngang.
//
//  Yêu cầu: "tránh cho việc thanh trượt xuất hiện trong các component".
//
//  ══ BỐ CỤC RẮN (boustrophedon) ══
//  Một dây chuyền là chuỗi công đoạn TUẦN TỰ. Nếu xếp theo kiểu "xuôi hàng"
//  (row-major: hàng 1 trái→phải, hàng 2 cũng trái→phải) thì card cuối hàng 1
//  nằm bên PHẢI còn card đầu hàng 2 nằm bên TRÁI → mạch sản phẩm bị cắt đứt,
//  người vận hành đọc sai thứ tự công đoạn.
//
//  Giải pháp: mỗi hàng ĐẢO CHIỀU so với hàng trước (rắn). Mũi tên nối liền
//  từ card cuối hàng này xuống card đầu hàng kế tiếp, ngay dưới cùng một cột.
//  Mỗi card mang SỐ THỨ TỰ công đoạn → nhìn bằng mắt vẫn đọc đúng thứ tự
//  dù hàng nào bị đảo.
//
//  Cách làm:
//    - Số cột tính bằng `ResizeObserver` từ bề rộng THẬT của container.
//    - Mũi tên nối vẽ trên LỚP PHỦ (`pointer-events:none`, `overflow:hidden`),
//      vị trí đo bằng `getBoundingClientRect()` → luôn khớp layout thực tế,
//      KHÔNG BAO GIỜ làm tăng `scrollWidth`.
// ============================================================================

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, ArrowLeft, ArrowDown } from "lucide-react";
import type { MachineStateView } from "../store";

/** Bề rộng tối thiểu của một card máy — dùng để tính số cột. */
const CARD_MIN_W = 190;
/** Khe ngang giữa các cột — phải khớp với `.flow-row` trong app.css. */
const GAP = 26;
/** Khe dọc giữa các hàng — phải khớp với `.flow-grid` trong app.css. */
const ROW_GAP = 34;

type Link = {
  key: string;
  /** "h" = nối ngang trong hàng, "v" = rẽ xuống hàng sau. */
  kind: "h" | "v";
  /** "r" = mũi tên hướng phải, "l" = hướng trái. */
  dir: "r" | "l";
  x: number;
  y: number;
};

/**
 * Chia `n` máy thành `rowsCount` hàng, mỗi hàng tối đa `cols` máy.
 * Các hàng được LÀM ĐẦY TRƯỚC (hàng trên nhiều máy hơn, hàng dưới ít hơn)
 * → hình sơ đồ cân bằng và mũi tên rẽ xuống luôn nối đúng cột.
 */
function rowSizes(n: number, cols: number, rowsCount: number): number[] {
  const sizes: number[] = [];
  let left = n;
  for (let i = 0; i < rowsCount; i++) {
    const take = Math.min(cols, left);
    sizes.push(take);
    left -= take;
  }
  return sizes;
}

export function ProcessFlow({
  machines,
  renderCard,
}: {
  machines: MachineStateView[];
  renderCard: (m: MachineStateView) => React.ReactNode;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const [cols, setCols] = useState(1);
  const [links, setLinks] = useState<Link[]>([]);

  // Chia thành các hàng: hàng trên đầy trước, hàng dưới ít dần.
  const rows = useMemo(() => {
    if (!machines.length) return [];
    const rowsCount = Math.ceil(machines.length / cols);
    const sizes = rowSizes(machines.length, cols, rowsCount);
    const out: MachineStateView[][] = [];
    let idx = 0;
    for (const size of sizes) {
      out.push(machines.slice(idx, idx + size));
      idx += size;
    }
    return out;
  }, [machines, cols]);

  // Tính số cột theo bề rộng thật — không đoán bằng media query.
  //
  // ⚠ BỔ SUNG: ưu tiên số cột CHIA ĐỀU các hàng (chênh lệch ≤ 1 máy giữa
  //   các hàng) để hình sơ đồ cân đối, thay vì dồn hết vào 1 hàng rồi để
  //   hàng cuối lệch (9 máy: 6+3 trông rất vỡ). Ưu tiên CÁI LỚN nhất vẫn vừa
  //   bề rộng để card không quá nhỏ.
  useEffect(() => {
    const el = gridRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      if (!w) return;
      // n cột + (n-1) khe phải vừa bề rộng → n = floor((w + gap) / (card + gap))
      const fit = Math.max(1, Math.floor((w + GAP) / (CARD_MIN_W + GAP)));
      const n = machines.length;
      let best = 1;
      for (let c = Math.min(fit, n); c >= 1; c--) {
        const rowsCount = Math.ceil(n / c);
        const sizes = rowSizes(n, c, rowsCount);
        const spread = Math.max(...sizes) - Math.min(...sizes);
        // Chênh lệch ≤ 1 máy giữa các hàng → chọn.
        if (spread <= 1) {
          best = c;
          break;
        }
      }
      setCols(best);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machines.length]);

  /**
   * Đo vị trí thật của từng card và suy ra vị trí mũi tên.
   *
   * Không giả định thứ tự trái→phải: hướng mũi tên được suy từ vị trí thật
   * (card kế tiếp nằm bên phải hay bên trái), nên đúng với cả hàng thuận và
   * hàng đảo.
   */
  const measureLinks = useCallback(() => {
    const grid = gridRef.current;
    if (!grid) return;
    const gr = grid.getBoundingClientRect();
    const nodes = [...grid.querySelectorAll<HTMLElement>(".flow-node")];
    if (nodes.length < 2) {
      setLinks([]);
      return;
    }

    const rects = nodes.map((n) => n.getBoundingClientRect());
    const out: Link[] = [];

    for (let i = 0; i < rects.length - 1; i++) {
      const a = rects[i];
      const b = rects[i + 1];
      const key = machines[i].def.machineId;
      const sameRow = Math.abs(a.top - b.top) < 4;

      if (sameRow) {
        // Cùng hàng → mũi tên ngang, đặt giữa khe giữa 2 card.
        const toRight = b.left > a.right;
        const gapMid = toRight ? (a.right + b.left) / 2 : (a.left + b.right) / 2;
        out.push({
          key: `h-${key}`,
          kind: "h",
          dir: toRight ? "r" : "l",
          x: gapMid - gr.left,
          y: a.top + a.height / 2 - gr.top,
        });
      } else {
        // Sang hàng mới → mũi tên rẽ xuống.
        //
        // ⚠ BUG ĐÃ SỬA (2 lần):
        //   1. Trước đây đặt ở mép PHẢI card cuối hàng (a.right − 8) trong khi
        //      card tiếp theo nằm mép TRÁI hàng sau → mũi tên không nối vào
        //      card nào, đọc hình như máy bị "rơi".
        //   2. Lần sau đặt ở giữa khe (a.right + b.right)/2 → rơi đúng mép phải
        //      của lưới, mũi tên 16px tràn ra ngoài → sinh thanh trượt ngang.
        //   Nay đặt ở GIỮA CỘT (theo bề rộng card cuối hàng) → nằm trọn trong
        //   lưới, đúng trên trục card đầu hàng sau (bố cục rắn: 2 card đó
        //   cùng cột nên trục là trục của cả cột).
        const colCenter = (a.left + a.right) / 2;
        out.push({
          key: `v-${key}`,
          kind: "v",
          dir: "r",
          x: colCenter - gr.left,
          y: (a.bottom + b.top) / 2 - gr.top,
        });
      }
    }
    setLinks(out);
  }, [machines]);

  useLayoutEffect(() => {
    measureLinks();
  }, [cols, machines, measureLinks]);

  useEffect(() => {
    const grid = gridRef.current;
    if (!grid) return;
    const ro = new ResizeObserver(() => measureLinks());
    ro.observe(grid);
    return () => ro.disconnect();
  }, [measureLinks]);

  return (
    <div className="flow-grid-wrap" ref={wrapRef}>
      <div className="flow-grid" ref={gridRef}>
        {rows.map((row, ri) => (
          <div
            key={ri}
            className={`flow-row${ri % 2 === 1 ? " flow-row-rev" : ""}`}
          >
            {row.map((m) => {
              const step = machines.indexOf(m) + 1;
              return (
                <div className="flow-node" key={m.def.machineId}>
                  <div className="flow-card">
                    <span className="flow-step num" aria-hidden="true">
                      {step}
                    </span>
                    {renderCard(m)}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Lớp phủ mũi tên — không ảnh hưởng layout (pointer-events: none). */}
      <div className="flow-overlay" aria-hidden="true">
        {links.map((l) =>
          l.kind === "h" ? (
            <span
              key={l.key}
              className={`flow-link flow-link-h${l.dir === "l" ? " flow-link-l" : ""}`}
              style={{ left: l.x, top: l.y }}
            >
              {l.dir === "l" ? <ArrowLeft size={16} /> : <ArrowRight size={16} />}
            </span>
          ) : (
            <span
              key={l.key}
              className="flow-link flow-link-v"
              style={{ left: l.x, top: l.y }}
            >
              <ArrowDown size={16} />
            </span>
          ),
        )}
      </div>
    </div>
  );
}
