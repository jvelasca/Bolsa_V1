/**
 * GP-V167 — Browser E2E Mercado contra FastAPI + PostgreSQL real.
 *
 * Journey: Browser → /trading → instrumento seed → Decision Surface → API → PG.
 * Cuenta aislada por corrida (`e2e-v167-*`). Requiere opt-in DB.
 *
 * Run (API :8000 + PG + Vite proxy):
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm e2e -- gp-v167-mercado
 *
 * Default: skipped.
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
  seedMercadoBrowserState,
  type MercadoIntegrationFixture,
} from "./integration";

test.describe("GP-V167 — Mercado integrated browser journey", () => {
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

  test("GP-V167-01: Mercado cockpit loads against real API", async ({
    page,
  }) => {
    if (!fixture) return;
    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: fixture.workspaceDocument,
    });
    await page.goto("/trading");
    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).not.toHaveAttribute("data-phase", "sin_contexto");
    await expect(page.getByText(fixture.symbol).first()).toBeVisible();
  });

  test("GP-V167-02: Mercado has no primary COMPRAR CTA", async ({ page }) => {
    if (!fixture) return;
    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: fixture.workspaceDocument,
    });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V167-03: decision surface sections visible", async ({ page }) => {
    if (!fixture) return;
    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: fixture.workspaceDocument,
    });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("decision-contexto")).toBeVisible();
    await expect(page.getByTestId("decision-estado")).toBeVisible();
    await expect(page.getByTestId("decision-accion")).toBeVisible();
  });

  test("GP-V167-04: position or entry surface matches portfolio seed", async ({
    page,
  }) => {
    if (!fixture) return;
    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: fixture.workspaceDocument,
    });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 20_000,
    });
    if (fixture.hasOpenPosition) {
      await expect(
        page.getByTestId("position-operational-star-card"),
      ).toBeVisible();
      await expect(page.getByTestId("position-decision-stop")).toBeVisible();
    } else {
      await expect(page.getByTestId("entry-decision-surface")).toBeVisible();
    }
  });

  test("GP-V167-05: ¿Por qué? opens decision explain panel", async ({
    page,
  }) => {
    if (!fixture) return;
    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: fixture.workspaceDocument,
    });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 20_000,
    });
    await page.getByTestId("operativa-cockpit-why").click();
    await expect(page.getByTestId("decision-explain-panel")).toBeVisible();
  });
});
