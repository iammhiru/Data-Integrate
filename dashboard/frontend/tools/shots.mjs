// Chụp ảnh từng màn hình để kiểm tra bố cục bằng mắt.
import { chromium } from "playwright";

const URL = "http://127.0.0.1:5173/mock.html";
const OUT = "e:/Work/SFSVcongty/Laird/Code/Data-Integrate/dashboard/frontend/shots";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

await page.screenshot({ path: `${OUT}/01-plant.png`, fullPage: true });

await page.getByRole("button", { name: "Dây chuyền" }).click();
await page.waitForTimeout(1200);
await page.screenshot({ path: `${OUT}/02-line.png`, fullPage: true });

await page.getByRole("button", { name: "Alarm & Sự kiện" }).click();
await page.waitForTimeout(1200);
await page.screenshot({ path: `${OUT}/03-alarms.png`, fullPage: true });

await browser.close();
process.exit(0);
console.log("đã chụp 3 màn hình vào", OUT);
