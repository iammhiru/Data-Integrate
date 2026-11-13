// Kiểm chứng NGỮ NGHĨA sơ đồ dòng chảy:
//  - mũi tên nằm trong KHE giữa 2 card liền kề (không trôi lơ lửng, không dính mép)
//  - không mũi tên nào nằm ngoài lưới
//  - mọi card đều nằm trong khung nhìn (không tràn ngang)
import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto("http://127.0.0.1:5173/mock.html", { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Dây chuyền" }).click();
await page.waitForTimeout(1500);

const r = await page.evaluate(() => {
  const nodes = [...document.querySelectorAll(".flow-node")].map((n) => {
    const b = n.getBoundingClientRect();
    return { l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width };
  });
  const links = [...document.querySelectorAll(".flow-link")].map((l) => {
    const b = l.getBoundingClientRect();
    return {
      cx: b.left + b.width / 2,
      cy: b.top + b.height / 2,
      cls: l.className,
    };
  });
  const wrap = document.querySelector(".flow-grid-wrap").getBoundingClientRect();
  return { nodes, links, wrap: { l: wrap.left, r: wrap.right, t: wrap.top, b: wrap.bottom } };
});

console.log(`Card: ${r.nodes.length} · Mũi tên: ${r.links.length}\n`);

const problems = [];
for (let i = 0; i < r.links.length; i++) {
  const a = r.nodes[i];
  const b = r.nodes[i + 1];
  const l = r.links[i];
  const sameRow = Math.abs(a.t - b.t) < 4;

  if (sameRow) {
    const lo = Math.min(a.r, b.l);
    const hi = Math.max(a.r, b.l);
    const inGap = l.cx >= lo - 2 && l.cx <= hi + 2;
    const d = Math.min(Math.abs(l.cx - a.r), Math.abs(l.cx - b.l));
    console.log(
      `#${i + 1} ngang  arrow@${Math.round(l.cx)}  gap[${Math.round(lo)}..${Math.round(hi)}]  ` +
        `${inGap ? "OK" : "!!! NGOAI KHE"}  cach mep ${Math.round(d)}px`,
    );
    if (!inGap) problems.push(`mũi tên #${i + 1} nằm ngoài khe ngang`);
    if (Math.abs(l.cx - (lo + hi) / 2) > 6)
      problems.push(`mũi tên #${i + 1} lệch giữa khe ${Math.round(Math.abs(l.cx - (lo + hi) / 2))}px`);
  } else {
    const inV = l.cy >= a.b - 4 && l.cy <= b.t + 4;
    const sameCol = Math.abs(l.cx - (a.l + a.r) / 2) < 12;
    console.log(
      `#${i + 1} re xuong  arrow@(${Math.round(l.cx)},${Math.round(l.cy)})  ` +
        `khe doc[${Math.round(a.b)}..${Math.round(b.t)}]  ` +
        `${inV ? "OK" : "!!! NGOAI KHE DOC"}  ${sameCol ? "trung cot" : "!!! LECH COT"}`,
    );
    if (!inV) problems.push(`mũi tên #${i + 1} nằm ngoài khe dọc`);
    if (!sameCol) problems.push(`mũi tên #${i + 1} lệch cột so với card cuối hàng`);
  }
}

for (const [i, l] of r.links.entries()) {
  if (l.cx < r.wrap.l - 1 || l.cx > r.wrap.r + 1) {
    problems.push(`mũi tên #${i + 1} tràn ra ngoài lưới (${Math.round(l.cx)})`);
  }
}

for (const [i, n] of r.nodes.entries()) {
  if (n.r > r.wrap.r + 1) problems.push(`card #${i + 1} tràn khung`);
}

console.log(
  problems.length
    ? `\n❌ ${problems.length} VẤN ĐỀ:\n  ` + problems.join("\n  ")
    : "\n✅ Tất cả mũi tên nối liền đúng card",
);
await browser.close();
process.exit(0);
