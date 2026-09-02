/**
 * GP-V178 — Session Golden MERCADO→EXIT (mock API).
 *
 * Journey stages: candidato → Hoy ENTRY dryRun → stale/recovery → POSITION
 * → T1 → TRAIL → recon → EXIT. NINGÚN estado ambiguo → COMPRAR.
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v178
 */
import { test, expect } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installGoldenSessionMocks,
  resetE2eMockRuntimeFlags,
  setE2eMockDeskMode,
  setE2eMockPositionStage,
  setE2eMockReconStatus,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  assertEntryCandidateTruth,
  assertOperationalTruth,
  assertPovOperatingStage,
  E2E_ENTRY_ONLY_INSTRUMENT,
  mercadoEntryPositionWorkspaceDocument,
  mercadoListFocusWorkspaceDocument,
  mercadoMultiInstrumentSlicesFromMock,
  mercadoWorkspaceDocument,
  paperAutonomousDaySlice,
  seedMercadoBrowserState,
  seedPaperDayBrowserState,
} from "./integration";

test.describe("GP-V178 — Session golden MERCADO→EXIT mock", () => {
  const slices = mercadoMultiInstrumentSlicesFromMock();
  const focus = slices[0]!;
  const daySlice = paperAutonomousDaySlice();
  const dayListDoc = mercadoListFocusWorkspaceDocument({
    instrumentId: daySlice.instrumentId,
    symbol: daySlice.symbol,
    name: "E2E Golden Day",
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installGoldenSessionMocks(page);
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
    resetE2eMockRuntimeFlags();
  });

  test("GP-V178-01: MERCADO candidato NVDA — entry surface · 0 COMPRAR", async ({
    page,
  }) => {
    const dualDoc = mercadoEntryPositionWorkspaceDocument({
      positionInstrumentId: focus.instrumentId,
      positionSymbol: focus.symbol,
      entryInstrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
      entrySymbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
    });
    setMercadoMockWorkspaceDocument(dualDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: dualDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await assertOperationalTruth(page, focus, { expectRecon: "CLEAN" });

    await page
      .locator(
        `[data-symbol="${E2E_ENTRY_ONLY_INSTRUMENT.symbol}"][data-instrument-id="${E2E_ENTRY_ONLY_INSTRUMENT.id}"]`,
      )
      .click();
    await assertEntryCandidateTruth(page, {
      instrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
      symbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
    });
  });

  test("GP-V178-02: Hoy ENTRY dryRun — AUTO off · 0 COMPRAR", async ({
    page,
  }) => {
    setE2eMockDeskMode("day");
    setMercadoMockWorkspaceDocument(dayListDoc);
    await seedPaperDayBrowserState(page, { workspaceDocument: dayListDoc });
    const reportPromise = page.waitForResponse(
      (res) => res.ok() && res.url().includes("/paper-desk/daily-report"),
    );
    await page.goto("/mesa");
    const reportRes = await reportPromise;
    const reportJson = (await reportRes.json()) as {
      data?: { autoDesk?: { dryRun?: boolean; paperDExecute?: boolean } };
    };
    expect(reportJson.data?.autoDesk?.dryRun).toBe(true);
    expect(reportJson.data?.autoDesk?.paperDExecute).toBe(false);

    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByText(/Plan armado \(AUTO\)|AUTO armado · ejecución off/i),
    ).toBeVisible();
    await expect(
      page.getByTestId("daily-desk-bucket-oportunidades"),
    ).toHaveAttribute("data-count", "1");
    await expect(page.getByTestId("daily-desk-cta-MSFT")).toHaveText(
      /Preparar operación/i,
    );
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V178-03: Hoy STALE → recovery sin inventar COMPRAR", async ({
    page,
  }) => {
    setE2eMockDeskMode("stale");
    setMercadoMockWorkspaceDocument(dayListDoc);
    await seedPaperDayBrowserState(page, { workspaceDocument: dayListDoc });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    const deny = page.getByTestId("daily-desk-item-auto-deny-inst-msft");
    await expect(deny).toBeVisible();
    await expect(deny).toHaveAttribute("data-attention", "BLOCKED");
    await expect(deny).toHaveAttribute("data-reason-code", "ENTRY_STALE_DATA");
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );

    setE2eMockDeskMode("day");
    await seedPaperDayBrowserState(page, { workspaceDocument: dayListDoc });
    await page.reload();
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByTestId("daily-desk-bucket-oportunidades"),
    ).toHaveAttribute("data-count", "1");
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V178-04: POSITION Mercado — operational truth", async ({ page }) => {
    const listDoc = mercadoListFocusWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    await assertOperationalTruth(page, focus, {
      expectRecon: "CLEAN",
      expectFreshness: "current",
    });
  });

  test("GP-V178-05: T1_READY — Reducir · 0 COMPRAR", async ({ page }) => {
    setE2eMockPositionStage("t1_ready");
    const listDoc = mercadoWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    await assertPovOperatingStage(page, focus, {
      operatingState: "T1_READY",
      actionText: /Reducir/i,
    });
  });

  test("GP-V178-06: TRAILING — Proteger · 0 COMPRAR", async ({ page }) => {
    setE2eMockPositionStage("trailing");
    const listDoc = mercadoWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    await assertPovOperatingStage(page, focus, {
      operatingState: "TRAILING",
      actionText: /Proteger/i,
    });
  });

  test("GP-V178-07: recon drift → clean · 0 COMPRAR", async ({ page }) => {
    const listDoc = mercadoWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    setE2eMockReconStatus("drift");
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    await assertOperationalTruth(page, focus, {
      expectRecon: "CRITICAL",
      expectFreshness: "current",
    });
    await expect(
      page.getByTestId("operativa-cockpit-pov-action"),
    ).toContainText(/Revisar/i);
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );

    setE2eMockReconStatus("ok");
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.reload();
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    await assertOperationalTruth(page, focus, {
      expectRecon: "CLEAN",
      expectFreshness: "current",
    });
  });

  test("GP-V178-08: EXIT_REQUIRED — Salir · 0 COMPRAR", async ({ page }) => {
    setE2eMockPositionStage("exit_required");
    const listDoc = mercadoWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    await assertPovOperatingStage(page, focus, {
      operatingState: "EXIT_REQUIRED",
      actionText: /Salir/i,
    });
  });
});
