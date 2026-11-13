// ============================================================================
//  PHASE 1 — MASTER DATA: frontend phải đọc được master data từ `master-api`
//  (`/master-api/api/lines`) và dùng nó cho OEE (Ideal Cycle Time) + hiển thị
//  work order.
//
//  Test mock HTTP (không cần backend thật) — cùng pattern với `live-ws.spec.ts`.
//  Chạy: npx playwright test tests/master-data.spec.ts
// ============================================================================

import { test, expect } from "@playwright/test";

const APP = "/";

/** Payload `/api/lines` của `master-api` (xem `services/master-api/app.py`). */
const LINES_PAYLOAD = {
  shift: {
    shiftId: "B",
    shiftName: "Ca B",
    startTime: "14:00",
    endTime: "22:00",
    plannedMinutes: 480,
    plannedBreakMinutes: 30,
  },
  lines: [
    {
      line_id: "LINE_01",
      display_name: "Chai PET — có ga",
      channel: "LINE_01",
      reference_process: "FILLING",
      sku: "PET-500-COKE",
      productName: "Nước có ga 500ml",
      idealCycleTimeSec: 0.4234,
      plannedQty: 57400,
      theoreticalQty: 63769,
      unit: "bottles",
      workOrder: {
        woId: "WO-2026-11-13-LINE_01-B",
        woCode: "WO-2611-1301-B",
        plannedQty: 57400,
        status: "RUNNING",
        actualStartTime: null,
      },
    },
    {
      line_id: "LINE_02",
      display_name: "Chai PET — không ga",
      channel: "LINE_02",
      reference_process: "FILLING",
      sku: "PET-500-WATER",
      productName: "Nước khoáng 500ml",
      idealCycleTimeSec: 0.5047,
      plannedQty: 52600,
      theoreticalQty: 53497,
      unit: "bottles",
      workOrder: {
        woId: "WO-2026-11-13-LINE_02-B",
        woCode: "WO-2611-1302-B",
        plannedQty: 52600,
        status: "RUNNING",
        actualStartTime: null,
      },
    },
    {
      line_id: "LINE_03",
      display_name: "Lon nhôm",
      channel: "LINE_03",
      reference_process: "FILLING",
      sku: "CAN-330-SUGAR",
      productName: "Nước giải khát lon 330ml",
      idealCycleTimeSec: 0.5877,
      plannedQty: 44000,
      theoreticalQty: 45942,
      unit: "cans",
      workOrder: {
        woId: "WO-2026-11-13-LINE_03-B",
        woCode: "WO-2611-1303-B",
        plannedQty: 44000,
        status: "RUNNING",
        actualStartTime: null,
      },
    },
  ],
};

test("master data: đọc SKU, kế hoạch và work order từ master-api", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.route("**/master-api/api/lines", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(LINES_PAYLOAD),
    }),
  );

  await page.goto(APP);
  await page.waitForTimeout(1200);

  // Mở màn Line View của LINE_01 → header phải hiện SKU + mã work order.
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();

  const sub = page.locator(".page-sub").first();
  await expect(sub).toContainText("PET-500-COKE");
  await expect(sub).toContainText("WO-2611-1301-B");

  expect(errors).toEqual([]);
});

test("master data: master-api lỗi → app vẫn chạy với giá trị fallback", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  // master-api sập → frontend phải fallback, không được crash.
  await page.route("**/master-api/api/lines", (route) =>
    route.fulfill({ status: 503, body: "unavailable" }),
  );

  await page.goto(APP);
  await page.waitForTimeout(1200);

  await expect(page.getByRole("heading", { name: "PLANT_01" })).toBeVisible();
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();

  // Fallback vẫn có SKU (giá trị hard-code cũ) → màn hình không trống.
  await expect(page.locator(".page-sub").first()).toContainText("PET-500-COKE");

  expect(errors).toEqual([]);
});
