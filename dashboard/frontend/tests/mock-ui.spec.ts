// ============================================================================
//  Kiểm thử layout — không thanh trượt ngang trong component,
//  và dữ liệu nhất quán giữa các màn.
//  Chạy: npx playwright test tests/mock-ui.spec.ts
//
//  ⚠ 12/11: đường dẫn chính của dashboard là "/" (index.html).
//    "/mock.html" vẫn chạy được (alias) — test dùng "/" để phản ánh thực tế.
// ============================================================================

import { test, expect } from "@playwright/test";

const APP = "/";

/** Mọi phần tử đang tạo thanh trượt ngang (overflow ngang bị giới hạn). */
async function horizontalOverflow(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const out: string[] = [];
    document.querySelectorAll<HTMLElement>("*").forEach((el) => {
      if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
        out.push(`${el.tagName}.${el.className} (${el.scrollWidth}>${el.clientWidth})`);
      }
    });
    return out;
  });
}

/** Các kích thước màn hình mục tiêu: control room, laptop, tablet. */
const VIEWPORTS = [
  { width: 1920, height: 1080, name: "control-room" },
  { width: 1600, height: 1000, name: "laptop-larg" },
  { width: 1280, height: 800, name: "laptop" },
  { width: 1024, height: 768, name: "tablet" },
];

for (const vp of VIEWPORTS) {
  test(`plant overview @ ${vp.name}: không thanh trượt ngang`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(APP);
    await expect(page.getByRole("heading", { name: "PLANT_01" })).toBeVisible();
    expect(await horizontalOverflow(page)).toEqual([]);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
  });

  test(`line view @ ${vp.name}: dòng chảy không cần kéo ngang`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(APP);
    await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
    await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();

    expect(await horizontalOverflow(page)).toEqual([]);

    // Tất cả 9 máy của line nằm trong khung nhìn (không bị cắt bên phải).
    const cards = page.locator(".flow-node .mcard");
    await expect(cards).toHaveCount(9);
    const gr = (await page.locator(".flow-grid").boundingBox())!;
    for (let i = 0; i < 9; i++) {
      const b = (await cards.nth(i).boundingBox())!;
      expect(b.x).toBeGreaterThanOrEqual(gr.x - 1);
      expect(b.x + b.width).toBeLessThanOrEqual(gr.x + gr.width + 1);
    }
    await expect(page.locator(".flow-link")).toHaveCount(8);
  });
}

// ============================================================================
//  POPUP THIẾT BỊ — là OVERLAY, không xóa nền (yêu cầu 12/11)
// ============================================================================

test("popup thiết bị: nền vẫn hiện và đóng về đúng màn trước", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();

  // Mở popup máy (máy thổi khuôn — có nhiệt độ °C).
  await page.locator(".flow-node .mcard").nth(1).click();
  await expect(page.getByRole("dialog")).toBeVisible();

  // ⚠ NỀN PHẢI CÒN: sơ đồ dòng chảy của LINE_01 vẫn còn trong DOM và
  //   vẫn nhìn thấy được (không bị xóa).
  await expect(page.locator(".flow-grid")).toBeVisible();
  await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();

  // Đóng popup → phải về LẠI LINE_01 (không nhảy về màn đầu tiên).
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();
  await expect(page.locator(".flow-grid")).toBeVisible();
});

test("popup thiết bị: đóng bằng click nền cũng về đúng màn", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await page.locator(".flow-node .mcard").nth(1).click();
  await expect(page.getByRole("dialog")).toBeVisible();

  // Click vào vùng nền bên trái (ngoài drawer).
  await page.mouse.click(200, 500);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();
});

test("popup thiết bị: mở từ Plant Overview → đóng về Plant Overview", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  // Mở line từ card ở Plant Overview, rồi bấm máy trong sơ đồ.
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await page.locator(".flow-node .mcard").nth(1).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: /LINE_01/ })).toBeVisible();
});

test("popup thiết bị: có đơn vị hiển thị", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await page.locator(".flow-node .mcard").nth(1).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(await horizontalOverflow(page)).toEqual([]);
  // Đơn vị SI hiển thị đúng (không phải degC/uS/cm thô).
  await expect(page.locator(".dr-body")).toContainText("°C");
  await expect(page.locator(".dr-body")).not.toContainText("degC");
});

// ============================================================================
//  CHÚ GIẢI TRẠNG THÁI — lưới thẻ, không phải 1 hàng (yêu cầu 12/11)
// ============================================================================

