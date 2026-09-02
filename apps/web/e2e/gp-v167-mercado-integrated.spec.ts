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
  ensureMercadoIntegrationFixture,
  gateIntegratedE2eEnvironment,
  seedMercadoBrowserState,
  type MercadoIntegrationFixture,
} from "./integration";

test.describe("GP-V167 — Mercado integrated browser journey", () => {
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

  test("GP-V167-01: Mercado cockpit loads against real API", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
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
    if (!fixture) throw new Error("fixture required");
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
    if (!fixture) throw new Error("fixture required");
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
    if (!fixture) throw new Error("fixture required");
    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: fixture.workspaceDocument,
    });
    await page.goto("/trading");
    await expect(page.getByTestId("operativa-cockpit")).toBeVisible({
      timeout: 20_000,
    });
    if (!fixture.hasOpenPosition) {
      throw new Error("Requires portfolio buy seed");
    }
    await expect(
      page.getByTestId("position-operational-star-card"),
    ).toBeVisible();
    await expect(page.getByTestId("position-decision-stop")).toBeVisible();
  });

  test("GP-V167-05: ¿Por qué? opens decision explain panel", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
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
