/**
 * Playwright — GP-E2E-01/02/03 smoke + GP-V164-UI integrado (spec-v156 / v164).
 *
 * Skip-by-default: set `E2E_RUN=1` to auto-start Vite (`pnpm dev`) with API mocks
 * in the specs, or `PLAYWRIGHT_BASE_URL` to hit an existing server.
 *
 * Examples:
 *   E2E_RUN=1 pnpm e2e
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e
 */
import { defineConfig } from "@playwright/test";

const port = Number(process.env.WEB_PORT ?? 5173);
const baseURL = (
  process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${port}`
).replace(/\/$/, "");
const e2eRun = process.env.E2E_RUN === "1";

export default defineConfig({
  testDir: "./e2e",
  /** Vitest unit tables live under e2e/helpers/*.test.ts — never load them in Playwright. */
  testIgnore: ["**/helpers/**/*.test.ts"],
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  webServer: e2eRun
    ? {
        command: "pnpm dev",
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      }
    : undefined,
});
