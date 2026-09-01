/**
 * GP-V164-UI-01..02 — Browser E2E contra FastAPI + PostgreSQL real.
 *
 * Complementa GP-V159-* (pytest ASGI) con journeys UI en navegador.
 *
 * Run (API :8000 + PG + Vite proxy):
 *   E2E_INTEGRATION=1 E2E_RUN=1 pnpm e2e -- gp-v164-ui
 *
 * Default: skipped.
 */
import { test, expect } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  assertApiHealthy,
  e2eIntegrationMode,
  E2E_SKIP_INTEGRATION_REASON,
} from "./integration";

test.describe("GP-V164-UI — integrated browser journeys", () => {
  test.beforeEach(async ({ request, baseURL }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    test.skip(!e2eIntegrationMode(), E2E_SKIP_INTEGRATION_REASON);
    if (!baseURL) {
      test.skip(true, "baseURL required");
      return;
    }
    try {
      await assertApiHealthy(request, baseURL);
    } catch (err) {
      test.skip(true, String(err));
    }
  });

  test("GP-V164-UI-01: decision journal loads against real API", async ({
    page,
  }) => {
    await page.goto("/decision-journal");
    await expect(page.getByTestId("decision-journal")).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByRole("heading", { name: "Decision Journal" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V164-UI-02: operational console loads against real API", async ({
    page,
  }) => {
    await page.goto("/operational-console");
    await expect(page.getByTestId("operational-console")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText(/Resolver excepciones/i)).toBeVisible();
    await expect(page.getByTestId("daily-desk-inbox")).toHaveCount(0);
  });
});
