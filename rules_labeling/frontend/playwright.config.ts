import { defineConfig, devices } from '@playwright/test';

const dbPath = '/tmp/rules-labeling-e2e.duckdb';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: `cd ../backend && uv run python ../scripts/seed_e2e_db.py ${dbPath} && uv run rules-labeling-api --db ${dbPath} --host 127.0.0.1 --port 8000`,
      url: 'http://127.0.0.1:8000/api/health',
      timeout: 20_000,
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --port 5173',
      url: 'http://127.0.0.1:5173',
      timeout: 20_000,
      reuseExistingServer: false,
    },
  ],
});
