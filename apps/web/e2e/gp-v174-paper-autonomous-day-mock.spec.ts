/**
 * GP-V174 — Paper Autonomous Day (mock API).
 *
 * Journey: Estudio→ranking→TradePlan→OpeningGate→AUTO (dryRun) → T1 position
 * → Hoy inbox → Journal → Mercado identity.
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installHoyPaperDayApiMocks,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  mercadoListFocusWorkspaceDocument,
  paperAutonomousDaySlice,
  seedPaperDayBrowserState,
} from "./integration";

async function assertMercadoPositionIdentity(
  page: Page,
  slice: ReturnType<typeof paperAutonomousDaySlice>,
) {
  const chartZone = page.getByTestId("chart-indicators-zone");
  await expect(chartZone).toBeVisible({ timeout: 20_000 });
  await expect(chartZone).toHaveAttribute(
    "data-instrument-id",
    slice.instrumentId,
  );

  const cockpit = page.getByTestId("operativa-cockpit");
  await expect(cockpit).toBeVisible({ timeout: 20_000 });
  await expect(cockpit).toHaveAttribute(
    "data-instrument-id",
    slice.instrumentId,
  );
  await expect(cockpit).toHaveAttribute("data-symbol", slice.symbol);
  await expect(cockpit).toHaveAttribute("data-position-id", slice.positionId);
  await expect(
    page.getByTestId("position-operational-star-card"),
  ).toBeVisible();
}

test.describe("GP-V174 — Paper Autonomous Day mock", () => {
  const slice = paperAutonomousDaySlice();
  const listDoc = mercadoListFocusWorkspaceDocument({
    instrumentId: slice.instrumentId,
    symbol: slice.symbol,
    name: "E2E Paper Day",
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    setMercadoMockWorkspaceDocument(listDoc);
    await installHoyPaperDayApiMocks(page);
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
  });

  test("GP-V174-01: Hoy inbox loads day chain (T1 + entry opportunity)", async ({
    page,
  }) => {
    await seedPaperDayBrowserState(page, { workspaceDocument: listDoc });
    await page.goto("/mesa");
    await expect(page.getByTestId("mesa-hoy-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("hoy-inbox")).toBeVisible();
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible();
    await expect(page.getByTestId("daily-desk-buckets")).toBeVisible();

    await expect(page.getByTestId("daily-desk-cta-AAPL")).toHaveText("Reducir");
    await expect(page.getByText(/T1 alcanzado/i)).toBeVisible();
    await expect(
      page.getByTestId("daily-desk-bucket-requiere_accion"),
    ).toHaveAttribute("data-count", "1");
    await expect(
      page.getByTestId("daily-desk-bucket-oportunidades"),
    ).toHaveAttribute("data-count", "1");
    await expect(page.getByTestId("daily-desk-cta-MSFT")).toHaveText(
      /Preparar operación/i,
    );
  });

  test("GP-V174-02: honest AUTO posture — no COMPRAR CTA", async ({ page }) => {
    await seedPaperDayBrowserState(page, { workspaceDocument: listDoc });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByText(/Plan armado \(AUTO\)|AUTO armado · ejecución off/i),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V174-03: Journal view loads from Hoy deep-link", async ({
    page,
  }) => {
    await seedPaperDayBrowserState(page, { workspaceDocument: listDoc });
    await page.goto("/mesa?view=journal");
    await expect(page.getByTestId("hoy-view-journal")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("daily-desk-inbox")).toHaveCount(0);
  });

  test("GP-V174-04: Hoy→Mercado preserves AAPL position identity", async ({
    page,
  }) => {
    await seedPaperDayBrowserState(page, { workspaceDocument: listDoc });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-cta-AAPL")).toBeVisible({
      timeout: 20_000,
    });

    await page.goto("/trading");
    await assertMercadoPositionIdentity(page, slice);
  });

  test("GP-V174-05: recon ok — no Cartera drift in inbox", async ({ page }) => {
    await seedPaperDayBrowserState(page, { workspaceDocument: listDoc });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText(/reconciliar cartera/i)).toHaveCount(0);
    await expect(page.getByText(/drift/i)).toHaveCount(0);
  });
});
