/**
 * S5 — puente AUTO → estrategia/indicadores → verificación DÍA-D (UI-only).
 *
 * Desde la operación de AUTO se debe poder ver (a) la **estrategia #1** que sustenta la señal con
 * los **indicadores que la sustentan** y la **razón**, y (b) lanzar la **verificación DÍA-D** bajo
 * demanda («Verificar D→hoy») que entra la sesión LAB y navega al verificador DÍA-D. Un hueco se
 * declara («Sin dato todavía»), nunca se fabrica.
 *
 * Cubre el hueco que quedó `skipped` en v2.88.103 (AUTO sin camino a la estrategia ni al DÍA-D).
 *
 * Run (auto-starts Vite; API mocked — no Python stack):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-s5
 * Default (no env): skipped.
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installAutoWorkspaceMocks,
} from "./fixtures";

/** Un `<main>` visible: se excluye el keep-alive de Backtests (`aria-hidden`/`inert`). */
async function expectSingleMain(page: Page) {
  await expect(
    page.locator("main:not([data-testid='backtests-keepalive-host'])"),
  ).toHaveCount(1);
}

test.describe("GP-E2E-S5 — puente AUTO → estrategia → DÍA-D", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installAutoWorkspaceMocks(page);
  });

  test("la operación muestra la estrategia #1 con sus indicadores y razón (P3)", async ({
    page,
  }) => {
    await page.goto("/auto/operar/operacion/e2e-cycle-aaa");

    await expect(page.getByTestId("auto-operation-strategy")).toBeVisible();
    await expect(
      page.getByTestId("auto-operation-strategy-label"),
    ).toContainText("#1 SMA cross");
    await expect(
      page.getByTestId("auto-operation-strategy-indicators"),
    ).toContainText("RSI");
    await expect(
      page.getByTestId("auto-operation-strategy-reason"),
    ).toContainText("Estrellas 3/5");
    // Con la cadena resuelta no se declara ningún hueco.
    await expect(page.getByTestId("auto-operation-strategy-gap")).toHaveCount(
      0,
    );
    await expectSingleMain(page);
  });

  test("«Verificar D→hoy» navega al verificador DÍA-D LAB con el instrumento y la #1 (P4)", async ({
    page,
  }) => {
    await page.goto("/auto/operar/operacion/e2e-cycle-aaa");

    const cta = page.getByTestId("auto-operation-strategy-verify-dia-d");
    await expect(cta).toBeVisible();
    await expect(cta).toBeEnabled();
    await cta.click();

    await expect(page).toHaveURL(/\/backtests\?/);
    const url = new URL(page.url());
    expect(url.pathname).toBe("/backtests");
    expect(url.searchParams.get("tab")).toBe("run");
    expect(url.searchParams.get("instrumentId")).toBe("inst-e2e-aaa");
    expect(url.searchParams.get("focus")).toBe("detail");
    expect(url.searchParams.get("verify")).toBe("1");
    // El host del verificador DÍA-D queda montado (banner + película).
    await expect(page.getByTestId("dia-d-verify-host")).toBeVisible();
  });
});
