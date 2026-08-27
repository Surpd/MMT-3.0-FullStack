import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const backendRoot = resolve(frontendRoot, "../backend");
const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 10000);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT ?? 4173);
const testUserId = process.env.TEST_USER_ID ?? "900000001";
const e2eBotToken = process.env.E2E_BOT_TOKEN ?? "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
const allowPrimary = process.env.ALLOW_PRODUCTION_TEST_USER?.trim().toLowerCase() === "true";
const e2eTargetConfigured = allowPrimary;
const backendProcessEnv = Object.fromEntries(
  Object.entries(process.env).filter(
    ([name]) => !["TEST_SUPABASE_URL", "TEST_SUPABASE_KEY"].includes(name),
  ),
);
const frontendProcessEnv = Object.fromEntries(
  Object.entries(process.env).filter(
    ([name]) =>
      ![
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "TEST_SUPABASE_URL",
        "TEST_SUPABASE_KEY",
        "ALLOW_PRODUCTION_TEST_USER",
      ].includes(name),
  ),
);

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
  webServer: e2eTargetConfigured
    ? [
        {
          command: "python scripts/run_test_server.py",
          cwd: backendRoot,
          url: `http://127.0.0.1:${backendPort}/`,
          timeout: 120_000,
          reuseExistingServer: false,
          env: {
            ...backendProcessEnv,
            BOT_TOKEN: e2eBotToken,
            TMDB_API_KEY: process.env.E2E_TMDB_API_KEY ?? "e2e-no-network",
            TEST_MODE: "true",
            TEST_USER_ID: testUserId,
            RUNTIME_ENV: "development",
            PORT: String(backendPort),
            ALLOW_PRODUCTION_TEST_USER: "true",
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