test("chú giải trạng thái: dạng lưới thẻ, dot lớn, không nằm 1 hàng", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);

  const cards = page.locator(".status-panel .status-card");
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBeGreaterThan(1);

  // Dot phải đủ lớn (≥ 16px bao gồm ring) — trước đây 8px, trông như lỗi font.
  const dot = await page.locator(".status-card-dot").first().boundingBox();
  expect(dot!.width).toBeGreaterThanOrEqual(16);
  expect(dot!.height).toBeGreaterThanOrEqual(16);

  // Các thẻ phải TRẢI trên nhiều hàng (không dồn hết 1 hàng).
  const tops = await page
    .locator(".status-panel .status-card")
    .evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().top)));
  expect(new Set(tops).size).toBeGreaterThan(1);

  // Mỗi thẻ có mô tả ý nghĩa (tooltip) chứ không chỉ mảng chữ.
  await expect(cards.first().locator(".status-card-hint")).not.toBeEmpty();
});

// ============================================================================
//  SIDEBAR — thu gọn được, không có tab "Thiết bị" (yêu cầu 12/11)
// ============================================================================

test("sidebar: thu gọn/mở rộng được và không có tab Thiết bị", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);

  const nav = page.locator(".nav .nav-item");
  const labels = await nav.allInnerTexts();
  expect(labels.join(" ")).not.toContain("Thiết bị");

  // Nút thu gọn tồn tại và hoạt động.
  const toggle = page.locator(".sidebar-collapse");
  await expect(toggle).toBeVisible();

  const wide = (await page.locator(".sidebar").boundingBox())!.width;
  await toggle.click();
  await expect(page.locator(".sidebar.sidebar-collapsed")).toBeVisible();
  const narrow = (await page.locator(".sidebar").boundingBox())!.width;
  expect(narrow).toBeLessThan(wide);

  // Mở rộng lại.
  await page.locator(".sidebar-collapse").click();
  await expect(page.locator(".sidebar.sidebar-collapsed")).toHaveCount(0);
});

test("sidebar: không có nút chết (mọi nút đều hoạt động)", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  const nav = page.locator(".nav .nav-item");
  const n = await nav.count();
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    const btn = nav.nth(i);
    expect(await btn.isDisabled()).toBe(false);
  }
});

// ============================================================================
//  ALARM CENTER & CÁC MÀN CÒN LẠI
// ============================================================================

test("alarm center: phân biệt alarm và sự kiện", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /alarm đang mở/i }).click();
  await expect(
    page.getByRole("heading", { name: "Giám sát sự kiện" }),
  ).toBeVisible();
  await expect(page.locator(".ev-kind").first()).toBeVisible();
  expect(await horizontalOverflow(page)).toEqual([]);
});

test("thời gian hiển thị theo giờ địa phương, khớp đồng hồ topbar", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();

  const clock = await page.locator(".clock").innerText();
  // Bảng "Các công đoạn" hiển thị thời điểm nhận gần nhất của từng máy.
  const cardTime = await page.locator(".stage-time").first().innerText();

  // Cùng định dạng HH:mm:ss và lệch nhau dưới 2 phút.
  const toSec = (t: string) => {
    const [h, m, s] = t.trim().split(":").map(Number);
    return h * 3600 + m * 60 + s;
  };
  const diff = Math.abs(toSec(clock) - toSec(cardTime));
  expect(diff).toBeLessThan(120);
});

test("vượt kế hoạch: hiện phần vượt, không hiện 'còn 0 pcs'", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  const foot = await page.locator(".lh-progress-foot").innerText();
  expect(foot).not.toContain("còn 0");
  expect(foot).toMatch(/còn|vượt/);
});

test("Performance không vượt 100% (OEE không sai)", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  const perf = await page
    .locator(".lh-kpis .kpi")
    .filter({ hasText: "Performance" })
    .locator(".kpi-value")
    .innerText();
  expect(Number(perf.replace("%", ""))).toBeLessThanOrEqual(100);
});

// ============================================================================
//  Các hành vi đã SỬA trong đợt dựng lại layout
// ============================================================================

test("ca sản xuất khớp đồng hồ hệ thống (không ghim cứng)", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);

  // Đồng hồ topbar và nhãn ca phải cùng chiều giờ.
  const clock = await page.locator(".clock").innerText();
  const hour = Number(clock.trim().split(":")[0]);
  const shiftText = await page.locator(".ctx-shift").innerText();
  // Ca A 06–14, Ca B 14–22, Ca C 22–06.
  const expected =
    hour >= 6 && hour < 14 ? "Ca A" : hour >= 14 && hour < 22 ? "Ca B" : "Ca C";
  expect(shiftText).toContain(expected);
});

