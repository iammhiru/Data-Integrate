// ============================================================================
//  Nguồn LIVE — kiểm thử adapter WebSocket tới `state-api` (FastAPI).
//
//  Dùng `page.routeWebSocket` để MOCK hoàn toàn server giả đúng giao thức
//  của `services/state-api/app.py`:
//    · snapshot  → gửi ngay khi client kết nối
//    · patch     → gửi khi cần (giả lập đổi trạng thái)
//    · heartbeat → giữ kết nối sống
//
//  ⚠ KHÔNG dùng `connectToServer()` — không có backend thật chạy ở
//    localhost:8000 trong lúc test, nên phải mock 100% (page ↔ route).
//
//  Chạy: npx playwright test tests/live-ws.spec.ts
// ============================================================================

import { test, expect } from "@playwright/test";
import { MACHINES } from "../src/mock/catalog.gen";

const APP = "/?source=live";

/** Tag `MachineState` → tên trạng thái (khớp `state_name` của Spark job). */
const STATE_NAME: Record<number, string> = {
  0: "OFF",
  1: "STARTING",
  2: "RUNNING",
  3: "STOPPED",
  4: "FAULTED",
  5: "MAINTENANCE",
};

/**
 * Dựng payload `snapshot` giống hệt `state-api`:
 *   mỗi máy có meta + summary + tags (value/valueType/statusCode/eventTime…).
 */
function buildSnapshot(opts: { state?: number; counters?: number } = {}) {
  const state = opts.state ?? 2;
  const counters = opts.counters ?? 1000;
  const now = new Date().toISOString();

  const machines = MACHINES.map((def, i) => {
    const tags: Record<string, unknown> = {};
    for (const t of def.tags) {
      let value: number | string | boolean | null = null;
      if (t.name === "MachineState") value = state;
      else if (t.name === "MachineMode") value = 2;
      else if (t.name === "EmergencyStop") value = false;
      else if (t.name === "AlarmCode") value = 0;
      else if (t.name === "Starved" || t.name === "Blocked") value = false;
      else if (t.name === "TotalCounter") value = counters + i;
      else if (t.name === "GoodCounter") value = counters - 10 + i;
      else if (t.name === "DefectCounter") value = 10;
      else if (t.name === "CurrentSpeed") value = 60;
      else if (t.name === "DesignSpeed") value = 60;
      else if (t.dataType === "Boolean") value = false;
      else if (t.dataType === "Int" || t.dataType === "Float") value = 42;
      else value = "OK";

      tags[t.name] = {
        value,
        valueType:
          t.dataType === "Boolean"
            ? "Boolean"
            : t.dataType === "String"
              ? "String"
              : "Int32",
        unit: t.unit,
        statusCode: "Good",
        isGood: true,
        tagCode: t.tagCode,
        tagType: t.tagType,
        eventTime: now,
        emittedAt: now,
        ...(t.name === "MachineState" ? { stateName: STATE_NAME[state] } : {}),
      };
    }

    return {
      machineId: def.machineId,
      plantId: "PLANT_01",
      lineId: def.lineId,
      processId: def.processId,
      machineType: def.machineType,
      equipmentCode: def.equipmentCode,
      sourceSystem: "middleware",
      state: STATE_NAME[state],
      stateSince: now,
      summary: { MachineState: state, AlarmCode: 0 },
      tagCount: def.tags.length,
      lastEventTime: now,
      ageSeconds: 0.2,
      stale: false,
      tags,
    };
  });

  return { type: "snapshot", ready: true, serverTime: now, machines };
}

/** Dựng payload `patch` — chỉ chứa tag vừa đổi. */
function buildPatch(
  machineId: string,
  tagName: string,
  value: number,
  stateName?: string,
) {
  const now = new Date().toISOString();
  return {
    type: "patch",
    serverTime: now,
    machines: [
      {
        machineId,
        state: stateName,
        lastEventTime: now,
        ageSeconds: 0.1,
        stale: false,
        tagCount: 5,
        tags: {
          [tagName]: {
            value,
            valueType: "Int32",
            statusCode: "Good",
            isGood: true,
            eventTime: now,
            emittedAt: now,
            ...(stateName ? { stateName } : {}),
          },
        },
      },
    ],
  };
}

