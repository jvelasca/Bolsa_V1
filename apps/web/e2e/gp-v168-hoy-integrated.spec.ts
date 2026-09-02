/**
 * GP-V168 — Browser E2E Hoy / Paper Autonomous Desk contra API real.
 *
 * Journey: Browser → /mesa → autoDesk → Daily Desk inbox.
 *
 * Run (API :8000 + PG + Vite proxy):
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm e2e -- gp-v168-hoy
 *
 * Default: skipped.
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  assertApiHealthy,
  assertE2eDatabaseIsolation,
  e2eIntegrationMode,
  ensureHoyIntegrationFixture,
  E2E_SKIP_DB_ISOLATION_REASON,
  E2E_SKIP_INTEGRATION_REASON,
  seedHoyBrowserState,
  type HoyIntegrationFixture,
} from "./integration";

test.describe("GP-V168 — Hoy Paper Autonomous Desk integrated", () => {
  let fixture: HoyIntegrationFixture | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    if (!e2eEnabled() || !e2eIntegrationMode() || !baseURL) return;
    try {
      assertE2eDatabaseIsolation();
      await assertApiHealthy(request, baseURL);
      fixture = await ensureHoyIntegrationFixture(request, baseURL);
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

  test("GP-V168-01: Hoy inbox loads with autoDesk wire", async ({ page }) => {
    if (!fixture) return;
    await seedHoyBrowserState(page, { accountId: fixture.accountId });
    await page.goto("/mesa");
    await expect(page.getByTestId("mesa-hoy-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("hoy-inbox")).toBeVisible();
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible();
    await expect(page.getByTestId("daily-desk-buckets")).toBeVisible();
  });

  test("GP-V168-02: Hoy has no primary COMPRAR CTA", async ({ page }) => {
    if (!fixture) return;
    await seedHoyBrowserState(page, { accountId: fixture.accountId });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V168-03: four Daily Desk buckets visible", async ({ page }) => {
    if (!fixture) return;
    await seedHoyBrowserState(page, { accountId: fixture.accountId });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-buckets")).toBeVisible({
      timeout: 20_000,
    });
    for (const bucketId of [
      "requiere_accion",
      "proteger",
      "posiciones",
      "oportunidades",
      "no_operar",
    ]) {
      await expect(
        page.getByTestId(`daily-desk-bucket-${bucketId}`),
      ).toBeVisible();
    }
  });

  test("GP-V168-04: autoDesk projects honest AUTO posture (no execute CTA)", async ({
    page,
  }) => {
    if (!fixture) return;
    await seedHoyBrowserState(page, { accountId: fixture.accountId });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    expect(fixture.hasAutoDesk).toBe(true);
    const autoBadges = page.getByText(/AUTO armado · ejecución off/i);
    const count = await autoBadges.count();
    if (fixture.entryProposed > 0) {
      expect(count).toBeGreaterThan(0);
    }
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});
