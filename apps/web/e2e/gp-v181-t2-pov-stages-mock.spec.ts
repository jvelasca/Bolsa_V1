/**
 * GP-V181 — T2 POV Stages Certification (mock API).
 *
 * Post-T1 arc: OPEN → T1_READY → T1_EXECUTED → T2_READY → T2_EXECUTED → CLOSED.
 * MONITOR→Mantener intentional (no desk "GESTIONAR T2"). 0 COMPRAR. No fills ledger.
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v181
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installStatefulLifecycleMocks,
  resetE2eMockRuntimeFlags,
  setE2eMockPositionStage,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  E2E_INSTRUMENT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_LIFECYCLE_POSITION_ID,
  E2E_SYMBOL,
  assertClosedPositionTruth,
  assertPositionCertification,
  lifecycleInstrumentSlice,
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
  type E2eGoldenPositionStage,
} from "./integration";

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

test.describe("GP-V181 — T2 POV stages mock", () => {
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

  test("GP-V181-01: T1→T2_READY→T2_EXECUTED→CLOSED · MONITOR · 0 COMPRAR", async ({
    page,
  }) => {
    test.setTimeout(90_000);

    setMercadoMockWorkspaceDocument(chartDoc);
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

    // T2_READY — primaryAction MONITOR → CTA Mantener (no COMPRAR / no GESTIONAR T2)
    await reloadMercadoStage(page, "t2_ready", chartDoc);
    await assertPositionCertification(page, slice, {
      operatingState: "T2_READY",
      actionText: /Mantener/i,
      remainingQuantity: 5,
      unrealizedR: 1.0,
    });
    await expect(page.getByTestId("operativa-cockpit-pov-state")).toContainText(
      /T2|MONITOR/i,
    );
    await assertNoComprar(page);

    await reloadMercadoStage(page, "t2_executed", chartDoc);
    await assertPositionCertification(page, slice, {
      operatingState: "T2_EXECUTED",
      actionText: /Mantener/i,
      remainingQuantity: 2,
      unrealizedR: 1.2,
    });
    await assertNoComprar(page);

    // CLOSED — misma identidad; representación, no ledger
    setE2eMockPositionStage("closed");
    const portfolioPromise = page.waitForResponse(
      (res) => res.ok() && res.url().includes("/api/portfolio"),
    );
    await page.reload();
    const portfolioJson = (await (await portfolioPromise).json()) as {
      data?: {
        positions?: Array<{
          id: string;
          quantity: number;
          operational?: {
            operationalView?: {
              positionId?: string;
              decisionId?: string | null;
              remainingQuantity?: number;
              operatingState?: string;
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
    expect(closed!.operational?.operationalView?.remainingQuantity).toBe(0);
    expect(closed!.operational?.operationalView?.operatingState).toBe("CLOSED");
    expect(closed!.operational?.operationalView?.positionId).toBe(
      slice.positionId,
    );
    expect(closed!.operational?.operationalView?.decisionId).toBe(
      E2E_LIFECYCLE_DECISION_ID,
    );

    await focusAapl(page);
    await assertClosedPositionTruth(page, {
      instrumentId: E2E_INSTRUMENT_ID,
      decisionId: E2E_LIFECYCLE_DECISION_ID,
    });
    await assertNoComprar(page);
  });
});