test("LIVE: kết nối state-api, hiện badge LIVE và dựng đủ 26 máy", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.routeWebSocket("**/state-api/ws/machines", (ws) => {
    // Server giả: gửi snapshot ngay khi client mở kết nối.
    ws.send(JSON.stringify(buildSnapshot()));
    // Client gửi `{"action":"ping"}` → trả heartbeat (giữ kết nối sống).
    ws.onMessage((msg) => {
      const text = msg.toString();
      if (text.includes("ping")) {
        ws.send(
          JSON.stringify({ type: "heartbeat", serverTime: new Date().toISOString(), ready: true }),
        );
      }
    });
  });

  await page.goto(APP);
  await expect(page.locator(".mock-badge.live")).toBeVisible();
  await expect(page.locator(".mock-badge.live")).toHaveText("LIVE");

  // Nút kết nối phải phản ánh trạng thái thật.
  await expect(page.locator(".conn")).toHaveText("Đang kết nối");

  await expect(page.getByRole("heading", { name: "PLANT_01" })).toBeVisible();
  await page.waitForTimeout(1000);

  // 26 máy đều có dữ liệu → không máy nào ở trạng thái "Mất dữ liệu".
  const noData = await page
    .locator(".status-panel .status-card")
    .filter({ hasText: "Mất dữ liệu" })
    .count();
  expect(noData).toBe(0);

  // OEE phải hợp lệ: Performance ≤ 100% (cùng cửa sổ quan sát cho bộ đếm
  // và Run Time — xem `telemetry-source.ts`).
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();
  const perf = await page
    .locator(".lh-kpis .kpi")
    .filter({ hasText: "Performance" })
    .locator(".kpi-value")
    .innerText();
  expect(Number(perf.replace("%", ""))).toBeLessThanOrEqual(100);

  expect(errors).toEqual([]);
});

test("LIVE: patch đổi trạng thái máy → ghi nhận sự kiện alarm", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.routeWebSocket("**/state-api/ws/machines", (ws) => {
    ws.send(JSON.stringify(buildSnapshot({ state: 2 })));

    const target = MACHINES[0].machineId;
    // Máy chuyển RUNNING → FAULTED, rồi bật alarm.
    ws.send(JSON.stringify(buildPatch(target, "MachineState", 4, "FAULTED")));
    ws.send(JSON.stringify(buildPatch(target, "AlarmCode", 1001)));

    ws.onMessage((msg) => {
      if (msg.toString().includes("ping")) {
        ws.send(
          JSON.stringify({ type: "heartbeat", serverTime: new Date().toISOString(), ready: true }),
        );
      }
    });
  });

  await page.goto(APP);
  await expect(page.locator(".mock-badge.live")).toBeVisible();
  await expect(page.locator(".conn")).toHaveText("Đang kết nối");
  await page.waitForTimeout(1000);

  // Sự kiện alarm phải được ghi nhận (nguồn sự kiện DUY NHẤT của chế độ thật).
  await page.getByRole("button", { name: /alarm đang mở/i }).click();
  await expect(page.getByRole("heading", { name: "Giám sát sự kiện" })).toBeVisible();
  await expect(page.locator(".ev-kind").first()).toBeVisible();

  expect(errors).toEqual([]);
});

test("LIVE: mất kết nối → adapter retry, không crash", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.routeWebSocket("**/state-api/ws/machines", (ws) => {
    ws.send(JSON.stringify(buildSnapshot()));
    // Đóng ngay → adapter phải retry, không được văng exception.
    setTimeout(() => ws.close({ code: 1006, reason: "test" }), 300);
  });

  await page.goto(APP);
  await expect(page.locator(".mock-badge.live")).toBeVisible();
  await page.waitForTimeout(1500);
  await expect(page.getByRole("heading", { name: "PLANT_01" })).toBeVisible();
  expect(errors).toEqual([]);
});
