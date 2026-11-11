import { test, expect } from "@playwright/test";

async function maskTelemetry(
  page: import("@playwright/test").Page,
  onlyStopped: boolean,
) {
  const mask = (snapshot: any) => ({
    ...snapshot,
    mode: "Kafka",
    tags: onlyStopped
      ? snapshot.tags
          .filter((t: any) => t.machineId === "M001" && t.tagName === "status")
          .map((t: any) => ({ ...t, value: "STOPPED" }))
      : [],
  });
  await page.route("**/api/snapshot", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: mask(await response.json()) });
  });
  await page.routeWebSocket("**/hubs/telemetry**", (ws) => {
    const server = ws.connectToServer();
    server.onMessage((message) => {
      const frames = message
        .toString()
        .split("\x1e")
        .filter(Boolean)
        .map((frame) => {
          const value = JSON.parse(frame);
          if (value.type === 1 && value.target === "Snapshot")
            value.arguments[0] = mask(value.arguments[0]);
          return JSON.stringify(value);
        });
      ws.send(frames.join("\x1e") + "\x1e");
    });
  });
}

test("missing telemetry is unknown, not zero running or stopped", async ({
  page,
}) => {
  await maskTelemetry(page, false);
  await page.goto("/");
  await expect(page.getByTestId("telemetry-coverage")).toContainText("0/100");
  for (const label of ["Đang vận hành", "Đang dừng"]) {
    const metric = page.locator(".metric").filter({ hasText: label });
    await expect(metric.locator(".metric-value")).toHaveText("—máy");
    await expect(metric).toContainText("Chưa nhận dữ liệu trạng thái");
  }
  await expect(page.locator(".machine-card .state-pill").first()).toHaveText(
    "Chưa rõ",
  );
});

test("known stopped machine allows real zero and reports remaining unknown", async ({
  page,
}) => {
  await maskTelemetry(page, true);
  await page.goto("/");
  await expect(page.getByTestId("telemetry-coverage")).toContainText("1/100");
  await expect(page.getByTestId("telemetry-coverage")).toContainText(
    "99 máy chưa rõ",
  );
  await expect(
    page
      .locator(".metric")
      .filter({ hasText: "Đang vận hành" })
      .locator(".metric-value"),
  ).toHaveText("0máy");
  await expect(
    page
      .locator(".metric")
      .filter({ hasText: "Đang dừng" })
      .locator(".metric-value"),
  ).toHaveText("1máy");
});
test("repository catalog, filters, detail and analysis", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByText("Đã kết nối", { exact: true })).toBeVisible();
  await expect(page.locator(".machine-card")).toHaveCount(100);
  await page.getByRole("button", { name: "Dây chuyền 1", exact: true }).click();
  await expect(page.locator(".machine-card")).toHaveCount(20);
  await page.getByLabel("Tìm máy").fill("M001");
  await expect(page.locator(".machine-card")).toHaveCount(1);
  await page.locator(".machine-card").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(16);
  await expect(page.locator("tbody")).toContainText("Có giá trị");
  await expect
    .poll(() => page.locator(".recharts-line-curve").count())
    .toBeGreaterThan(0);
  await page.getByLabel("Đóng chi tiết").click();
  await page.getByRole("button", { name: "Phân tích & OEE" }).click();
  await expect(
    page.getByRole("heading", { name: "Phân tích từ PostgreSQL" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Chất lượng dữ liệu" }).click();
  await expect(page.getByText("Sức khỏe nhánh dashboard")).toBeVisible();
  expect(errors).toEqual([]);
});
test("mobile and empty filter", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator(".machine-card")).toHaveCount(100);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByLabel("Tìm máy").fill("UNKNOWN_TEST");
  await expect(page.getByText("Không có máy phù hợp bộ lọc.")).toBeVisible();
});
test("two SignalR clients receive repository snapshot", async ({ baseURL }) => {
  const { HubConnectionBuilder } = await import("@microsoft/signalr");
  const clients = [0, 1].map(() =>
    new HubConnectionBuilder().withUrl(`${baseURL}/hubs/telemetry`).build(),
  );
  try {
    await Promise.all(
      clients.map(
        (c) =>
          new Promise<void>((resolve, reject) => {
            c.on("Snapshot", (s) => {
              if (s.tags.some((t: any) => t.machineId === "M001")) resolve();
            });
            c.start().catch(reject);
            setTimeout(() => reject(Error("snapshot timeout")), 10000).unref();
          }),
      ),
    );
  } finally {
    await Promise.all(clients.map((c) => c.stop()));
  }
});
test("reconnects after interrupted socket", async ({ page }) => {
  let socket: any;
  let count = 0;
  await page.routeWebSocket("**/hubs/telemetry**", (ws) => {
    socket = ws;
    count++;
    ws.connectToServer();
  });
  await page.goto("/");
  await expect(page.getByText("Đã kết nối", { exact: true })).toBeVisible();
  socket.close({ code: 1001, reason: "test" });
  await expect.poll(() => count).toBeGreaterThanOrEqual(2);
  await expect(page.getByText("Đã kết nối", { exact: true })).toBeVisible();
  await expect(page.locator(".machine-card")).toHaveCount(100);
});
test("desktop screenshot", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".machine-card")).toHaveCount(100);
  await page.screenshot({ path: "../artifacts/dashboard.png", fullPage: true });
});
