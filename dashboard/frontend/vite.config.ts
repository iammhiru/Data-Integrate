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
    },
  },
});
