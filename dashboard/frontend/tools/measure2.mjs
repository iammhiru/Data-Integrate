// Tóm tắt đo đạc mock — dạng bảng gọn để so sánh với ảnh tham khảo.
import { chromium } from "playwright";

const URL = "http://127.0.0.1:5173/mock.html";
const W = Number(process.argv[2] || 1920);
const H = Number(process.argv[3] || 1080);

const probe = () => {
  const q = (s) => [...document.querySelectorAll(s)];
  const box = (el) => { const b = el.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }; };
  const out = { vw: innerWidth, vh: innerHeight, scrollH: document.documentElement.scrollHeight };
  out.docOverflow = document.documentElement.scrollWidth - innerWidth;
  out.badScroll = q("*").filter((el) => el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflowX !== "visible")
    .map((el) => `${el.tagName}.${(el.className || "").toString().split(" ")[0]} sw=${el.scrollWidth} cw=${el.clientWidth}`);
  out.fontSizes = {};
  const leaves = [];
  const walk = (el, d) => {
    if (d > 8) return;
    const kids = [...el.children].filter((c) => getComputedStyle(c).display !== "none");
    if (!kids.length && el.textContent.trim()) {
      const cs = getComputedStyle(el); const b = el.getBoundingClientRect();
      if (b.width > 0) { leaves.push({ t: el.textContent.trim().slice(0, 30), fs: parseFloat(cs.fontSize) }); out.fontSizes[cs.fontSize] = (out.fontSizes[cs.fontSize] || 0) + 1; }
      return;
    }
    kids.forEach((k) => walk(k, d + 1));
  };
  walk(document.querySelector(".content") || document.body, 0);
  out.smallText = leaves.filter((l) => l.fs < 11).length;
  out.totalText = leaves.length;
  const grid = document.querySelector(".flow-grid");
  if (grid) {
    const nodes = q(".flow-node");
    const tops = nodes.map((n) => Math.round(n.getBoundingClientRect().top));
    out.flow = {
      cols: getComputedStyle(grid).gridTemplateColumns.split(" ").length,
      rows: new Set(tops).size,
      n: nodes.length,
      gridW: Math.round(grid.getBoundingClientRect().width),
      cardW: Math.round(nodes[0]?.getBoundingClientRect().width || 0),
      cardH: Math.round(nodes[0]?.getBoundingClientRect().height || 0),
      links: q(".flow-link").length,
      hLinks: q(".flow-link-h").length,
      vLinks: q(".flow-link-v").length,
      gridH: Math.round(grid.getBoundingClientRect().height),
    };
  }
  out.kpi = q(".kpi-row .kpi").map((e) => `${e.querySelector(".kpi-label")?.textContent?.trim()}=${e.querySelector(".kpi-value")?.textContent?.trim()} [${box(e).w}x${box(e).h}]`);
  out.cards = q(".line-card").map((e) => `${e.querySelector(".line-id")?.textContent?.trim()} ${box(e).w}x${box(e).h} @${box(e).x},${box(e).y}`);
  out.panels = q(".panel, .rail-panel, .line-header-panel").map((e) => `${(e.className || "").toString().split(" ").slice(0, 2).join(".")} ${box(e).w}x${box(e).h} @${box(e).x},${box(e).y}`);
  return out;
};

const run = async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  console.log("### PLANT @" + W + "x" + H);
  console.log(JSON.stringify(await page.evaluate(probe), null, 1));
  await page.getByRole("button", { name: "Mở LINE_01" }).click();
  await page.waitForTimeout(1200);
  console.log("### LINE");
  console.log(JSON.stringify(await page.evaluate(probe), null, 1));
  await browser.close();
};
run();
