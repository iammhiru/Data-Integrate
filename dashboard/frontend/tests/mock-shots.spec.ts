// Chụp ảnh các màn MOCK để review thị giác.
// Chạy: npx playwright test tests/mock-shots.spec.ts
import { test } from "@playwright/test";

const OUT = "../artifacts/mock";

test("chụp ảnh 4 màn", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/mock.html");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}-01-plant.png`, fullPage: true });

  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}-02-line.png`, fullPage: true });

  await page.locator(".flow-node .mcard").nth(1).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}-03-machine.png` });
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: /alarm đang mở/i }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}-04-alarms.png`, fullPage: true });
});
