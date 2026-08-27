import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";
import { chromium } from "@playwright/test";

const repoRoot = resolve(process.cwd(), "..");
const testUrl = process.env.TEST_SUPABASE_URL?.trim();
const testKey = process.env.TEST_SUPABASE_KEY?.trim();
const allowPrimary = process.env.ALLOW_PRODUCTION_TEST_USER?.trim().toLowerCase() === "true";
const backendEnvFile = resolve(repoRoot, "backend", ".env");

if (Boolean(testUrl) !== Boolean(testKey)) {
  console.error("E2E refused: TEST_SUPABASE_URL and TEST_SUPABASE_KEY must be provided together.");
  process.exit(1);
}

if (!testUrl && !testKey && !allowPrimary) {
  if (existsSync(backendEnvFile) || process.env.SUPABASE_URL || process.env.SUPABASE_KEY) {
    console.error(
      "E2E refused: the current backend has a Supabase target; set ALLOW_PRODUCTION_TEST_USER=true to use only the reserved synthetic user.",
    );
    process.exit(1);
  }
  console.warn(
    "E2E NOT CONFIGURED (SKIPPED): set TEST_SUPABASE_URL/TEST_SUPABASE_KEY or explicitly opt in with ALLOW_PRODUCTION_TEST_USER=true.",
  );
  process.exit(0);
}

const python = process.env.PYTHON ?? "python";
const backendRoot = resolve(repoRoot, "backend");
const bootstrap = resolve(backendRoot, "scripts", "bootstrap_test_user.py");
if (!existsSync(bootstrap)) {
  console.error(`E2E setup failed: missing ${bootstrap}`);
  process.exit(1);
}

const env = {
  ...process.env,
  TEST_MODE: "true",
  TEST_USER_ID: process.env.TEST_USER_ID ?? "900000001",
  RUNTIME_ENV: "development",
  ALLOW_PRODUCTION_TEST_USER: allowPrimary ? "true" : "false",
  TEST_SUPABASE_URL: testUrl ?? "",
  TEST_SUPABASE_KEY: testKey ?? "",
};

const seed = spawnSync(python, [bootstrap], {
  cwd: backendRoot,
  env,
  stdio: "inherit",
});
if (seed.error) {
  console.error(`E2E setup failed to start Python: ${seed.error.message}`);
  process.exit(1);
}
if (seed.status !== 0) process.exit(seed.status ?? 1);

const playwright = process.platform === "win32" ? "npx.cmd" : "npx";
if (!existsSync(chromium.executablePath())) {
  console.log("Playwright Chromium is not installed; installing it for this test run.");
  const install = spawnSync(playwright, ["playwright", "install", "chromium"], {
    cwd: process.cwd(),
    env,
    stdio: "inherit",
  });
  if (install.error) {
    console.error(`Playwright browser setup failed: ${install.error.message}`);
    process.exit(1);
  }
  if (install.status !== 0) process.exit(install.status ?? 1);
}

const run = spawnSync(playwright, ["playwright", "test", ...process.argv.slice(2)], {
  cwd: process.cwd(),
  env,
  stdio: "inherit",
});
if (run.error) {
  console.error(`Playwright failed to start: ${run.error.message}`);
  process.exit(1);
}
process.exit(run.status ?? 1);
