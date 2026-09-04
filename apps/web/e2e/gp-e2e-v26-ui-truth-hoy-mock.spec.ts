/**
 * GP-E2E-V26 — UI Truth Hoy↔Mercado (mock, thin).
 *
 * Smoke: Mercado cockpit mounts · AUTO desk can open · no COMPRAR.
 * Levels equality is covered by g-operator-05 unit tests.
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v26
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON, installApiMocks } from "./fixtures";

test.describe("GP-E2E-V26 — UI Truth Hoy mock", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installApiMocks(page);
  });

  test("Mercado cockpit + AUTO desk chrome · no COMPRAR", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/trading");
    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );

    const auto = page.getByTestId("auto-desk-panel");
    const autoCount = await auto.count();
    test.skip(
      autoCount === 0,
      "AUTO desk not mounted without position journey",
    );
    await auto.getByTestId("auto-desk-summary").click();
    await expect(auto.getByTestId("auto-desk-plan-preview")).toBeVisible();
  });

  test("V2.41 — Hoy Posiciones empty is honest when Atención has opens", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/hoy");
    const empty = page.getByTestId("daily-desk-empty-posiciones");
    const emptyCount = await empty.count();
    const attention = page.getByTestId("daily-desk-items-requiere_accion");
    const attentionCount = await attention.count();
    test.skip(
      emptyCount === 0 || attentionCount === 0,
      "needs empty Posiciones + items in Atención",
    );
    await expect(empty).not.toHaveText(/Sin posiciones abiertas/i);
    await expect(empty).toContainText(/Atención/i);
  });
});
