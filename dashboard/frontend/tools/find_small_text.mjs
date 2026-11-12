// Liệt kê mọi phần tử có font-size < 11px trên từng màn hình.
// Dùng để tìm chữ quá nhỏ còn sót (WCAG / work.md §1.3).
import { chromium } from "playwright";

const URL = "http://127.0.0.1:5173/mock.html";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(URL, { waitUntil: "networkidle" });

const SMALL = 11;

async function report(label) {
  const small = await page.evaluate((min) => {
    const out = [];
    for (const el of document.querySelectorAll("*")) {
      if (!el.textContent?.trim()) continue;
      if (el.children.length) continue; // chỉ leaf
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < min) {
        out.push({
          fs,
          tag: el.tagName.toLowerCase(),
          cls: el.className?.toString().slice(0, 60),
          text: el.textContent.trim().slice(0, 40),
        });
      }
    }
    return out;
  }, SMALL);
  console.log(`\n### ${label} — ${small.length} phần tử < ${SMALL}px`);
  for (const s of small) console.log(`  ${s.fs}px  ${s.tag}.${s.cls}  "${s.text}"`);
}

await report("PLANT");

// sang trang dây chuyền
await page.getByRole("button", { name: /Dây chuyền/ }).click();
await page.waitForTimeout(700);
await report("LINE");

// sang alarm
await page.getByRole("button", { name: /Alarm/ }).click();
await page.waitForTimeout(700);
await report("ALARMS");

await browser.close();
process.exit(0);
