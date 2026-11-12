// ============================================================================
//  Seed sự kiện mô phỏng (alarm / chuyển trạng thái) — để panel "Sự kiện"
//  và "Alarm đang mở" có nội dung khi review concept.
//  Khi tích hợp thật, sự kiện đến từ batch downtime_event + alarm stream.
// ============================================================================

import type { MockEvent } from "./mock-simulator";

type Seed = {
  machineId: string;
  equipmentCode: string;
  agoMin: number;
  kind: "state" | "alarm" | "info";
  text: string;
  severity: "info" | "warn" | "crit";
};

const SEEDS: Seed[] = [
  {
    machineId: "L01_CODER_01",
    equipmentCode: "CODE-L01-01",
    agoMin: 23,
    kind: "alarm",
    text: "A-417 — Mực in không đủ áp, nghiêng mực",
    severity: "crit",
  },
  {
    machineId: "L01_CODER_01",
    equipmentCode: "CODE-L01-01",
    agoMin: 24,
    kind: "state",
    text: "RUNNING → FAULTED",
    severity: "crit",
  },
  {
    machineId: "L01_RINSER_01",
    equipmentCode: "RINSE-L01-01",
    agoMin: 31,
    kind: "state",
    text: "RUNNING → STOPPED (thiếu nước rửa)",
    severity: "warn",
  },
  {
    machineId: "L02_AIRCONV_01",
    equipmentCode: "ACONV-L02-01",
    agoMin: 46,
    kind: "state",
    text: "RUNNING → MAINTENANCE",
    severity: "info",
  },
  {
    machineId: "L01_FILLER_01",
    equipmentCode: "FILL-L01-01",
    agoMin: 58,
    kind: "state",
    text: "STOPPED → RUNNING",
    severity: "info",
  },
  {
    machineId: "L03_CANFILLER_01",
    equipmentCode: "FILL-L03-01",
    agoMin: 72,
    kind: "state",
    text: "OFF → STARTING",
    severity: "info",
  },
  {
    machineId: "L01_BLOWER_01",
    equipmentCode: "BLOW-L01-01",
    agoMin: 95,
    kind: "info",
    text: "Đổi khuôn — tạo dừng kế hoạch 6 phút",
    severity: "info",
  },
  {
    machineId: "L02_LABELER_01",
    equipmentCode: "LABL-L02-01",
    agoMin: 112,
    kind: "info",
    text: "Hết cuộn nhãn — chất lượng nguồn = Bad",
    severity: "warn",
  },
];

export function seedEvents(): MockEvent[] {
  const now = Date.now();
  return SEEDS.map((s) => ({
    at: new Date(now - s.agoMin * 60_000).toISOString(),
    machineId: s.machineId,
    equipmentCode: s.equipmentCode,
    kind: s.kind,
    text: s.text,
    severity: s.severity,
  }));
}
