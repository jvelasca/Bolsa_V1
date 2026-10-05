/**
 * V2.88.57 — Integridad del deep-link de la operación AUTO.
 *
 * Certifica el defecto P2 de la auditoría de `v2.88.56`: un `cycleId` EXPLÍCITO
 * pero inexistente NO debe caer silenciosamente a `cycles[0]` mostrando la historia
 * de otra operación. Debe declararse «Operación no encontrada» sin pintar etapas.
 *
 * Casos:
 *   - `/auto/operar/operacion/does-not-exist` (ruta canónica)
 *   - `/auto-monitor?mode=operation&cycle=does-not-exist` (override de monitor)
 *
 * Run (auto-starts Vite; API mocked — no Python stack):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-v28857
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

/** El deep-link inválido declara la ausencia y NO pinta la historia de otro ciclo. */
async function expectOperacionNoEncontrada(page: Page, id: string) {
  await expect(
    page.getByTestId("auto-operation-story-not-found"),
  ).toBeVisible();
  await expect(
    page.getByTestId("auto-operation-story-not-found"),
  ).toHaveAttribute("data-cycle-id", id);
  // Ninguna etapa de la operación (ni la del primer ciclo real).
  await expect(page.getByTestId("auto-operation-story-stage")).toHaveCount(0);
  await expect(page.getByTestId("auto-operation-story-context")).toHaveCount(0);
  // Ningún ciclo queda presionado.
  await expect(
    page.locator(
      "[data-testid='auto-operation-story-cycle'][aria-pressed='true']",
    ),
  ).toHaveCount(0);
  await expectSingleMain(page);
  await expectSingleH1(page);
}

test.describe("GP-E2E-V28857 — deep-link de operación inválido", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installAutoWorkspaceMocks(page);
  });

  test("ruta canónica con cycleId inexistente no muestra otra operación", async ({
    page,
  }) => {
    await page.goto("/auto/operar/operacion/does-not-exist");
    await expect(page.getByTestId("auto-operacion-page")).toBeVisible();
    await expectOperacionNoEncontrada(page, "does-not-exist");
  });

  test("el monitor no cae a cycles[0] con un ?cycle= inexistente", async ({
    page,
  }) => {
    await page.goto("/auto-monitor?mode=operation&cycle=does-not-exist");
    await expect(page.getByTestId("auto-monitor-page")).toBeVisible();
    await expectOperacionNoEncontrada(page, "does-not-exist");
  });

  test("la ruta válida sigue mostrando la operación seleccionada", async ({
    page,
  }) => {
    await page.goto("/auto/operar/operacion/e2e-cycle-aaa");
    await expect(page.getByTestId("auto-operation-story-cycles")).toBeVisible();
    await expect(
      page.getByTestId("auto-operation-story-not-found"),
    ).toHaveCount(0);
    await expect(
      page.getByTestId("auto-operation-story-stage").first(),
    ).toBeVisible();
    await expect(
      page.locator(
        "[data-testid='auto-operation-story-cycle'][data-cycle-id='e2e-cycle-aaa'][aria-pressed='true']",
      ),
    ).toHaveCount(1);
    await expectSingleMain(page);
    await expectSingleH1(page);
  });
});
