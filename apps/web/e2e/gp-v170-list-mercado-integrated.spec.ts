/**
 * GP-V170 — LISTA→GRÁFICO→ACCIÓN integrado (API real).
 *
 * Journey: click fila Cartera → pestaña gráfico → cockpit DECISIÓN mismo símbolo/fase.
 * Workspace sin gráfico pre-seedeado. Panel DECISIÓN cerrado al inicio.
 *
 * Run:
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm e2e -- gp-v170-list
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  assertApiHealthy,
  assertE2eDatabaseIsolation,
  e2eIntegrationMode,
  ensureMercadoIntegrationFixture,
  E2E_SKIP_DB_ISOLATION_REASON,
  E2E_SKIP_INTEGRATION_REASON,
  mercadoListFocusWorkspaceDocument,
  seedMercadoBrowserState,
  type MercadoIntegrationFixture,
} from "./integration";

test.describe("GP-V170 — Lista→Gráfico→Acción integrated", () => {
  let fixture: MercadoIntegrationFixture | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    if (!e2eEnabled() || !e2eIntegrationMode() || !baseURL) return;
    try {
      assertE2eDatabaseIsolation();
      await assertApiHealthy(request, baseURL);
      fixture = await ensureMercadoIntegrationFixture(request, baseURL);
    } catch {
      fixture = null;
    }
  });

  test.beforeEach(async ({ request, baseURL }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    test.skip(!e2eIntegrationMode(), E2E_SKIP_INTEGRATION_REASON);
    if (!baseURL) {
      test.skip(true, "baseURL required");
      return;
    }
    try {
      assertE2eDatabaseIsolation();
      await assertApiHealthy(request, baseURL);
    } catch (err) {
      test.skip(true, String(err));
    }
    if (!fixture) {
      test.skip(true, E2E_SKIP_DB_ISOLATION_REASON);
    }
  });

  test("GP-V170-01: list row opens chart + cockpit with matching phase", async ({
    page,
  }) => {
    if (!fixture) return;
    test.skip(!fixture.hasOpenPosition, "Requires portfolio buy seed");

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

    const listPhase = await listRow
      .locator('[data-testid="list-operativa-phase"]')
      .getAttribute("data-phase");
    expect(listPhase).toBeTruthy();
    expect(listPhase).not.toBe("sin_contexto");

    await listRow.click();

    await expect(page.getByTestId("chart-indicators-zone")).toBeVisible({
      timeout: 20_000,
    });
    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).toHaveAttribute("data-phase", listPhase!);
    await expect(page.getByText(fixture.symbol).first()).toBeVisible();
  });

  test("GP-V170-03: list click opens DECISIÓN panel when collapsed", async ({
    page,
  }) => {
    if (!fixture) return;
    test.skip(!fixture.hasOpenPosition, "Requires portfolio buy seed");

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
  });
});
