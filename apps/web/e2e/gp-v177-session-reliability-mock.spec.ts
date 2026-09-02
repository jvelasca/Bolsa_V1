/**
 * GP-V177 — Session Reliability / Operational Truth (mock API).
 *
 * Journey: A→B→C→A → refresh → stale → recovery → UNKNOWN → recon → clean.
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v177
 */
import { test, expect } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installSessionReliabilityMocks,
  resetE2eMockRuntimeFlags,
  setE2eMockDataFreshness,
  setE2eMockReconStatus,
  setE2eMockUnknownOrder,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  assertOperationalTruth,
  E2E_INSTRUMENT_ID,
  mercadoListFocusWorkspaceDocument,
  mercadoMultiInstrumentSlicesFromMock,
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
} from "./integration";

test.describe("GP-V177 — Session reliability mock", () => {
  const slices = mercadoMultiInstrumentSlicesFromMock();

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installSessionReliabilityMocks(page);
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
    resetE2eMockRuntimeFlags();
  });

  test("GP-V177-01: A→B→C→A identity + operational truth", async ({ page }) => {
    expect(slices.length).toBeGreaterThanOrEqual(3);
    const [a, b, c] = slices;
    const listDoc = mercadoListFocusWorkspaceDocument({
      instrumentId: a!.instrumentId,
      symbol: a!.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");

    for (const slice of [a!, b!, c!, a!]) {
      const listRow = page.getByTestId(`list-instrument-open-${slice.symbol}`);
      await expect(listRow).toBeVisible({ timeout: 20_000 });
      await expect(listRow).toHaveAttribute(
        "data-instrument-id",
        slice.instrumentId,
      );
      await listRow.click();
      await assertOperationalTruth(page, slice, {
        expectRecon: "CLEAN",
        expectFreshness: "current",
      });
    }
  });

  test("GP-V177-02: refresh preserves focus truth (B)", async ({ page }) => {
    const [a, b] = slices;
    const listDoc = mercadoListFocusWorkspaceDocument({
      instrumentId: a!.instrumentId,
      symbol: a!.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${b!.symbol}`).click();
    await assertOperationalTruth(page, b!, { expectRecon: "CLEAN" });

    const focusedDoc = mercadoWorkspaceDocument({
      instrumentId: b!.instrumentId,
      symbol: b!.symbol,
    });
    setMercadoMockWorkspaceDocument(focusedDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: focusedDoc,
      operativaOpen: true,
    });
    await page.reload();
    await assertOperationalTruth(page, b!, {
      expectRecon: "CLEAN",
      expectFreshness: "current",
    });
    await expect(page.getByTestId("operativa-cockpit")).not.toHaveAttribute(
      "data-instrument-id",
      a!.instrumentId,
    );
  });

  test("GP-V177-03: stale data-status → 0 COMPRAR · IDs intactos", async ({
    page,
  }) => {
    const focus = slices[0]!;
    const listDoc = mercadoListFocusWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    setE2eMockDataFreshness("stale");
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    await assertOperationalTruth(page, focus, {
      expectFreshness: "stale",
      expectRecon: "CLEAN",
    });
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V177-04: recovery current sin inventar COMPRAR", async ({
    page,
  }) => {
    const focus = slices[0]!;
    const listDoc = mercadoListFocusWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    setE2eMockDataFreshness("stale");
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    await assertOperationalTruth(page, focus, { expectFreshness: "stale" });

    setE2eMockDataFreshness("current");
    const focusedDoc = mercadoWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(focusedDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: focusedDoc,
      operativaOpen: true,
    });
    await page.reload();
    await assertOperationalTruth(page, focus, {
      expectFreshness: "current",
      expectRecon: "CLEAN",
    });
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V177-05: UNKNOWN · no reenviar · 0 COMPRAR · IDs", async ({
    page,
  }) => {
    const focus =
      slices.find((s) => s.instrumentId === E2E_INSTRUMENT_ID) ?? slices[0]!;
    const listDoc = mercadoListFocusWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    setE2eMockUnknownOrder(true);
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: true,
    });
    const intentsPromise = page.waitForResponse(
      (res) => res.ok() && res.url().includes("/submit-intents"),
    );
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${focus.symbol}`).click();
    const intentsBody = (await (await intentsPromise).json()) as {
      data?: { total?: number; intents?: Array<{ orderId?: string }> };
    };
    expect(intentsBody.data?.total).toBe(1);
    expect(intentsBody.data?.intents?.[0]?.orderId).toBe("ord-unknown-001");

    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).toHaveAttribute(
      "data-instrument-id",
      focus.instrumentId,
    );
    await expect(cockpit).toHaveAttribute(
      "data-execution-lifecycle",
      "unknown",
    );
    const opsCta = page.getByTestId("operativa-cockpit-cta-operaciones");
    await expect(opsCta).toBeVisible();
    await expect(opsCta).toHaveAttribute("title", /Orden desconocida/i);
    await expect(opsCta).toHaveAttribute("title", /no reenviar/i);
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
    await expect(
      page.getByRole("button", { name: /reenviar|auto-heal|resend/i }),
    ).toHaveCount(0);
  });

  test("GP-V177-06: recon drift · REVISAR · 0 COMPRAR", async ({ page }) => {
    const focus = slices[1] ?? slices[0]!;
    const listDoc = mercadoListFocusWorkspaceDocument({
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
      page.getByTestId("operativa-cockpit-pov-state"),
    ).toHaveAttribute("data-state", "RECONCILIATION_DRIFT");
    await expect(
      page.getByTestId("operativa-cockpit-pov-action"),
    ).toContainText(/Revisar/i);
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V177-07: back to clean after drift", async ({ page }) => {
    const focus = slices[1] ?? slices[0]!;
    const listDoc = mercadoListFocusWorkspaceDocument({
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
    await expect(page.getByTestId("operativa-cockpit-recon")).toHaveAttribute(
      "data-recon",
      "CRITICAL",
      { timeout: 20_000 },
    );

    setE2eMockReconStatus("ok");
    const focusedDoc = mercadoWorkspaceDocument({
      instrumentId: focus.instrumentId,
      symbol: focus.symbol,
    });
    setMercadoMockWorkspaceDocument(focusedDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: focusedDoc,
      operativaOpen: true,
    });
    await page.reload();
    await assertOperationalTruth(page, focus, {
      expectRecon: "CLEAN",
      expectFreshness: "current",
    });
    await expect(
      page.getByTestId("operativa-cockpit-pov-state"),
    ).not.toHaveAttribute("data-state", "RECONCILIATION_DRIFT");
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});
