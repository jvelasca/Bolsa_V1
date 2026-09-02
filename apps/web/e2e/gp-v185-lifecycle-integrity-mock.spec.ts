/**
 * GP-V185 — Lifecycle Integrity (FSM reject · idempotency · realized PnL).
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v185
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
  E2E_LIFECYCLE_POSITION_ID,
  accountLifecycleFills,
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
          realizedPnl?: number;
          totalPnl?: number;
          unrealizedR?: number;
          operationalView?: {
            remainingQuantity?: number;
            operatingState?: string;
            t1?: { status?: string } | null;
            t2?: { status?: string } | null;
            stopHistory?: unknown[];
            events?: Array<{ kind?: string }>;
          };
        };
      }
    >;
  };
};

type SummaryWire = {
  data?: { cash?: number; totalEquity?: number };
};

type DeskWire = {
  data?: { summary?: { cash?: number; totalEquity?: number } };
};

async function emitLifecycle(
  page: Page,
  body: Record<string, unknown>,
): Promise<{
  ok: boolean;
  status: number;
  body: {
    data?: { ok?: boolean; idempotent?: boolean; count?: number };
    error?: { code?: string; message?: string };
  };
}> {
  return page.evaluate(async (payload) => {
    const response = await fetch("/api/e2e/lifecycle/events", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    return {
      ok: response.ok,
      status: response.status,
      body: await response.json(),
    };
  }, body);
}

async function emitKinds(
  page: Page,
  kinds: LifecycleStoreEventKind[],
): Promise<void> {
  for (const kind of kinds) {
    const res = await emitLifecycle(page, { kind });
    expect(res.ok, `emit ${kind} status=${res.status}`).toBe(true);
    expect(res.body?.data?.ok).toBe(true);
  }
}

async function readSurfaces(page: Page) {
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

test.describe("GP-V185 — Lifecycle integrity & financial event model", () => {
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

  test("GP-V185-01: illegal POST → 409 · log unchanged", async ({ page }) => {
    test.setTimeout(90_000);
    await emitKinds(page, ["POSITION_OPENED"]);
    expect(getE2eMockLifecycleEvents()).toHaveLength(1);

    const before = getE2eMockLifecycleEvents().length;
    const illegal = await emitLifecycle(page, { kind: "T2_EXECUTED" });
    expect(illegal.status).toBe(409);
    expect(illegal.body.error?.code).toBe("illegal_transition");
    expect(getE2eMockLifecycleEvents()).toHaveLength(before);

    const timeBad = await emitLifecycle(page, {
      kind: "T1_EXECUTED",
      at: "2026-09-02T09:00:00.000Z",
    });
    expect(timeBad.status).toBe(409);
    expect(timeBad.body.error?.code).toBe("time_regression");
    expect(getE2eMockLifecycleEvents()).toHaveLength(before);

    const foreign = await emitLifecycle(page, {
      kind: "T1_EXECUTED",
      positionId: "pos-foreign",
    });
    expect(foreign.status).toBe(409);
    expect(foreign.body.error?.code).toBe("position_mismatch");
    expect(getE2eMockLifecycleEvents()).toHaveLength(before);
  });

  test("GP-V185-02: idempotent eventId · trail PnL equity única", async ({
    page,
  }) => {
    test.setTimeout(90_000);

    await emitKinds(page, [
      "POSITION_OPENED",
      "T1_TRIGGERED",
      "T1_EXECUTED",
      "TRAIL_APPLIED",
      "EXIT_REQUIRED",
    ]);

    const closeBody = {
      kind: "POSITION_CLOSED",
      eventId: "evt-close-once",
    };
    const first = await emitLifecycle(page, closeBody);
    expect(first.ok).toBe(true);
    expect(first.body.data?.idempotent).toBe(false);
    const count = first.body.data?.count;
    expect(count).toBe(6);

    const second = await emitLifecycle(page, closeBody);
    expect(second.ok).toBe(true);
    expect(second.body.data?.idempotent).toBe(true);
    expect(second.body.data?.count).toBe(count);
    expect(getE2eMockLifecycleEvents()).toHaveLength(6);

    const log = getE2eMockLifecycleEvents();
    const acct = accountLifecycleFills(log);
    const { portfolio, summary, desk } = await readSurfaces(page);
    const closed = portfolio.data?.positions?.find(
      (row) => row.id === E2E_LIFECYCLE_POSITION_ID,
    );
    expect(closed).toBeTruthy();
    assertLifecycleFinancialInvariants(closed!);
    assertClosedLineage(closed!.operational?.operationalView ?? {}, "trail");
    assertWireEventsMatchLog(closed!.operational?.operationalView?.events, log);

    expect(closed!.operational?.realizedPnl).toBe(acct.realizedPnl);
    expect(closed!.operational?.totalPnl).toBe(acct.totalPnl);
    expect(acct.realizedPnl).toBe(55);

    const expectedEquity = buildLifecycleSnapshotFromEvents(log).totalEquity;
    expect(expectedEquity).toBe(acct.totalEquity);
    expect(portfolio.data?.portfolio?.totalEquity).toBe(expectedEquity);
    expect(summary.data?.totalEquity).toBe(expectedEquity);
    expect(desk.data?.summary?.totalEquity).toBe(expectedEquity);
    expect(portfolio.data?.portfolio?.cash).toBe(acct.cash);
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V185-03: duplicate fillId rejected after T1", async ({ page }) => {
    test.setTimeout(60_000);
    await emitKinds(page, ["POSITION_OPENED", "T1_EXECUTED", "T2_TRIGGERED"]);
    const before = getE2eMockLifecycleEvents().length;
    const dup = await emitLifecycle(page, {
      kind: "T2_EXECUTED",
      fillId: "fill-mock-t1",
      eventId: "evt-dup-fill",
    });
    expect(dup.status).toBe(409);
    expect(dup.body.error?.code).toBe("duplicate_fill_id");
    expect(getE2eMockLifecycleEvents()).toHaveLength(before);
  });
});
