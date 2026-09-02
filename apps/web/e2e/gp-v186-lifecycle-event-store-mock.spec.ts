/**
 * GP-V186 — Lifecycle Event Store mock integrity (ENTRY cash · eventId conflict).
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v186
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
  accountLifecycleFills,
  lifecycleInstrumentSlice,
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
  type LifecycleStoreEventKind,
} from "./integration";

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
  }
}

test.describe("GP-V186 — Lifecycle event store mock integrity", () => {
  test.skip(!e2eEnabled(), E2E_SKIP_REASON);
  const slice = lifecycleInstrumentSlice();
  const chartDoc = mercadoWorkspaceDocument({
    instrumentId: slice.instrumentId,
    symbol: slice.symbol,
  });

  test.beforeEach(async ({ page }) => {
    resetE2eMockRuntimeFlags();
    setMercadoMockWorkspaceDocument(chartDoc);
    await installStatefulLifecycleMocks(page);
    await seedMercadoBrowserState(page, {
      accountId: E2E_ACCOUNT_ID,
      instrumentId: slice.instrumentId,
    });
    await page.goto("/mercado");
  });

  test("GP-V186-01: OPEN cash 99000 · eventId conflict 409 · log intacto", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    await emitKinds(page, ["POSITION_OPENED"]);
    expect(getE2eMockLifecycleEvents()).toHaveLength(1);
    const afterOpen = accountLifecycleFills(getE2eMockLifecycleEvents());
    expect(afterOpen.cash).toBe(99_000);
    expect(afterOpen.remaining).toBe(10);

    const portfolio = await page.evaluate(async () => {
      const res = await fetch("/api/portfolio");
      return res.json();
    });
    expect(portfolio.data?.portfolio?.cash).toBe(99_000);

    const first = await emitLifecycle(page, {
      kind: "T1_EXECUTED",
      eventId: "evt-123",
      quantity: 5,
      price: 105,
    });
    expect(first.ok).toBe(true);
    expect(getE2eMockLifecycleEvents()).toHaveLength(2);

    const conflict = await emitLifecycle(page, {
      kind: "T1_EXECUTED",
      eventId: "evt-123",
      quantity: 8,
      price: 130,
    });
    expect(conflict.status).toBe(409);
    expect(conflict.body.error?.code).toBe("event_id_conflict");
    expect(getE2eMockLifecycleEvents()).toHaveLength(2);

    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});
