/**
 * GP-V184 — Lifecycle Event-Driven Mock (POST emit → persist → GET).
 *
 * GP-V184-01 trail: OPEN→T1→TRAIL→EXIT→CLOSED vía POST /api/e2e/lifecycle/events
 * GP-V184-02 T2: T1→T2→CLOSED · wire events ⊆ log persistido
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v184
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  getE2eMockLifecycleEvents,
  installStatefulLifecycleMocks,
  resetE2eMockRuntimeFlags,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  E2E_ACCOUNT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_LIFECYCLE_POSITION_ID,
  assertClosedLineage,
  assertLifecycleFinancialInvariants,
  assertWireEventsMatchLog,
  buildLifecycleSnapshotFromEvents,
  lifecycleInstrumentSlice,
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
  type LifecycleFinancialPosition,
  type LifecycleStoreEventKind,
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

type DeskWire = {
  data?: { summary?: { cash?: number; totalEquity?: number } };
};

async function emitLifecycle(
  page: Page,
  kind: LifecycleStoreEventKind,
): Promise<void> {
  const res = await page.evaluate(async (eventKind) => {
    const response = await fetch("/api/e2e/lifecycle/events", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ kind: eventKind }),
    });
    return {
      ok: response.ok,
      status: response.status,
      body: await response.json(),
    };
  }, kind);
  expect(res.ok, `emit ${kind} status=${res.status}`).toBe(true);
  expect(res.body?.data?.ok).toBe(true);
  expect(res.body?.data?.event?.kind).toBe(kind);
}

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

test.describe("GP-V184 — Lifecycle event-driven mock", () => {
  const slice = lifecycleInstrumentSlice();
  const chartDoc = mercadoWorkspaceDocument({
    instrumentId: slice.instrumentId,
    symbol: slice.symbol,
    name: "E2E Lifecycle AAPL",
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installStatefulLifecycleMocks(page);
    setMercadoMockWorkspaceDocument(chartDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: chartDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
    resetE2eMockRuntimeFlags();
  });

  test("GP-V184-01: trail POST emit→GET lineage + equity única", async ({
    page,
  }) => {
    test.setTimeout(90_000);

    for (const kind of [
      "POSITION_OPENED",
      "T1_TRIGGERED",
      "T1_EXECUTED",
      "TRAIL_APPLIED",
      "EXIT_REQUIRED",
      "POSITION_CLOSED",
    ] as const) {
      await emitLifecycle(page, kind);
    }

    const log = getE2eMockLifecycleEvents();
    expect(log.map((ev) => ev.kind)).toEqual([
      "POSITION_OPENED",
      "T1_TRIGGERED",
      "T1_EXECUTED",
      "TRAIL_APPLIED",
      "EXIT_REQUIRED",
      "POSITION_CLOSED",
    ]);

    const { portfolio, summary, desk } = await readLifecycleSurfaces(page);
    const closed = lifecyclePosition(portfolio);
    expect(closed).toBeTruthy();
    assertLifecycleFinancialInvariants(closed!);
    assertClosedLineage(closed!.operational?.operationalView ?? {}, "trail");
    assertWireEventsMatchLog(closed!.operational?.operationalView?.events, log);

    const expectedEquity = buildLifecycleSnapshotFromEvents(log).totalEquity;
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

  test("GP-V184-02: T2 POST emit→CLOSED wire events = log", async ({
    page,
  }) => {
    test.setTimeout(90_000);

    for (const kind of [
      "POSITION_OPENED",
      "T1_EXECUTED",
      "T2_TRIGGERED",
      "T2_EXECUTED",
      "POSITION_CLOSED",
    ] as const) {
      await emitLifecycle(page, kind);
    }

    const log = getE2eMockLifecycleEvents();
    const { portfolio, summary, desk } = await readLifecycleSurfaces(page);
    const closed = lifecyclePosition(portfolio);
    expect(closed).toBeTruthy();
    assertLifecycleFinancialInvariants(closed!);
    assertClosedLineage(closed!.operational?.operationalView ?? {}, "t2");
    assertWireEventsMatchLog(closed!.operational?.operationalView?.events, log);
    expect(closed!.operational?.operationalView?.t2?.status).toBe("executed");

    const expectedEquity = buildLifecycleSnapshotFromEvents(log).totalEquity;
    expect(portfolio.data?.portfolio?.totalEquity).toBe(expectedEquity);
    expect(summary.data?.totalEquity).toBe(expectedEquity);
    expect(desk.data?.summary?.totalEquity).toBe(expectedEquity);
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});
