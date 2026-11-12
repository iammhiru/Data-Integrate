// Render mes_dashboard_2x2.html ở đúng kích thước ảnh gốc (1536×1024)
// rồi so sánh vị trí khung với ảnh UI2x2.png.
import { chromium } from "playwright";
import path from "path";

const HTML = "file:///" + path.resolve("..", "..", "docs", "mes_dashboard_2x2.html").replace(/\\/g, "/");

const run = async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1536, height: 1024 } });
  await page.goto(HTML, { waitUntil: "load" });
  await page.waitForTimeout(800);

  const info = await page.evaluate(() => {
    const q = (s) => [...document.querySelectorAll(s)];
    const box = (el) => { const b = el.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }; };
    return {
      scrollH: document.documentElement.scrollHeight,
      frames: q(".frame").map((e) => box(e)),
      bottom: q(".bottom .bp").map((e) => box(e)),
      top: box(document.querySelector(".top")),
      bodyBg: getComputedStyle(document.body).backgroundColor,
    };
  });
  console.log(JSON.stringify(info, null, 1));
  await page.screenshot({ path: "tools/_2x2_render.png", fullPage: true });
  await browser.close();
};
run();
