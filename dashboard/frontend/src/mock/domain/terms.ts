// ============================================================================
//  THUẬT NGỮ — dùng từ tiếng Anh chuẩn ngành sản xuất (MES/SCADA).
//
//  ⚠ YÊU CẦU (12/11): "Nhịp sản xuất", "Đạt kế hoạch ca" là cách diễn đạt
//    không chuẩn. Người vận hành nhà máy dùng thuật ngữ quen thuộc:
//
//    | Thuật ngữ chuẩn   | Viết tắt | Nghĩa / công thức                      |
//    |-------------------|----------|-----------------------------------------|
//    | OEE               | OEE      | Availability × Performance × Quality     |
//    | Availability      | A        | Run Time / Planned Production Time       |
//    | Performance       | P        | (Ideal Cycle × Total Count) / Run Time   |
//    | Quality (Yield)   | Q        | Good Count / Total Count                 |
//    | Plan Attainment   | —        | Actual Output / Planned Output           |
//    | Production Pace   | —        | Actual Output / Planned-to-date Output   |
//    | Running Machines  | —        | Số máy đang chạy                        |
//    | Active Alarms     | —        | Số alarm đang mở                        |
//    | Downtime          | —        | Thời gian dừng máy                       |
//    | Unplanned Downtime| UDT      | Dừng không theo kế hoạch                |
//
//  Mỗi nhãn có 2 dạng: tiếng Anh (chính, hiển thị) + tiếng Việt (tooltip
//  giải thích) để người đọc tiếng Việt vẫn hiểu.
// ============================================================================

export type Term = {
  /** Nhãn hiển thị chính (tiếng Anh chuẩn ngành). */
  en: string;
  /** Giải thích tiếng Việt (hiện ở tooltip / `title`). */
  vi: string;
  /** Công thức hoặc nguồn (hiện ở tooltip). */
  formula?: string;
};

/** Khoá chuẩn hoá để dùng nhất quán ở mọi màn. */
export const TERMS: Record<string, Term> = {
  oee: {
    en: "OEE",
    vi: "Hiệu suất tổng thể thiết bị",
    formula: "Availability × Performance × Quality",
  },
  availability: {
    en: "Availability",
    vi: "Tỷ lệ thời gian máy chạy",
    formula: "Run Time / Planned Production Time",
  },
  performance: {
    en: "Performance",
    vi: "Hiệu suất so với chu kỳ lý tưởng",
    formula: "(Ideal Cycle Time × Total Count) / Run Time",
  },
  quality: {
    en: "Quality",
    vi: "Tỷ lệ sản phẩm đạt (Yield)",
    formula: "Good Count / Total Count",
  },
  planAttainment: {
    en: "Plan Attainment",
    vi: "Tỷ lệ đạt kế hoạch ca",
    formula: "Actual Output / Planned Output (cả ca)",
  },
  productionPace: {
    en: "Production Pace",
    vi: "Nhịp sản xuất so với kế hoạch tích luỹ tới hiện tại",
    formula: "Actual Output / Planned-to-date Output",
  },
  runningMachines: {
    en: "Running Machines",
    vi: "Số máy đang chạy",
  },
  activeAlarms: {
    en: "Active Alarms",
    vi: "Số alarm đang mở",
  },
  output: {
    en: "Output",
    vi: "Sản lượng",
  },
  target: {
    en: "Target",
    vi: "Kế hoạch",
  },
  actual: {
    en: "Actual",
    vi: "Thực tế",
  },
  yield: {
    en: "Yield",
    vi: "Tỷ lệ sản phẩm đạt",
  },
  downtime: {
    en: "Downtime",
    vi: "Thời gian dừng máy",
  },
};

export type TermKey = keyof typeof TERMS;

/** Nhãn hiển thị. */
export function t(key: TermKey): string {
  return TERMS[key].en;
}

/** Tooltip đầy đủ: "Tiếng Việt — công thức". */
export function tip(key: TermKey): string {
  const x = TERMS[key];
  return x.formula ? `${x.vi} — ${x.formula}` : x.vi;
}
