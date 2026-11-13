// ============================================================================
//  Entry point của TRANG CHẨN ĐOÁN PIPELINE (Factory Pulse).
//
//  ⚠ 12/11: giao diện vận hành chính của dự án đã chuyển sang UI MES 4 màn
//    (src/mock/App.tsx, phục vụ tại "/"). Trang này được giữ lại ở
//    "/diagnostics.html" vì nó phục vụ MỤC TIÊU CHÍNH của dự án: tích hợp
//    dữ liệu — hiển thị trạng thái pipeline (Kafka → backend → SignalR),
//    độ trễ, chất lượng dữ liệu và truy vấn PostgreSQL.
//
//    Không phải giao diện vận hành cho người chạy nhà máy.
// ============================================================================

import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
