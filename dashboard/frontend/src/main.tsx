// ============================================================================
//  Entry point CHÍNH của MES Dashboard.
//
//  ⚠ 12/11: UI mock đã được chọn làm giao diện chính (4 màn, thiết kế
//    theo prompt.md / work.md / ảnh tham khảo). App "Factory Pulse" cũ
//    (src/App.tsx + src/style.css) được giữ lại làm TRANG CHẨN ĐOÁN PIPELINE
//    tại đường dẫn /diagnostics — chỉ số dữ liệu & độ trễ, không phải giao
//    diện vận hành chính.
//
//  Nguồn dữ liệu: mock-simulator (MOCK). Khi tích hợp SignalR, chỉ thay
//  module nguồn trong `mock/store.ts` — toàn bộ UI giữ nguyên.
// ============================================================================

import React from "react";
import { createRoot } from "react-dom/client";
import App from "./mock/App";
import "./mock/tokens.css";
import "./mock/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
