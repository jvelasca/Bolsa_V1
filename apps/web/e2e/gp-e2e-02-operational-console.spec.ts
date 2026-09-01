/**
 * GP-E2E-02 — Operational Console smoke (spec-v156 §2).
 *
 * Asserts `/operational-console` is excepciones-only: header copy, link to Libro/Mesa,
 * no duplicate Daily Desk inbox buckets.
 *
 * Run (auto-starts Vite; API mocked — no Python stack):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-02
 *
 * Run against existing dev server:
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e -- gp-e2e-02
 *
 * Default (no env): skipped.
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON, installApiMocks } from "./fixtures";

test.describe("GP-E2E-02 — Operational Console", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installApiMocks(page);
  });

  test("shows excepciones-only chrome with Libro link and no Daily Desk inbox", async ({
    page,
  }) => {
    await page.goto("/operational-console");

    await expect(page.getByTestId("operational-console")).toBeVisible();
    await expect(page.getByText(/Resolver excepciones/i)).toBeVisible();
    await expect(
      page.getByRole("link", { name: /Libro · Operaciones/i }).first(),
    ).toBeVisible();

    await expect(page.getByTestId("daily-desk-inbox")).toHaveCount(0);
    await expect(page.getByTestId("daily-desk-buckets")).toHaveCount(0);
    await expect(page.getByTestId("hoy-inbox")).toHaveCount(0);
  });
});
