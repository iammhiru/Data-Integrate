// ============================================================================
//  Metric Profile — định nghĩa thông số hiển thị theo machineType
//  Nguồn: docs/MES_UI_Concept_v1.0.md §B.2 / §C.5
//
//  Nguyên tắc: KHÔNG hard-code theo machineId. Profile theo machineType +
//  nhóm tag đã khai báo trong catalog → máy mới tự động có UI đúng.
//
//  Mỗi metric khai báo:
//    - label : nhãn tiếng Việt hiển thị
//    - tags  : 1..n tag nguồn. 1 tag = hiển thị trực tiếp.
//               nhiều tag = hiển thị dạng "actual / setpoint" (2 tag)
//    - kind  : 'value' | 'ratio' (actual/setpoint) | 'counter' | 'flag'
// ============================================================================

export type MetricKind = "value" | "ratio" | "counter" | "flag";

export type MetricDef = {
  label: string;
  /** tag thực (khi kind = ratio, tags[0] = actual, tags[1] = setpoint). */
  tags: string[];
  kind: MetricKind;
  /** Ghi chú/tooltip giải thích ý nghĩa nghiệp vụ. */
  hint?: string;
};

export type MetricGroup = {
  title: string;
  metrics: MetricDef[];
};

/**
 * Bộ đếm "sản phẩm đạt" đặc trưng của từng loại máy.
 *
 * Không phải máy nào cũng có `GoodCounter` — catalog gốc của middleware chỉ
 * khai báo `GoodCounter` cho 24/26 máy; DATE_CODER chỉ có `PrintCount`.
 * UI phải đọc đúng bộ đếm sẵn có thay vì hiện "—".
 */
const COUNTER_TAG_BY_TYPE: Record<string, string> = {
  DATE_CODER: "PrintCount",
  BOTTLE_LABELER: "LabelApplyCount",
  CAN_INSPECTION: "InspectionCount",
};

/** Tag bộ đếm đặc trưng của loại máy (null = máy không đếm sản phẩm). */
export function counterTagFor(machineType: string): string | null {
  if (machineType === "CIP_SKID") return null;
  return COUNTER_TAG_BY_TYPE[machineType] ?? "GoodCounter";
}

/** Nhãn tiếng Việt cho bộ đếm đặc trưng. */
export function counterTagLabel(machineType: string): string {
  switch (machineType) {
    case "DATE_CODER":
      return "Lượt in";
    case "BOTTLE_LABELER":
      return "Lượt dán";
    case "CAN_INSPECTION":
      return "Lượt kiểm tra";
    case "CIP_SKID":
      return "Chu kỳ CIP";
    default:
      return "Đạt";
  }
}

/** Nhóm dùng chung cho mọi máy (tầng 1 — Core). */
const CORE_SPEED: MetricDef = {
  label: "Tốc độ",
  tags: ["CurrentSpeed", "DesignSpeed"],
  kind: "ratio",
  hint: "Tốc độ thực tế so với tốc độ thiết kế (setpoint).",
};

const CORE_FLAGS: MetricDef[] = [
  { label: "Dừng khẩn", tags: ["EmergencyStop"], kind: "flag" },
  { label: "Thiếu NL", tags: ["Starved"], kind: "flag" },
  { label: "Tắc nghẽn", tags: ["Blocked"], kind: "flag" },
  { label: "Alarm", tags: ["AlarmCode"], kind: "flag" },
];

/**
 * Profile theo machineType. Thứ tự nhóm = thứ tự hiển thị.
 * Chỉ khai báo nhóm ĐẶC TRƯNG; phần Core được ghép tự động.
 */
