/**
 * GP-V170 — LISTA→GRÁFICO→ACCIÓN integrado (API real).
 *
 * Journey: click fila Cartera → pestaña gráfico → cockpit DECISIÓN mismo instrumento.
 * Workspace sin gráfico pre-seedeado. Panel DECISIÓN cerrado al inicio.
 *
 * Run:
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm e2e -- gp-v170-list
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  ensureMercadoIntegrationFixture,
  gateIntegratedE2eEnvironment,
  mercadoListFocusWorkspaceDocument,
  seedMercadoBrowserState,
  type MercadoIntegrationFixture,
} from "./integration";

test.describe("GP-V170 — Lista→Gráfico→Acción integrated", () => {
  let environmentSkip: string | null = null;
  let fixture: MercadoIntegrationFixture | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    environmentSkip = await gateIntegratedE2eEnvironment(request, baseURL, {
      e2eEnabled: e2eEnabled(),
      e2eSkipReason: E2E_SKIP_REASON,
    });
    if (environmentSkip || !baseURL) return;
    fixture = await ensureMercadoIntegrationFixture(request, baseURL);
  });

  test.beforeEach(() => {
    if (environmentSkip) {
      test.skip(true, environmentSkip);
    }
    if (!fixture) {
      throw new Error(
        "Mercado E2E fixture missing after environment gates (fixture/product failure).",
      );
    }
  });

  test("GP-V170-01: list row opens chart + cockpit with matching identity", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
    if (!fixture.hasOpenPosition || !fixture.positionId) {
      throw new Error("Requires portfolio buy seed");
    }

    const workspaceDocument = mercadoListFocusWorkspaceDocument({
      instrumentId: fixture.instrumentId,
      symbol: fixture.symbol,
      workspaceId: fixture.workspaceId,
    });

    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument,
      operativaOpen: false,
    });

    await page.goto("/trading");
    const listRow = page.getByTestId(`list-instrument-open-${fixture.symbol}`);
    await expect(listRow).toBeVisible({ timeout: 20_000 });
    await expect(listRow).toHaveAttribute(
      "data-instrument-id",
      fixture.instrumentId,
    );

    const listPhase = await listRow
      .locator('[data-testid="list-operativa-phase"]')
      .getAttribute("data-phase");
    expect(listPhase).toBeTruthy();
    expect(listPhase).not.toBe("sin_contexto");

    await listRow.click();

    const chartZone = page.getByTestId("chart-indicators-zone");
    await expect(chartZone).toBeVisible({ timeout: 20_000 });
    await expect(chartZone).toHaveAttribute(
      "data-instrument-id",
      fixture.instrumentId,
    );

    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).toHaveAttribute("data-phase", listPhase!);
    await expect(cockpit).toHaveAttribute(
      "data-instrument-id",
      fixture.instrumentId,
    );
    await expect(cockpit).toHaveAttribute("data-symbol", fixture.symbol);
    await expect(cockpit).toHaveAttribute(
      "data-position-id",
      fixture.positionId,
    );
    if (fixture.tradePlanId) {
      await expect(cockpit).toHaveAttribute(
        "data-trade-plan-id",
        fixture.tradePlanId,
      );
    }
    if (fixture.decisionId) {
      await expect(cockpit).toHaveAttribute(
        "data-decision-id",
        fixture.decisionId,
      );
    }

    await expect(page.getByTestId("position-decision-stop")).toBeVisible();
    await expect(page.getByTestId("position-decision-t1")).toBeVisible();
    await expect(page.getByTestId("position-decision-t2")).toBeVisible();
    if (fixture.levels?.currentStop != null) {
      await expect(page.getByTestId("position-decision-stop")).toContainText(
        fixture.levels.currentStop.toFixed(2),
      );
    }
  });

  test("GP-V170-03: list click opens DECISIÓN panel and chart when collapsed", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
    if (!fixture.hasOpenPosition) {
      throw new Error("Requires portfolio buy seed");
    }

    const workspaceDocument = mercadoListFocusWorkspaceDocument({
      instrumentId: fixture.instrumentId,
      symbol: fixture.symbol,
      workspaceId: fixture.workspaceId,
    });

    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument,
      operativaOpen: false,
    });

    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${fixture.symbol}`).click();
    await expect(page.getByTestId("trading-operativa-panel")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible();
    await expect(page.getByTestId("chart-indicators-zone")).toBeVisible();
    await expect(page.getByTestId("operativa-cockpit")).toHaveAttribute(
      "data-instrument-id",
      fixture.instrumentId,
    );
  });
});
