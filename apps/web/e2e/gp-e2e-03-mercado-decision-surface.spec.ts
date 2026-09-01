/**
 * GP-E2E-03 / GP-V164-UI-03 — Mercado Decision Surface placement (mock).
 *
 * Valida la preferencia panel|gráfico en configuración de plataforma
 * (misma fuente que el toggle del cockpit DECISIÓN).
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-03
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON, installApiMocks } from "./fixtures";

test.describe("GP-E2E-03 — Mercado Decision Surface placement", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installApiMocks(page);
  });

  test("GP-V164-UI-03: platform config Mercado toggle panel ↔ chart", async ({
    page,
  }) => {
    await page.goto("/settings#general");
    await page.waitForURL("**/overview");

    await expect(page.getByText("Ubicación del estado operativo")).toBeVisible({
      timeout: 10_000,
    });
    const toggle = page.getByTestId("decision-surface-placement-toggle");
    await expect(toggle).toBeVisible();

    await expect(
      page.getByText(/estado completo se muestra en el panel DECISIÓN/i),
    ).toBeVisible();

    await toggle.getByRole("button", { name: "Gráfico" }).click();
    await expect(
      page.getByText(/estado compacto flota en el gráfico/i),
    ).toBeVisible();

    await toggle.getByRole("button", { name: "Panel" }).click();
    await expect(
      page.getByText(/estado completo se muestra en el panel DECISIÓN/i),
    ).toBeVisible();

    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});