export const METRIC_PROFILES: Record<string, MetricGroup[]> = {
  // ── Chiết rót ────────────────────────────────────────────────────────
  CARBONATED_FILLER: [
    {
      title: "Chiết rót",
      metrics: [
        { label: "Mức chiết", tags: ["FillLevel"], kind: "value", hint: "Mức chất lỏng trong chai (% so với dung tích định)." },
        { label: "Tốc độ chiết", tags: ["FillRate"], kind: "value", hint: "Tốc độ chiết rót thực tế của đầu chiết." },
        { label: "Số đầu chiết", tags: ["HeadCount"], kind: "value" },
        { label: "Nhiệt độ SP", tags: ["ProductTemp"], kind: "value", hint: "Nhiệt độ sản phẩm trong bình." },
      ],
    },
    {
      title: "Khí CO₂",
      metrics: [
        { label: "Áp suất CO₂", tags: ["CO2Pressure"], kind: "value", hint: "Áp suất khí carbon dioxide trong bình." },
        { label: "Lưu lượng CO₂", tags: ["CO2FlowRate"], kind: "value" },
      ],
    },
  ],

  STILL_FILLER: [
    {
      title: "Chiết rót",
      metrics: [
        { label: "Mức chiết", tags: ["FillLevel"], kind: "value", hint: "Mức chất lỏng trong chai (% so với dung tích định)." },
        { label: "Tốc độ chiết", tags: ["FillRate"], kind: "value" },
        { label: "Số đầu chiết", tags: ["HeadCount"], kind: "value" },
        { label: "Nhiệt độ SP", tags: ["ProductTemp"], kind: "value" },
      ],
    },
    {
      title: "Nước & áp suất",
      metrics: [
        { label: "Áp suất chiết", tags: ["FillingPressure"], kind: "value" },
        { label: "Nhiệt độ nước", tags: ["WaterTemp"], kind: "value" },
        { label: "Độ dẫn nước", tags: ["WaterConductivity"], kind: "value", hint: "Độ dẫn điện của nước — chỉ số chất lượng nước đầu vào." },
      ],
    },
  ],

  CAN_FILLER: [
    {
      title: "Chiết rót",
      metrics: [
        { label: "Mức chiết", tags: ["FillLevel"], kind: "value" },
        { label: "Tốc độ chiết", tags: ["FillRate"], kind: "value" },
        { label: "Số đầu chiết", tags: ["HeadCount"], kind: "value" },
        { label: "Nhiệt độ SP", tags: ["ProductTemp"], kind: "value" },
      ],
    },
    {
      title: "Khí CO₂",
      metrics: [
        { label: "Áp suất CO₂", tags: ["CO2Pressure"], kind: "value" },
        { label: "Lưu lượng CO₂", tags: ["CO2FlowRate"], kind: "value" },
      ],
    },
  ],

  // ── Thổi khuôn ───────────────────────────────────────────────────────
  STRETCH_BLOW_MOULDER: [
    {
      title: "Thổi khuôn",
      metrics: [
        { label: "Nhiệt độ khuôn", tags: ["MoldTemp"], kind: "value", hint: "Nhiệt độ khuôn — quyết định chất lượng chai." },
        { label: "Nhiệt độ heater", tags: ["HeaterTemp"], kind: "value" },
        { label: "Áp suất thổi", tags: ["BlowPressure"], kind: "value" },
        { label: "Khối lượng chai", tags: ["BottleWeight"], kind: "value", hint: "Trọng lượng chai thành phẩm — kiểm soát độ mỏng thành." },
        { label: "Số khuôn", tags: ["CavityCount"], kind: "value" },
        { label: "Chu kỳ", tags: ["CycleTime"], kind: "value", hint: "Thời gian một chu kỳ thổi (giây)." },
      ],
    },
  ],

  // ── Cấp preform ──────────────────────────────────────────────────────
  PREFORM_FEEDER: [
    {
      title: "Cấp preform",
      metrics: [
        { label: "Mực phễu", tags: ["HopperLevel"], kind: "value", hint: "Mức còn lại trong phễu (%)." },
        { label: "Tốc độ cấp", tags: ["PreformFeedRate"], kind: "value" },
      ],
    },
  ],

  // ── Băng tải khí ──────────────────────────────────────────────────────
  AIR_CONVEYOR: [
    {
      title: "Vận chuyển khí",
      metrics: [
        { label: "Lưu lượng khí", tags: ["AirFlowRate"], kind: "value" },
        { label: "Áp suất khí", tags: ["AirPressure"], kind: "value" },
        { label: "Tốc độ motor", tags: ["MotorSpeed"], kind: "value" },
      ],
    },
  ],

  // ── Rửa ──────────────────────────────────────────────────────────────
  BOTTLE_RINSER: [
    {
      title: "Rửa",
      metrics: [
        { label: "Nhiệt độ nước rửa", tags: ["RinseWaterTemp"], kind: "value" },
        { label: "Áp suất nước rửa", tags: ["RinseWaterPressure"], kind: "value" },
        { label: "Lưu lượng nước rửa", tags: ["RinseWaterFlowRate"], kind: "value" },
        { label: "Áp suất vòi", tags: ["NozzlePressure"], kind: "value" },
        { label: "Pha CIP", tags: ["CIPPhase"], kind: "value", hint: "Bước hiện tại của chu kỳ CIP của máy này." },
      ],
    },
  ],

  CAN_RINSER: [
    {
      title: "Rửa",
      metrics: [
        { label: "Nhiệt độ nước rửa", tags: ["RinseWaterTemp"], kind: "value" },
        { label: "Áp suất nước rửa", tags: ["RinseWaterPressure"], kind: "value" },
        { label: "Lưu lượng nước rửa", tags: ["RinseWaterFlowRate"], kind: "value" },
        { label: "Áp suất vòi", tags: ["NozzlePressure"], kind: "value" },
        { label: "Pha CIP", tags: ["CIPPhase"], kind: "value" },
      ],
    },
  ],

  // ── Siết nắp ─────────────────────────────────────────────────────────
  SCREW_CAPPER: [
    {
      title: "Siết nắp",
      metrics: [
        { label: "Mô-men siết", tags: ["Torque"], kind: "value", hint: "Mô-men siết nắp thực tế (Nm)." },
        { label: "Tốc độ cấp nắp", tags: ["CapFeedRate"], kind: "value" },
      ],
    },
  ],

  // ── Dán nhãn ─────────────────────────────────────────────────────────
  BOTTLE_LABELER: [
    {
      title: "Dán nhãn",
      metrics: [
        { label: "Cuộn nhãn còn", tags: ["LabelRollRemaining"], kind: "value", hint: "Chiều dài cuộn nhãn còn lại (m)." },
      ],
    },
  ],

  // ── In mã ngày ───────────────────────────────────────────────────────
  DATE_CODER: [
    {
      title: "In mã ngày",
      metrics: [
        { label: "Mực còn", tags: ["InkLevel"], kind: "value", hint: "Mức mực trong bình (%) — cần canh khi thấp." },
        { label: "Chiều cao vòi", tags: ["NozzleHeight"], kind: "value" },
        { label: "Chất lượng in", tags: ["PrintQuality"], kind: "value", hint: "Mã đánh giá chất lượng in của hệ thống." },
      ],
    },
  ],

  // ── Đóng thùng ───────────────────────────────────────────────────────
  CASE_PACKER: [
    {
      title: "Đóng thùng",
      metrics: [
        { label: "Bột màng còn", tags: ["FilmRemaining"], kind: "value", hint: "Chiều dài màng co còn lại (m)." },
        { label: "Định dạng thùng", tags: ["CaseFormat"], kind: "value", hint: "Mã định dạng thùng hiện tại." },
        { label: "Số chai/thùng", tags: ["BottlesPerCase", "CansPerCase"], kind: "value" },
        { label: "Số pallet", tags: ["PalletCount"], kind: "counter" },
      ],
    },
  ],

  // ── Khử pallet ───────────────────────────────────────────────────────
  CAN_DEPALLETIZER: [
    {
      title: "Khử pallet",
      metrics: [
        { label: "Tốc độ cấp lon", tags: ["CanFeedRate"], kind: "value" },
        { label: "Số lớp", tags: ["LayerCount"], kind: "value" },
        { label: "Số pallet", tags: ["PalletCount"], kind: "counter" },
      ],
    },
  ],

  // ── Hàn seam ─────────────────────────────────────────────────────────
  CAN_SEAMER: [
    {
      title: "Hàn seam",
      metrics: [
        { label: "Chất lượng seam", tags: ["SeamQuality"], kind: "value", hint: "Mã đánh giá chất lượng seam." },
        { label: "Áp suất seam", tags: ["SeamPressure"], kind: "value" },
        { label: "Mô-men seam", tags: ["SeamTorque"], kind: "value" },
        { label: "Chân hút", tags: ["CanVacuum"], kind: "value", hint: "Lực hút chân hút (kPa) — thấp = hụt lon." },
        { label: "Số lon lỗi seam", tags: ["SeamDefectCount"], kind: "counter" },
      ],
    },
  ],

  // ── Kiểm tra lon ─────────────────────────────────────────────────────
  CAN_INSPECTION: [
    {
      title: "Kiểm tra",
      metrics: [
        { label: "Kết quả", tags: ["InspectResult"], kind: "value", hint: "Mã kết quả kiểm tra gần nhất." },
        { label: "Tỷ lệ lỗi", tags: ["DefectRate"], kind: "value", hint: "Tỷ lệ lỗi phát hiện (%) — chỉ số chất lượng." },
        { label: "Lý do loại", tags: ["RejectReason"], kind: "value" },
        { label: "Số lượt kiểm tra", tags: ["InspectionCount"], kind: "counter" },
      ],
    },
  ],

  // ── CIP ──────────────────────────────────────────────────────────────
  CIP_SKID: [
    {
      title: "Hệ CIP",
      metrics: [
        {
          label: "Chu kỳ CIP",
          tags: ["TotalCounter"],
          kind: "counter",
          hint: "Số chu kỳ CIP đã chạy trong ca.",
        },
        { label: "pH", tags: ["pH"], kind: "value", hint: "pH dung dịch CIP — thuộc khoảng quy định là điều kiện vệ sinh." },
        { label: "Độ dẫn", tags: ["Conductivity"], kind: "value", hint: "Độ dẫn điện (µS/cm) — phản ánh nồng độ dung dịch." },
        { label: "Nhiệt độ bể", tags: ["TankTemp"], kind: "value" },
        { label: "Mực bể", tags: ["TankLevel"], kind: "value" },
        { label: "Lưu lượng", tags: ["FlowRate"], kind: "value" },
        { label: "Áp suất", tags: ["Pressure"], kind: "value" },
        { label: "Liều hóa chất", tags: ["ChemicalDose"], kind: "value", hint: "Lượng hóa chất định lượng (L)." },
        { label: "Đang hồi lưu", tags: ["CirculationOn"], kind: "flag" },
        { label: "Đang gia nhiệt", tags: ["HeatingOn"], kind: "flag" },
      ],
    },
  ],
};

/**
 * Profile đầy đủ cho một máy = Core + profile đặc trưng theo machineType.
 * Nhóm Core luôn ở cuối (thông số chung) — trừ CIP_SKID vốn không có
 * speed/yield theo nghĩa dòng chảy.
 */
export function profileFor(machineType: string): MetricGroup[] {
  const specific = METRIC_PROFILES[machineType] ?? [];
  const isCIP = machineType === "CIP_SKID";
  const counterTag = counterTagFor(machineType);
  const core: MetricGroup[] = isCIP
    ? []
    : [
        {
          title: "Thông số chung",
          metrics: [
            CORE_SPEED,
            {
              label: counterTagLabel(machineType),
              tags: [counterTag ?? "GoodCounter", "DefectCounter"],
              kind: "counter",
              hint: "Số lượng đạt / số lượng lỗi tích luỹ từ đầu ca.",
            },
            ...CORE_FLAGS,
          ],
        },
      ];
  return [...specific, ...core];
}
