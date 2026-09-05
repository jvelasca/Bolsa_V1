/**
 * GP-V175 — Chaos & stale → no-execute (mock API).
 * V1.76 — aserciones de causa (no apariencia compatible).
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v175
 */
import { test, expect, type Page, type Response } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installHoyStaleNoExecuteMocks,
  installUnknownOrderMocks,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  E2E_ENTRY_ONLY_INSTRUMENT,
  E2E_INSTRUMENT_ID,
  E2E_SYMBOL,
  expandDailyDeskBucketIfCollapsed,
  mercadoEntryPositionWorkspaceDocument,
  mercadoListFocusWorkspaceDocument,
  paperAutonomousDaySlice,
  seedPaperDayBrowserState,
  seedStaleNoExecuteBrowserState,
} from "./integration";

async function jsonBody(res: Response): Promise<Record<string, unknown>> {
  return (await res.json()) as Record<string, unknown>;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

test.describe("GP-V175 — stale deny mock", () => {
  const slice = paperAutonomousDaySlice();
  const listDoc = mercadoListFocusWorkspaceDocument({
    instrumentId: slice.instrumentId,
    symbol: slice.symbol,
    name: "E2E Stale No-Execute",
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    setMercadoMockWorkspaceDocument(listDoc);
    await installHoyStaleNoExecuteMocks(page);
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
  });

  test("GP-V175-01: Hoy ENTRY_STALE_DATA — BLOCKED · 0 COMPRAR · no AUTO feliz", async ({
    page,
  }) => {
    await seedStaleNoExecuteBrowserState(page, { workspaceDocument: listDoc });
    const reportPromise = page.waitForResponse(
      (res) => res.ok() && res.url().includes("/paper-desk/daily-report"),
    );
    await page.goto("/mesa");
    const report = asRecord((await jsonBody(await reportPromise)).data);
    const autoDesk = asRecord(report.autoDesk);
    expect(autoDesk.dryRun).toBe(true);
    expect(autoDesk.paperDExecute).toBe(false);
    const entry = asRecord(autoDesk.entry);
    const candidates = Array.isArray(entry.candidates) ? entry.candidates : [];
    const first = asRecord(candidates[0]);
    expect(first.reasonCode).toBe("ENTRY_STALE_DATA");
    expect(String(first.humanMessage ?? "").trim().length).toBeGreaterThan(0);

    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expandDailyDeskBucketIfCollapsed(page, "no_operar");
    const deny = page.getByTestId("daily-desk-item-auto-deny-inst-msft");
    await expect(deny).toBeVisible();
    await expect(deny).toHaveAttribute("data-attention", "BLOCKED");
    await expect(deny).toHaveAttribute("data-reason-code", "ENTRY_STALE_DATA");
    await expect(deny).toContainText(/Datos obsoletos/i);
    await expect(deny).not.toContainText(/AUTO armado/i);
    await expect(page.getByTestId("daily-desk-cta-MSFT")).not.toHaveText(
      /AUTO armado|^COMPRAR$/i,
    );
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V175-02: stale deny named — not silent empty oportunidades", async ({
    page,
  }) => {
    await seedStaleNoExecuteBrowserState(page, { workspaceDocument: listDoc });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("daily-desk-bucket-no_operar")).toBeVisible();
    await expect(
      page.getByTestId("daily-desk-bucket-no_operar"),
    ).not.toHaveAttribute("data-count", "0");
    await expandDailyDeskBucketIfCollapsed(page, "no_operar");
    await expect(
      page.getByText(/Datos obsoletos|ENTRY_STALE_DATA|stale/i).first(),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V175-03: Mercado NVDA data-status stale — identity · no COMPRAR", async ({
    page,
  }) => {
    const dualDoc = mercadoEntryPositionWorkspaceDocument({
      positionInstrumentId: E2E_INSTRUMENT_ID,
      positionSymbol: E2E_SYMBOL,
      entryInstrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
      entrySymbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
      name: "E2E Stale Entry",
    });
    setMercadoMockWorkspaceDocument(dualDoc);
    await seedStaleNoExecuteBrowserState(page, { workspaceDocument: dualDoc });
    await page.goto("/trading");

    const nvdaStatus = page.waitForResponse((res) => {
      if (!res.ok()) return false;
      const url = res.url();
      return url.includes(
        `/instruments/${E2E_ENTRY_ONLY_INSTRUMENT.id}/data-status`,
      );
    });

    await page
      .locator(
        `[data-symbol="${E2E_ENTRY_ONLY_INSTRUMENT.symbol}"][data-instrument-id="${E2E_ENTRY_ONLY_INSTRUMENT.id}"]`,
      )
      .first()
      .click();

    const statusBody = asRecord((await jsonBody(await nvdaStatus)).data);
    expect(statusBody.instrumentId).toBe(E2E_ENTRY_ONLY_INSTRUMENT.id);
    expect(statusBody.freshnessStatus).toBe("stale");

    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).toHaveAttribute(
      "data-instrument-id",
      E2E_ENTRY_ONLY_INSTRUMENT.id,
    );
    await expect(page.getByTestId("chart-data-status")).toHaveAttribute(
      "data-instrument-id",
      E2E_ENTRY_ONLY_INSTRUMENT.id,
      { timeout: 20_000 },
    );
    await expect(page.getByTestId("entry-decision-surface")).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});

test.describe("GP-V175 — UNKNOWN order isolated", () => {
  const slice = paperAutonomousDaySlice();
  const listDoc = mercadoListFocusWorkspaceDocument({
    instrumentId: slice.instrumentId,
    symbol: slice.symbol,
    name: "E2E UNKNOWN Order",
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    setMercadoMockWorkspaceDocument(listDoc);
    await installUnknownOrderMocks(page);
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
  });

  test("GP-V175-04: UNKNOWN — REVISAR · no reenviar · no auto-heal · 1 intent", async ({
    page,
  }: {
    page: Page;
  }) => {
    await seedPaperDayBrowserState(page, { workspaceDocument: listDoc });
    const intentsPromise = page.waitForResponse(
      (res) => res.ok() && res.url().includes("/submit-intents"),
    );
    await page.goto("/trading");
    const intentsBody = asRecord((await jsonBody(await intentsPromise)).data);
    const intents = Array.isArray(intentsBody.intents)
      ? intentsBody.intents
      : [];
    expect(intentsBody.total).toBe(1);
    expect(intents).toHaveLength(1);
    expect(asRecord(intents[0]).orderId).toBe("ord-unknown-001");

    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).toHaveAttribute(
      "data-instrument-id",
      E2E_INSTRUMENT_ID,
    );
    await expect(cockpit).toHaveAttribute(
      "data-execution-lifecycle",
      "unknown",
    );

    const opsCta = page.getByTestId("operativa-cockpit-cta-operaciones");
    await expect(opsCta).toBeVisible();
    await expect(opsCta).toHaveText(/Ver operaciones/i);
    await expect(opsCta).toHaveAttribute("title", /Orden desconocida/i);
    await expect(opsCta).toHaveAttribute("title", /no reenviar/i);

    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
    await expect(
      page.getByRole("button", { name: /reenviar|auto-heal|resend/i }),
    ).toHaveCount(0);
    await expect(page.getByTestId("mesa-incident-banner")).toHaveCount(0);
  });
});
