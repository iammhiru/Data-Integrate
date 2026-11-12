// Kiểm tra tính nhất quán số liệu giữa Plant Overview và Line View.
import { chromium } from "playwright";

const URL = "http://127.0.0.1:5173/mock.html";

const run = async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);

  const grab = async (label) => {
    const d = await page.evaluate(() => {
      const t = (s) => [...document.querySelectorAll(s)].map((e) => e.textContent.replace(/\s+/g, " ").trim());
      return {
        kpi: t(".kpi-row .kpi").map((s) => s.slice(0, 80)),
        lineCards: t(".line-card").map((s) => s.slice(0, 110)),
        panels: t(".panel").map((s) => s.slice(0, 90)),
        alarms: t(".rail-row, .event-row").slice(0, 12),
      };
    });
    console.log(`--- ${label} ---`);
    d.kpi.forEach((s) => console.log("  KPI : " + s));
    d.lineCards.forEach((s) => console.log("  CARD: " + s));
    d.panels.forEach((s) => console.log("  PANL: " + s));
    return d;
  };

  await grab("PLANT");
  await page.getByRole("button", { name: "Mở LINE_01" }).click();
  await page.waitForTimeout(1500);
  await grab("LINE_01");

  await page.getByRole("button", { name: "Mở LINE_02" }).click().catch(() => {});
  await page.goBack().catch(() => {});
  await browser.close();
};
run();
