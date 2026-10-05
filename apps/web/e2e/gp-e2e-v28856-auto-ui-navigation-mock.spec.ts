/**
 * V2.88.56 — AUTO UI REFACTOR 2.1: navegación canónica del espacio AUTO.
 *
 * Certifica de extremo a extremo el defecto P2 de la auditoría `v2.88.55`:
 *   - `/auto` → `/auto/operar` → `/auto/operar/operacion/:cycleId`
 *   - "Detalle técnico" → `/auto-monitor?mode=current&cycle=...` (monitor experto)
 *   - "Ver heatmap" → `/auto/analisis?tab=dia-d&view=feedback&window=...&symbol=...`
 *   - invariantes ADR-044: un único `<main>` (sin el keep-alive de Backtests) y un `h1` por ruta.
 *
 * Run (auto-starts Vite; API mocked — no Python stack):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v28856
 * Against an existing dev server:
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e -- gp-e2e-v28856
 *
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

async function expectSingleH1(page: Page) {
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
}

test.describe("GP-E2E-V28856 — AUTO UI 2.1 navigation", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installAutoWorkspaceMocks(page);
  });

  test("Operar → Operación → Detalle técnico (monitor experto con el ciclo)", async ({
    page,
  }) => {
    await page.goto("/auto");

    // `/auto` redirige a la sección por defecto.
    await expect(page).toHaveURL(/\/auto\/operar$/);
    await expect(page.getByTestId("auto-operar-page")).toBeVisible();
    await expectSingleMain(page);
    await expectSingleH1(page);

    const link = page.getByTestId("auto-operar-operation-link").first();
    await expect(link).toBeVisible();
    await link.click();

    await expect(page.getByTestId("auto-operacion-page")).toBeVisible();
    await expect(page).toHaveURL(/\/auto\/operar\/operacion\/e2e-cycle-aaa$/);
    await expectSingleMain(page);
    await expectSingleH1(page);

    // El botón del detalle técnico necesita el ciclo cargado para llevar su `cycleId`.
    await expect(page.getByTestId("auto-operation-story-cycles")).toBeVisible();
    await page.getByTestId("auto-operation-story-open-technical").click();

    await expect(page).toHaveURL(/\/auto-monitor\?/);
    const url = new URL(page.url());
    expect(url.pathname).toBe("/auto-monitor");
    expect(url.searchParams.get("mode")).toBe("current");
    expect(url.searchParams.get("cycle")).toBe("e2e-cycle-aaa");

    await expect(page.getByTestId("auto-monitor-page")).toBeVisible();
    // El `cycle` NO es inerte: la tarjeta del ciclo queda enfocada.
    await expect(
      page.locator(
        "[data-testid='auto-monitor-cycle'][data-cycle-id='e2e-cycle-aaa']",
      ),
    ).toHaveAttribute("data-cycle-focused", "true");
    await expectSingleMain(page);
    await expectSingleH1(page);
  });

  test("Operación → Ver heatmap lleva al DÍA-D del workspace AUTO", async ({
    page,
  }) => {
    await page.goto("/auto/operar/operacion/e2e-cycle-aaa");

    await expect(
      page.getByTestId("auto-operation-story-open-heatmap"),
    ).toBeVisible();
    await page.getByTestId("auto-operation-story-open-heatmap").click();

    await expect(page).toHaveURL(/\/auto\/analisis\?/);
    const url = new URL(page.url());
    expect(url.pathname).toBe("/auto/analisis");
    expect(url.searchParams.get("tab")).toBe("dia-d");
    expect(url.searchParams.get("view")).toBe("feedback");
    expect(url.searchParams.get("symbol")).toBe("AAA");
    expect(url.searchParams.get("window")).toBe("2026-09-29_2026-09-30");

    await expect(page.getByTestId("auto-analisis-page")).toBeVisible();
    await expect(page.getByTestId("dia-d-auto-feedback-panel")).toBeVisible();
    // El símbolo de la operación llega enfocado a la tabla de feedback.
    await expect(
      page.locator(
        "[data-testid='dia-d-auto-feedback-value'][data-symbol='AAA']",
      ),
    ).toHaveAttribute("data-focused", "true");
    await expectSingleMain(page);
    await expectSingleH1(page);
  });

  test("cada ruta AUTO expone un main y un h1 únicos (ADR-044)", async ({
    page,
  }) => {
    const routes = [
      "/auto/operar",
      "/auto/cartera",
      "/auto/riesgo",
      "/auto/analisis",
      "/auto/sistema",
      "/auto-monitor?mode=operation",
    ];
    for (const route of routes) {
      await page.goto(route);
      await expect(
        page
          .getByTestId("auto-workspace")
          .or(page.getByTestId("auto-monitor-page")),
      ).toBeVisible();
      await expectSingleMain(page);
      await expectSingleH1(page);
    }
  });
});
