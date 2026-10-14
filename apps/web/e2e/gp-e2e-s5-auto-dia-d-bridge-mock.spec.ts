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
  installApiMocks,
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
    // H6 — el ciclo DECLARA su `presetKey` y este casa con el `strategyType` del TOP #1: la
    // estrategia EJECUTADA queda resuelta (identidad EXACTA, no la «mejor disponible»).
    await expect(
      page.getByTestId("auto-operation-strategy-preset-key"),
    ).toContainText("sma_crossover");
    await expect(
      page.getByTestId("auto-operation-strategy-match"),
    ).toHaveAttribute("data-match", "same");
    await expect(
      page.getByTestId("auto-operation-strategy-executed"),
    ).toHaveAttribute("data-verify-target", "executed");
    await expect(
      page.getByTestId("auto-operation-strategy-executed"),
    ).toContainText("#1 SMA cross");
    await expectSingleMain(page);
  });

  test("«Verificar D→hoy» navega al verificador DÍA-D LAB con el instrumento y la EJECUTADA (P4)", async ({
    page,
  }) => {
    await page.goto("/auto/operar/operacion/e2e-cycle-aaa");

    const cta = page.getByTestId("auto-operation-strategy-verify-dia-d");
    await expect(cta).toBeVisible();
    // H6 — el CTA verifica la estrategia EJECUTADA del ciclo (resuelta por identidad EXACTA),
    // no la «mejor disponible» del TOP.
    await expect(cta).toHaveAttribute("data-verify-target", "executed");
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

  test("sin estrategia ejecutada resoluble el CTA se inhabilita y declara el hueco (H6)", async ({
    page,
  }) => {
    // El ciclo declara una `presetKey` que NO existe en el TOP del valor: H6 es fail-closed y
    // NUNCA cae en silencio al #1 (se declara el hueco y el CTA queda deshabilitado).
    await installApiMocks(page, {
      auto: true,
      autoCyclePresetKey: "estrategia_no_declarada_en_el_top",
    });
    await page.goto("/auto/operar/operacion/e2e-cycle-aaa");

    await expect(page.getByTestId("auto-operation-strategy")).toBeVisible();
    // La cadena (instrumento → TOP → definición) SÍ se resuelve: el hueco es solo de la ejecutada.
    await expect(page.getByTestId("auto-operation-strategy-gap")).toHaveCount(
      0,
    );
    await expect(
      page.getByTestId("auto-operation-strategy-preset-key"),
    ).toContainText("estrategia_no_declarada_en_el_top");
    await expect(
      page.getByTestId("auto-operation-strategy-match"),
    ).toHaveAttribute("data-match", "differs");

    const executed = page.getByTestId("auto-operation-strategy-executed");
    await expect(executed).toHaveAttribute("data-verify-target", "none");
    await expect(executed).toContainText(
      "no está entre las estrategias del valor",
    );

    const cta = page.getByTestId("auto-operation-strategy-verify-dia-d");
    await expect(cta).toHaveAttribute("data-verify-target", "none");
    await expect(cta).toBeDisabled();
    await expect(cta).toHaveAttribute(
      "title",
      /no está entre las estrategias del valor/,
    );
  });
});