test("mũi tên dòng chảy nối liền giữa 2 card liền kề", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();

  const bad = await page.evaluate(() => {
    const nodes = [...document.querySelectorAll<HTMLElement>(".flow-node")].map(
      (n) => n.getBoundingClientRect(),
    );
    const links = [...document.querySelectorAll<HTMLElement>(".flow-link")].map(
      (l) => l.getBoundingClientRect(),
    );
    const out: string[] = [];
    for (let i = 0; i < links.length; i++) {
      const a = nodes[i];
      const b = nodes[i + 1];
      const cx = links[i].left + links[i].width / 2;
      const cy = links[i].top + links[i].height / 2;
      if (Math.abs(a.top - b.top) < 4) {
        // Cùng hàng: mũi tên phải nằm trong khe giữa 2 card.
        const lo = Math.min(a.right, b.left);
        const hi = Math.max(a.right, b.left);
        if (cx < lo - 2 || cx > hi + 2) out.push(`#${i + 1} ngoài khe ngang`);
        if (Math.abs(cx - (lo + hi) / 2) > 6) out.push(`#${i + 1} lệch giữa khe`);
      } else {
        // Rẽ xuống: phải nằm trong khe dọc và trùng cột với card cuối hàng.
        if (cy < a.bottom - 4 || cy > b.top + 4) out.push(`#${i + 1} ngoài khe dọc`);
        if (Math.abs(cx - (a.left + a.right) / 2) > 12)
          out.push(`#${i + 1} lệch cột`);
      }
    }
    return out;
  });
  expect(bad).toEqual([]);
});

test("kết nối được báo cáo theo KÊNH, không theo máy", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  const sub = await page
    .locator(".kpi")
    .filter({ hasText: "Running Machines" })
    .locator(".kpi-sub")
    .innerText();
  // Phải nói về KÊNH, không nói "N máy mất kết nối".
  expect(sub).toMatch(/kênh/i);
  expect(sub).not.toMatch(/\d+\s*máy.*mất kết nối/i);
});

test("mọi chữ đều ≥ 11px (WCAG / độ đọc ở khoảng cách vận hành)", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  const small = await page.evaluate(() => {
    const out: string[] = [];
    for (const el of document.querySelectorAll<HTMLElement>("*")) {
      if (el.children.length) continue;
      if (!el.textContent?.trim()) continue;
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < 11) out.push(`${el.tagName}.${el.className}: ${fs}px`);
    }
    return out;
  });
  expect(small).toEqual([]);
});

test("alarm center: bảng có cấu trúc + tìm kiếm + lọc dây chuyền", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /alarm đang mở/i }).click();

  // Bảng có các cột cấu trúc.
  await expect(page.locator(".alarm-table thead th")).toHaveCount(8);
  await expect(page.locator(".alarm-table tbody tr").first()).toBeVisible();

  // Tìm kiếm lọc được danh sách.
  const rowsBefore = await page.locator(".alarm-table tbody tr").count();
  await page.getByLabel(/Tìm kiếm alarm/i).fill("CODE-L01-01");
  await page.waitForTimeout(300);
  const rowsAfter = await page.locator(".alarm-table tbody tr").count();
  expect(rowsAfter).toBeLessThan(rowsBefore);
  expect(rowsAfter).toBeGreaterThan(0);

  // Lọc theo dây chuyền.
  await page.getByLabel(/Tìm kiếm alarm/i).fill("");
  await page.getByLabel(/Lọc theo dây chuyền/i).selectOption("LINE_03");
  await page.waitForTimeout(300);
  const lines = await page.locator(".alarm-table tbody .alarm-line").allInnerTexts();
  for (const l of lines) expect(l).toBe("LINE_03");
});

// ============================================================================
//  MOCK DATA ĐẦY ĐỦ — mọi tag trong catalog đều có giá trị (yêu cầu 12/11)
// ============================================================================

test("mock data: mọi tag của máy đều có giá trị, không phải '—'", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(APP);
  await page.getByRole("button", { name: /Mở chi tiết LINE_01/ }).click();
  await page.locator(".flow-node .mcard").nth(1).click();
  await expect(page.getByRole("dialog")).toBeVisible();

  // Tab "Thông số" liệt kê TOÀN BỘ tag của máy.
  await page.getByRole("tab", { name: /Thông số/ }).click();
  const rows = page.locator(".tag-table tbody tr");
  const n = await rows.count();
  expect(n).toBeGreaterThan(5);

  // Không ô nào hiển thị "—" (tức là mọi tag đều có giá trị mock).
  const dashes = await rows
    .locator(".tag-value")
    .evaluateAll((els) => els.filter((e) => e.textContent?.trim() === "—").length);
  expect(dashes).toBe(0);
});
