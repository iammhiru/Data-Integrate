// Kiểm tra ngữ nghĩa sơ đồ dòng chảy: thứ tự máy, vị trí mũi tên nối.
import { chromium } from "playwright";

const URL = "http://127.0.0.1:5173/mock.html";

const run = async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: "Mở LINE_01" }).click();
  await page.waitForTimeout(1500);

  const r = await page.evaluate(() => {
    const nodes = [...document.querySelectorAll(".flow-node")];
    const grid = document.querySelector(".flow-grid");
    const gr = grid.getBoundingClientRect();
    const cards = nodes.map((n) => {
      const b = n.getBoundingClientRect();
      return {
        code: n.querySelector(".mcard-code")?.textContent?.trim(),
        col: Math.round(b.x),
        row: Math.round(b.y),
        right: Math.round(b.right),
        cx: Math.round(b.x + b.width / 2),
        cy: Math.round(b.y + b.height / 2),
        w: Math.round(b.width),
        h: Math.round(b.height),
      };
    });
    const links = [...document.querySelectorAll(".flow-link")].map((e) => {
      const b = e.getBoundingClientRect();
      return { cls: e.className, x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2) };
    });
    return { cols: getComputedStyle(grid).gridTemplateColumns, cards, links, gridW: Math.round(gr.width) };
  });
  console.log(JSON.stringify(r, null, 1));

  console.log("\n--- SƠ ĐỒ (thứ tự theo hàng) ---");
  const rows = [];
  for (const c of r.cards) {
    let row = rows.find((x) => Math.abs(x.y - c.row) < 6);
    if (!row) { row = { y: c.row, items: [] }; rows.push(row); }
    row.items.push(c);
  }
  rows.sort((a, b) => a.y - b.y);
  for (const row of rows) {
    row.items.sort((a, b) => a.col - b.col);
    console.log(`y=${row.y}: ` + row.items.map((c) => `${c.code}[${c.col}..${c.right}]`).join("  |  "));
  }
  console.log("\nlinks:");
  r.links.forEach((l, i) => console.log(`  ${i}: ${l.cls.includes("h") ? "→" : "↴"} @ x=${l.x} y=${l.y}`));
  await browser.close();
};
run();