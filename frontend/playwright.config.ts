import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';
const python = resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python');
export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1, timeout: 45000,
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure', screenshot: 'only-on-failure', headless: true },
  webServer: [
    { command: `"${python}" ../backend/e2e_server.py`, url: 'http://127.0.0.1:5051/api/health', reuseExistingServer: false, timeout: 120000 },
    { command: 'npm run dev -- --port 5174 --strictPort', url: 'http://127.0.0.1:5174', env: { API_PROXY_TARGET: 'http://127.0.0.1:5051' }, reuseExistingServer: false, timeout: 120000 },
  ],
});
