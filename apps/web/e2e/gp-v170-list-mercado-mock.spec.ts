/**
 * GP-V170 — LISTA→GRÁFICO→ACCIÓN (mock API).
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-v170-list
 */
import { test, expect } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installMercadoApiMocks,
} from "./fixtures";
import {
  E2E_INSTRUMENT_ID,
  E2E_SYMBOL,
  mercadoListFocusWorkspaceDocument,
  seedMercadoBrowserState,
} from "./integration";

test.describe("GP-V170 — Lista→Gráfico→Acción mock", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installMercadoApiMocks(page);
    await seedMercadoBrowserState(page, {
      workspaceDocument: mercadoListFocusWorkspaceDocument(),
      operativaOpen: false,
    });
  });

  test("GP-V170-02: mock list click aligns list badge phase with cockpit", async ({
    page,
  }) => {
    await page.goto("/trading");
    const listRow = page.getByTestId(`list-instrument-open-${E2E_SYMBOL}`);
    await expect(listRow).toBeVisible({ timeout: 20_000 });

    const listPhase = await listRow
      .locator('[data-testid="list-operativa-phase"]')
      .getAttribute("data-phase");
    expect(listPhase).toBeTruthy();

    await listRow.click();

    await expect(page.getByTestId("chart-indicators-zone")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("chart-indicators-zone")).toHaveAttribute(
      "data-instrument-id",
      E2E_INSTRUMENT_ID,
    );
    await expect(page.getByTestId("operativa-cockpit")).toHaveAttribute(
      "data-phase",
      listPhase!,
    );
    await expect(page.getByTestId("operativa-cockpit")).toHaveAttribute(
      "data-instrument-id",
      E2E_INSTRUMENT_ID,
    );
    await expect(page.getByTestId("operativa-cockpit")).toHaveAttribute(
      "data-symbol",
      E2E_SYMBOL,
    );
  });
});
