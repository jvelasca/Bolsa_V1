/**
 * GP-V183 — Lifecycle Snapshot Truth (mock API).
 *
 * GP-V183-01 trail: OPEN → T1 → TRAIL → EXIT_REQUIRED → CLOSED
 *   lineage monotónica · invariantes financieras · equity portfolio === summary.
 * GP-V183-02 T2: T1_EXECUTED → T2_EXECUTED → CLOSED (T2 sobrevive).
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v183
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
  E2E_ACCOUNT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_LIFECYCLE_POSITION_ID,
  E2E_SYMBOL,
  assertClosedLineage,
  assertLifecycleFinancialInvariants,
  assertMonotonicClosedLineage,
  assertPositionCertification,
  buildLifecycleSnapshot,
  lifecycleInstrumentSlice,
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
  type E2eGoldenPositionStage,
  type LifecycleFinancialPosition,
  type LifecycleLineagePath,
} from "./integration";

type PortfolioWire = {
  data?: {
    portfolio?: { cash?: number; totalEquity?: number };
    positions?: Array<
      LifecycleFinancialPosition & {
        id: string;
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
      }
    >;
  };
};

type SummaryWire = {
  data?: { cash?: number; totalEquity?: number; openPositions?: number };
};

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

type DeskWire = {
  data?: { summary?: { cash?: number; totalEquity?: number } };
};

async function readLifecycleSurfaces(page: Page): Promise<{
  portfolio: PortfolioWire;
  summary: SummaryWire;
  desk: DeskWire;
}> {
  const portfolio = (await page.evaluate(async () => {
    const res = await fetch("/api/portfolio");
    return res.json();
  })) as PortfolioWire;
  const summary = (await page.evaluate(async (accountId) => {
    const res = await fetch(`/api/accounts/${accountId}/summary`);
    return res.json();
  }, E2E_ACCOUNT_ID)) as SummaryWire;
  const desk = (await page.evaluate(async () => {
    const res = await fetch("/api/paper-desk/daily-report");
    return res.json();
  })) as DeskWire;
  return { portfolio, summary, desk };
}

function lifecyclePosition(wire: PortfolioWire) {
  return wire.data?.positions?.find(
    (row) => row.id === E2E_LIFECYCLE_POSITION_ID,
  );
}

function assertSnapshotBattery(
  stages: E2eGoldenPositionStage[],
  path: LifecycleLineagePath,
): void {
  for (const stage of stages) {
    const snap = buildLifecycleSnapshot({ stage, lineagePath: path });
    if (snap.position) {
      assertLifecycleFinancialInvariants(snap.position);
      const view = snap.position.operational.operationalView as {
        t1?: { status?: string } | null;
        t2?: { status?: string } | null;
        stopHistory?: unknown[];
        events?: Array<{ kind?: string }>;
        remainingQuantity?: number;
        operatingState?: string;
      };
      if (stage === "exit_required") {
        assertMonotonicClosedLineage(view, path);
      }
      if (stage === "closed") {
        assertClosedLineage(view, path);
      }
    }
    if (stage !== "candidate") {
      expect(snap.position).toBeTruthy();
    }
  }
}

test.describe("GP-V183 — Lifecycle snapshot truth mock", () => {
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

  test("GP-V183-01: trail OPEN→CLOSED lineage + invariantes + equity única", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    assertSnapshotBattery(
      [
        "open",
        "t1_ready",
        "t1_executed",
        "trailing",
        "exit_required",
        "closed",
      ],
      "trail",
    );

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

    await reloadMercadoStage(page, "exit_required", chartDoc);
    await assertPositionCertification(page, slice, {
      operatingState: "EXIT_REQUIRED",
      actionText: /Salir/i,
      remainingQuantity: 5,
      unrealizedR: 0.6,
    });

    setE2eMockPositionStage("closed");
    await page.reload();
    const { portfolio, summary, desk } = await readLifecycleSurfaces(page);
    const closed = lifecyclePosition(portfolio);
    expect(closed).toBeTruthy();
    assertLifecycleFinancialInvariants(closed!);
    assertClosedLineage(closed!.operational?.operationalView ?? {}, "trail");
    const expectedEquity = buildLifecycleSnapshot({
      stage: "closed",
      lineagePath: "trail",
    }).totalEquity;
    expect(portfolio.data?.portfolio?.totalEquity).toBe(expectedEquity);
    expect(summary.data?.totalEquity).toBe(expectedEquity);
    expect(desk.data?.summary?.totalEquity).toBe(expectedEquity);
    expect(portfolio.data?.portfolio?.cash).toBe(summary.data?.cash);
    expect(closed!.operational?.operationalView?.positionId).toBe(
      slice.positionId,
    );
    expect(closed!.operational?.operationalView?.decisionId).toBe(
      E2E_LIFECYCLE_DECISION_ID,
    );
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V183-02: T2 path CLOSED conserva T1+T2", async ({ page }) => {
    test.setTimeout(90_000);
    assertSnapshotBattery(
      ["open", "t1_executed", "t2_ready", "t2_executed", "closed"],
      "t2",
    );

    setMercadoMockWorkspaceDocument(chartDoc);
    setE2eMockPositionStage("open");
    await seedMercadoBrowserState(page, {
      workspaceDocument: chartDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
    await focusAapl(page);

    await reloadMercadoStage(page, "t1_executed", chartDoc);
    await reloadMercadoStage(page, "t2_executed", chartDoc);
    await assertPositionCertification(page, slice, {
      operatingState: "T2_EXECUTED",
      actionText: /Mantener/i,
      remainingQuantity: 2,
      unrealizedR: 0.4,
    });

    setE2eMockPositionStage("closed");
    await page.reload();
    const { portfolio, summary, desk } = await readLifecycleSurfaces(page);
    const closed = lifecyclePosition(portfolio);
    expect(closed).toBeTruthy();
    assertLifecycleFinancialInvariants(closed!);
    assertClosedLineage(closed!.operational?.operationalView ?? {}, "t2");
    assertMonotonicClosedLineage(
      closed!.operational?.operationalView ?? {},
      "t2",
    );
    const expectedEquity = buildLifecycleSnapshot({
      stage: "closed",
      lineagePath: "t2",
    }).totalEquity;
    expect(portfolio.data?.portfolio?.totalEquity).toBe(expectedEquity);
    expect(summary.data?.totalEquity).toBe(expectedEquity);
    expect(desk.data?.summary?.totalEquity).toBe(expectedEquity);
    expect(closed!.operational?.operationalView?.decisionId).toBe(
      E2E_LIFECYCLE_DECISION_ID,
    );
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});
