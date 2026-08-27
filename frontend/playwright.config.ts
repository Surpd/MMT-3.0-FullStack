import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const backendRoot = resolve(frontendRoot, "../backend");
const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 10000);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT ?? 4173);
const testUserId = process.env.TEST_USER_ID ?? "900000001";
const testUrl = process.env.TEST_SUPABASE_URL?.trim();
const testKey = process.env.TEST_SUPABASE_KEY?.trim();
const e2eBotToken = process.env.E2E_BOT_TOKEN ?? "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
const { TEST_SUPABASE_KEY: _testSupabaseKey, ...frontendProcessEnv } = process.env;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer:
    testUrl && testKey
      ? [
          {
            command: "python scripts/run_test_server.py",
            cwd: backendRoot,
            url: `http://127.0.0.1:${backendPort}/`,
            timeout: 120_000,
            reuseExistingServer: false,
            env: {
              ...process.env,
              BOT_TOKEN: e2eBotToken,
              TMDB_API_KEY: process.env.E2E_TMDB_API_KEY ?? "e2e-no-network",
              TEST_MODE: "true",
              TEST_USER_ID: testUserId,
              RUNTIME_ENV: "development",
              PORT: String(backendPort),
              TEST_SUPABASE_URL: testUrl,
              TEST_SUPABASE_KEY: testKey,
            },
          },
          {
            command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
            cwd: frontendRoot,
            url: `http://127.0.0.1:${frontendPort}/`,
            timeout: 120_000,
            reuseExistingServer: false,
            env: {
              ...frontendProcessEnv,
              VITE_API_BASE: `http://127.0.0.1:${backendPort}`,
              VITE_TEST_MODE: "true",
              VITE_TEST_USER_ID: testUserId,
            },
          },
        ]
      : undefined,
});
