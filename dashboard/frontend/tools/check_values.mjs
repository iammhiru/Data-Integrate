// Kiểm tra giá trị số hiển thị trên từng màn — sau khi đổi công thức OEE.
import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto("http://127.0.0.1:5173/mock.html", { waitUntil: "networkidle" });
await page.waitForTimeout(1000);

console.log("=== PLANT ===");
const kpiN = await page.locator(".kpi").count();
for (let i = 0; i < kpiN; i++) {
  const k = page.locator(".kpi").nth(i);
  const label = await k.locator(".kpi-label").first().innerText({ timeout: 3000 }).catch(() => "?");
  const value = await k.locator(".kpi-value").first().innerText({ timeout: 3000 }).catch(() => "?");
  const sub = await k.locator(".kpi-sub").first().innerText({ timeout: 3000 }).catch(() => "");
  console.log("  " + label.padEnd(20), value.padEnd(10), sub);
}

console.log("\n=== LINE CARD ===");
const cardN = await page.locator(".line-card").count();
for (let i = 0; i < cardN; i++) {
  const c = page.locator(".line-card").nth(i);
  const id = await c.locator(".line-id").first().innerText({ timeout: 3000 }).catch(() => "?");
  const oee = await c.locator(".line-oee-value").first().innerText({ timeout: 3000 }).catch(() => "-");
  const parts = await c.locator(".line-oee-parts").first().innerText({ timeout: 3000 }).catch(() => "-");
  console.log(`  ${id}  OEE=${oee}  ${parts.replace(/\n/g, " ")}`);
}

await page.getByRole("button", { name: "Dây chuyền" }).click();
await page.waitForTimeout(1200);
console.log("\n=== LINE_01 KPI ===");
const kpiCount = await page.locator(".lh-kpis .kpi").count();
for (let i = 0; i < kpiCount; i++) {
  const k = page.locator(".lh-kpis .kpi").nth(i);
  // ⚠ Dùng timeout ngắn + first(): locator không có phần tử sẽ chờ 30s mặc
  // định → treo script. Phải chặn thời gian chờ.
  const label = await k.locator(".kpi-label").first().innerText({ timeout: 3000 }).catch(() => "?");
  const value = await k.locator(".kpi-value").first().innerText({ timeout: 3000 }).catch(() => "?");
  const sub = await k.locator(".kpi-sub").first().innerText({ timeout: 3000 }).catch(() => "");
  console.log("  " + label.padEnd(20), value.padEnd(10), sub);
}
console.log("  " + (await page.locator(".lh-progress-foot").innerText({ timeout: 3000 })));

await browser.close();
// ⚠ Playwright đôi khi treo ở browser.close() → process không thoát, bị
//   hệ thống kill (exit code 4294967295) dù đã in đủ output.
//   Thoát cưỡng bức để script luôn kết thúc với exit code 0.
process.exit(0);
