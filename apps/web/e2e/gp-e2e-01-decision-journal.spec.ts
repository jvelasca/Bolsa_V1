/**
 * GP-E2E-01 — Decision Journal smoke (spec-v156 §2).
 *
 * Asserts `/decision-journal` loads read-only chrome: `data-testid="decision-journal"`
 * visible and no primary COMPRAR CTA.
 *
 * Run (auto-starts Vite; API mocked — no Python stack):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-01
 *
 * Run against existing dev server:
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e -- gp-e2e-01
 *
 * Default (no env): skipped.
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON, installApiMocks } from "./fixtures";

test.describe("GP-E2E-01 — Decision Journal", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installApiMocks(page);
  });

  test("loads read-only journal without COMPRAR primary CTA", async ({
    page,
  }) => {
    await page.goto("/decision-journal");

    await expect(page.getByTestId("decision-journal")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Decision Journal" }),
    ).toBeVisible();

    const buyButtons = page.getByRole("button", { name: /^COMPRAR$/i });
    await expect(buyButtons).toHaveCount(0);

    const buyLinks = page.getByRole("link", { name: /^COMPRAR$/i });
    await expect(buyLinks).toHaveCount(0);
  });
});
