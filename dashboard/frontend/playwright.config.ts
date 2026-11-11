import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests', timeout: 30000, use: { baseURL: process.env.PREVIEW_URL || 'http://127.0.0.1:5173', headless: true }, reporter: 'list' });
