/**
 * GP-V179 — Stateful Position Lifecycle Certification (mock API).
 *
 * Un test: CANDIDATO → ENTRY dryRun → STALE → RECOVERY → OPEN → T1_READY
 * → T1_EXECUTED → TRAILING → RECON DRIFT → CLEAN → EXIT_REQUIRED → CLOSED.
 * Identidad AAPL congelada. 0 COMPRAR. No fills ledger.
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v179
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installStatefulLifecycleMocks,
  resetE2eMockRuntimeFlags,
  setE2eMockDeskMode,
  setE2eMockPositionStage,
  setE2eMockReconStatus,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  E2E_INSTRUMENT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_LIFECYCLE_POSITION_ID,
  E2E_SYMBOL,
  assertClosedLineage,
  assertClosedPositionTruth,
  assertEntryCandidateTruth,
  assertLifecycleFinancialInvariants,
  assertPositionCertification,
  buildLifecycleSnapshot,
  expandDailyDeskBucketIfCollapsed,
  lifecycleInstrumentSlice,
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
  seedPaperDayBrowserState,
  type E2eGoldenPositionStage,
} from "./integration";

const DENY_AAPL = "daily-desk-item-auto-deny-inst-aapl";

async function assertNoComprar(page: Page): Promise<void> {
  await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(0);
}

async function focusAapl(page: Page): Promise<void> {
  const row = page.getByTestId(`list-instrument-open-${E2E_SYMBOL}`);
  await expect(row).toBeVisible({ timeout: 20_000 });
  await row.click();
}

async function reloadMercadoStage(
  page: Page,
  stage: E2eGoldenPositionStage,
  workspaceDocument: ReturnType<typeof mercadoWorkspaceDocument>,
): Promise<void> {
  setE2eMockPositionStage(stage);
  await seedMercadoBrowserState(page, {
    workspaceDocument,
    operativaOpen: true,
  });
  await page.reload();
  await focusAapl(page);
}

test.describe("GP-V179 — Stateful position lifecycle mock", () => {
  const slice = lifecycleInstrumentSlice();
  const chartDoc = mercadoWorkspaceDocument({
    instrumentId: slice.instrumentId,
    symbol: slice.symbol,
    name: "E2E Lifecycle AAPL",
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installStatefulLifecycleMocks(page);
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
    resetE2eMockRuntimeFlags();
  });

  test("GP-V179-01: AAPL candidato→CLOSED conserva identidad y 0 COMPRAR", async ({
    page,
  }) => {
    test.setTimeout(120_000);

    setMercadoMockWorkspaceDocument(chartDoc);
    await seedPaperDayBrowserState(page, { workspaceDocument: chartDoc });
    await seedMercadoBrowserState(page, {
      workspaceDocument: chartDoc,
      operativaOpen: true,
    });

    // CANDIDATO — Mercado entry surface, sin positionId
    await page.goto("/trading");
    await focusAapl(page);
    await assertEntryCandidateTruth(page, {
      instrumentId: E2E_INSTRUMENT_ID,
      symbol: E2E_SYMBOL,
    });

    // ENTRY dryRun — Hoy AUTO armado · ejecución off
    await page.goto("/mesa");
    const reportPromise = page.waitForResponse(
      (res) => res.ok() && res.url().includes("/paper-desk/daily-report"),
    );
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    const reportRes = await reportPromise;
    const reportJson = (await reportRes.json()) as {
      data?: { autoDesk?: { dryRun?: boolean; paperDExecute?: boolean } };
    };
    expect(reportJson.data?.autoDesk?.dryRun).toBe(true);
    expect(reportJson.data?.autoDesk?.paperDExecute).toBe(false);
    await expect(
      page.getByText(/Plan armado \(AUTO\)|AUTO armado · ejecución off/i),
    ).toBeVisible();
    await expect(
      page.getByTestId("daily-desk-bucket-oportunidades"),
    ).toHaveAttribute("data-count", "1");
    await expect(page.getByTestId(`daily-desk-cta-${E2E_SYMBOL}`)).toHaveText(
      /Preparar operación/i,
    );
    await assertNoComprar(page);

    // STALE — deny BLOCKED + ENTRY_STALE_DATA
    setE2eMockDeskMode("lifecycle_stale");
    await page.reload();
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expandDailyDeskBucketIfCollapsed(page, "no_operar");
    const deny = page.getByTestId(DENY_AAPL);
    await expect(deny).toBeVisible();
    await expect(deny).toHaveAttribute("data-attention", "BLOCKED");
    await expect(deny).toHaveAttribute("data-reason-code", "ENTRY_STALE_DATA");
    await assertNoComprar(page);

    // RECOVERY — deny ausente (no solo oportunidades=1)
    setE2eMockDeskMode("lifecycle");
    await page.reload();
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId(DENY_AAPL)).toHaveCount(0);
    await expect(
      page.locator("[data-reason-code='ENTRY_STALE_DATA']"),
    ).toHaveCount(0);
    await expect(
      page.getByTestId("daily-desk-bucket-oportunidades"),
    ).toHaveAttribute("data-count", "1");
    await assertNoComprar(page);

    // POSITION OPEN — IDs congelados
    setE2eMockPositionStage("open");
    await seedMercadoBrowserState(page, {
      workspaceDocument: chartDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await focusAapl(page);
    await assertPositionCertification(page, slice, {
      operatingState: "PROTECTED",
      actionText: /Mantener/i,
      remainingQuantity: 10,
      unrealizedR: 0.4,
    });

    await reloadMercadoStage(page, "t1_ready", chartDoc);
    await assertPositionCertification(page, slice, {
      operatingState: "T1_READY",
      actionText: /Reducir/i,
      remainingQuantity: 10,
      unrealizedR: 0.6,
    });

    await reloadMercadoStage(page, "t1_executed", chartDoc);
    await assertPositionCertification(page, slice, {
      operatingState: "T1_EXECUTED",
      actionText: /Mantener/i,
      remainingQuantity: 5,
      unrealizedR: 0.8,
    });

    await reloadMercadoStage(page, "trailing", chartDoc);
    await assertPositionCertification(page, slice, {
      operatingState: "TRAILING",
      actionText: /Proteger/i,
      remainingQuantity: 5,
      unrealizedR: 0.6,
    });

    // RECON DRIFT → CLEAN
    setE2eMockReconStatus("drift");
    await page.reload();
    await focusAapl(page);
    await expect(page.getByTestId("operativa-cockpit")).toHaveAttribute(
      "data-position-id",
      slice.positionId,
    );
    await expect(page.getByTestId("operativa-cockpit-recon")).toHaveAttribute(
      "data-recon",
      "CRITICAL",
    );
    await expect(
      page.getByTestId("operativa-cockpit-pov-action"),
    ).toContainText(/Revisar/i);
    await assertNoComprar(page);

    setE2eMockReconStatus("ok");
    await page.reload();
    await focusAapl(page);
    await assertPositionCertification(page, slice, {
      operatingState: "TRAILING",
      actionText: /Proteger/i,
      remainingQuantity: 5,
      unrealizedR: 0.6,
      expectRecon: "CLEAN",
    });

    await reloadMercadoStage(page, "exit_required", chartDoc);
    await assertPositionCertification(page, slice, {
      operatingState: "EXIT_REQUIRED",
      actionText: /Salir/i,
      remainingQuantity: 5,
      unrealizedR: 0.6,
    });

    // CLOSED — wire remaining 0 · sin star-card · Journal misma cadena
    setE2eMockPositionStage("closed");
    const portfolioPromise = page.waitForResponse(
      (res) => res.ok() && res.url().includes("/api/portfolio"),
    );
    await page.reload();
    const portfolioJson = (await (await portfolioPromise).json()) as {
      data?: {
        portfolio?: { totalEquity?: number };
        positions?: Array<{
          id: string;
          quantity: number;
          avgCost?: number;
          lastPrice?: number;
          marketValue?: number;
          unrealizedPnl?: number;
          unrealizedPnlPct?: number;
          operational?: {
            remainingQuantity?: number;
            unrealizedR?: number;
            operationalView?: {
              positionId?: string;
              decisionId?: string | null;
              remainingQuantity?: number;
              operatingState?: string;
              quantity?: number;
              t1?: { status?: string } | null;
              t2?: { status?: string } | null;
              stopHistory?: unknown[];
              events?: Array<{ kind?: string }>;
              levels?: { unrealizedR?: number };
            };
          };
        }>;
      };
    };
    const closed = portfolioJson.data?.positions?.find(
      (row) => row.id === E2E_LIFECYCLE_POSITION_ID,
    );
    expect(closed).toBeTruthy();
    expect(closed!.quantity).toBe(0);
    expect(
      closed!.operational?.operationalView?.remainingQuantity ??
        closed!.operational?.remainingQuantity,
    ).toBe(0);
    expect(closed!.operational?.operationalView?.operatingState).toBe("CLOSED");
    expect(closed!.operational?.operationalView?.positionId).toBe(
      slice.positionId,
    );
    expect(closed!.operational?.operationalView?.decisionId).toBe(
      E2E_LIFECYCLE_DECISION_ID,
    );
    assertClosedLineage(closed!.operational?.operationalView ?? {}, "trail");
    assertLifecycleFinancialInvariants({
      quantity: closed!.quantity,
      avgCost: closed!.avgCost ?? 100,
      lastPrice: closed!.lastPrice ?? 0,
      marketValue: closed!.marketValue ?? 0,
      unrealizedPnl: closed!.unrealizedPnl ?? 0,
      unrealizedPnlPct: closed!.unrealizedPnlPct ?? 0,
      operational: closed!.operational,
    });
    expect(portfolioJson.data?.portfolio?.totalEquity).toBe(
      buildLifecycleSnapshot({ stage: "closed", lineagePath: "trail" })
        .totalEquity,
    );

    await focusAapl(page);
    await assertClosedPositionTruth(page, {
      instrumentId: E2E_INSTRUMENT_ID,
      decisionId: E2E_LIFECYCLE_DECISION_ID,
    });
  });
});
