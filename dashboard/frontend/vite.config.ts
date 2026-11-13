import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

// 3 entry point:
//   /                   → giao diện vận hành MES (4 màn) — APP CHÍNH
//   /diagnostics.html  → trang chẩn đoán pipeline (Factory Pulse)
//   /mock.html         → alias của app chính (giữ để các script cũ chạy được)
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        diagnostics: resolve(__dirname, 'diagnostics.html'),
        mock: resolve(__dirname, 'mock.html'),
      },
      output: {
        manualChunks: { charts: ['recharts'], signalr: ['@microsoft/signalr'] },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5080',
      '/health': 'http://localhost:5080',
      '/hubs': { target: 'http://localhost:5080', ws: true },
      // `state-api` (FastAPI, nhánh streaming) — WebSocket /ws/machines.
      // Tiền tố `/state-api` chỉ để tránh đụng `/api` của backend .NET cũ;
      // phải BÓC tiền tố trước khi chuyển tiếp (FastAPI không có prefix này).
      '/state-api': {
        target: 'http://localhost:8000',
        ws: true,
        rewrite: (p) => p.replace(/^\/state-api/, ''),
      },
      // `master-api` (FastAPI) — master data: dòng chạy, SKU, work order,
      // kế hoạch sản lượng. Đọc từ PostgreSQL master (fallback JSON).
      '/master-api': {
        target: 'http://localhost:8001',
        rewrite: (p) => p.replace(/^\/master-api/, ''),
      },
    },
  },
});
