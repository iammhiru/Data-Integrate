// Đo đạc layout mock hiện tại ở 1920×1080 cho cả 4 màn.
// Dùng để so sánh định lượng với ảnh tham khảo (vì phiên này không đọc được ảnh).
import { chromium } from "playwright";

const URL = "http://127.0.0.1:5173/mock.html";
const W = 1920, H = 1080;

const probe = () => {
  const out = { vw: innerWidth, vh: innerHeight, scrollH: document.documentElement.scrollHeight };
  const q = (s) => [...document.querySelectorAll(s)];
  const box = (el) => {
    const b = el.getBoundingClientRect();
    return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
  };
  // flow grid
  const grid = document.querySelector(".flow-grid");
  if (grid) {
    const nodes = q(".flow-node");
    const cols = getComputedStyle(grid).gridTemplateColumns.split(" ").length;
    const rows = [...new Set(nodes.map((n) => Math.round(n.getBoundingClientRect().top)))].length;
    out.flow = {
      cols, rows, n: nodes.length,
      gridW: Math.round(grid.getBoundingClientRect().width),
      nodeW: nodes[0] ? Math.round(nodes[0].getBoundingClientRect().width) : 0,
      links: q(".flow-link").length,
      // vị trí mũi tên dọc (rẽ hàng) so với card kế tiếp
      vLinks: q(".flow-link-v").map((e) => {
        const b = e.getBoundingClientRect();
        return { x: Math.round(b.x + b.width / 2), y: Math.round(b.y) };
      }),
      lastRowIdx: nodes.map((n, i) => [i, Math.round(n.getBoundingClientRect().top)]).reduce((acc, [i, t]) => {
        if (!acc.length || t > acc[acc.length - 1][1]) acc.push([i, t]);
        return acc;
      }, []),
    };
  }
  // kpi row
  out.kpis = q(".kpi-row .kpi").map((e) => {
    const lbl = e.querySelector(".kpi-label")?.textContent?.trim();
    const val = e.querySelector(".kpi-value")?.textContent?.trim();
    const sub = e.querySelector(".kpi-sub")?.textContent?.trim();
    return { lbl, val, sub, ...box(e), accent: e.classList.contains("kpi-accent") };
  });
  // line cards
  out.lineCards = q(".line-card").map((e) => ({
    id: e.querySelector(".line-id")?.textContent?.trim(),
    ...box(e),
  }));
  // text nodes & font sizes
  const leaves = [];
  const walk = (el, d) => {
    if (d > 8) return;
    const kids = [...el.children].filter((c) => getComputedStyle(c).display !== "none");
    if (!kids.length && el.textContent.trim()) {
      const cs = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      if (b.width > 0) leaves.push({ t: el.textContent.trim().slice(0, 40), fs: cs.fontSize, x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width) });
      return;
    }
    kids.forEach((k) => walk(k, d + 1));
  };
  walk(document.querySelector(".content") || document.body, 0);
  out.leaves = leaves;
  out.fontSizes = {};
  for (const l of leaves) out.fontSizes[l.fs] = (out.fontSizes[l.fs] || 0) + 1;
  // panels
  out.panels = q(".panel, .line-header-panel, .rail-panel, .section").map((e) => ({ cls: e.className, ...box(e) }));
  return out;
};

const run = async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const log = {};

  await page.goto(URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  log.plant = await page.evaluate(probe);
  await page.screenshot({ path: "tools/_shot_plant.png", fullPage: true });

  await page.getByRole("button", { name: "Mở LINE_01" }).click();
  await page.waitForTimeout(1500);
  log.line = await page.evaluate(probe);
  await page.screenshot({ path: "tools/_shot_line.png", fullPage: true });

  // đo tràn ngang
  log.overflow = await page.evaluate(() => {
    const bad = [];
    document.querySelectorAll("*").forEach((el) => {
      if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflowX !== "visible") {
        bad.push({ cls: el.className?.toString().slice(0, 60), sw: el.scrollWidth, cw: el.clientWidth });
      }
    });
    return { docOverflow: document.documentElement.scrollWidth - innerWidth, bad: bad.slice(0, 15) };
  });

  await browser.close();
  console.log(JSON.stringify(log, null, 1));
};
run();
