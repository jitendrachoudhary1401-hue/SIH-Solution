import { defineConfig } from '@playwright/test';
const python = process.platform === 'win32' ? '..\\.venv\\Scripts\\python.exe' : '../.venv/bin/python';
export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1, timeout: 45000,
  use: { baseURL: 'http://127.0.0.1:5051', trace: 'retain-on-failure', screenshot: 'only-on-failure', headless: true },
  webServer: { command: `"${python}" ../backend/e2e_server.py`, url: 'http://127.0.0.1:5051/api/health', reuseExistingServer: false, timeout: 120000 },
});
