// Entry point riêng cho MOCK — không ảnh hưởng app chính (src/main.tsx).
// Chạy: http://127.0.0.1:5173/mock.html
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import MockApp from "./App";

createRoot(document.getElementById("mock-root")!).render(
  <StrictMode>
    <MockApp />
  </StrictMode>,
);
