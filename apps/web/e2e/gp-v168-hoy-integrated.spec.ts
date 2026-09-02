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
  ensureHoyIntegrationFixture,
  gateIntegratedE2eEnvironment,
  seedHoyBrowserState,
  type HoyIntegrationFixture,
} from "./integration";

test.describe("GP-V168 — Hoy Paper Autonomous Desk integrated", () => {
  let environmentSkip: string | null = null;
  let fixture: HoyIntegrationFixture | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    environmentSkip = await gateIntegratedE2eEnvironment(request, baseURL, {
      e2eEnabled: e2eEnabled(),
      e2eSkipReason: E2E_SKIP_REASON,
    });
    if (environmentSkip || !baseURL) return;
    fixture = await ensureHoyIntegrationFixture(request, baseURL);
  });

  test.beforeEach(() => {
    if (environmentSkip) {
      test.skip(true, environmentSkip);
    }
    if (!fixture) {
      throw new Error(
        "Hoy E2E fixture missing after environment gates (fixture/product failure).",
      );
    }
  });

  test("GP-V168-01: Hoy inbox loads with autoDesk wire", async ({ page }) => {
    if (!fixture) throw new Error("fixture required");
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
    if (!fixture) throw new Error("fixture required");
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
    if (!fixture) throw new Error("fixture required");
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
    if (!fixture) throw new Error("fixture required");
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
