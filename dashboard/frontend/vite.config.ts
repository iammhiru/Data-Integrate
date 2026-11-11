import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], build: { rollupOptions: { output: { manualChunks: { charts: ['recharts'], signalr: ['@microsoft/signalr'] } } } }, server: { proxy: {
  '/api': 'http://localhost:5080', '/health': 'http://localhost:5080',
  '/hubs': { target: 'http://localhost:5080', ws: true }
} } });
