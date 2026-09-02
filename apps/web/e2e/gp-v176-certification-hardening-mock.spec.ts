/**
 * GP-V176 — Certification Hardening (mock API).
 *
 * Reason causality: stale → ENTRY_STALE_DATA → BLOCKED → 0 COMPRAR.
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v176
 */
import { test, expect } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installHoyStaleNoExecuteMocks,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  mercadoListFocusWorkspaceDocument,
  paperAutonomousDaySlice,
  seedStaleNoExecuteBrowserState,
} from "./integration";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

test.describe("GP-V176 — Certification Hardening mock", () => {
  const slice = paperAutonomousDaySlice();
  const listDoc = mercadoListFocusWorkspaceDocument({
    instrumentId: slice.instrumentId,
    symbol: slice.symbol,
    name: "E2E Reason Causality",
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    setMercadoMockWorkspaceDocument(listDoc);
    await installHoyStaleNoExecuteMocks(page);
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
  });

  test("GP-V176-01: freshness stale → ENTRY_STALE_DATA → BLOCKED → 0 COMPRAR", async ({
    page,
  }) => {
    await seedStaleNoExecuteBrowserState(page, { workspaceDocument: listDoc });
    const reportPromise = page.waitForResponse(
      (res) => res.ok() && res.url().includes("/paper-desk/daily-report"),
    );
    await page.goto("/mesa");
    const reportRes = await reportPromise;
    const report = asRecord(
      ((await reportRes.json()) as Record<string, unknown>).data,
    );
    const autoDesk = asRecord(report.autoDesk);
    expect(autoDesk.dryRun).toBe(true);
    expect(autoDesk.paperDExecute).toBe(false);

    const entry = asRecord(autoDesk.entry);
    const candidates = Array.isArray(entry.candidates) ? entry.candidates : [];
    expect(candidates.length).toBeGreaterThan(0);
    const first = asRecord(candidates[0]);
    expect(first.freshness).toBe("stale");
    expect(first.reasonCode).toBe("ENTRY_STALE_DATA");
    expect(String(first.humanMessage ?? "").trim().length).toBeGreaterThan(0);

    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    const deny = page.getByTestId("daily-desk-item-auto-deny-inst-msft");
    await expect(deny).toHaveAttribute("data-attention", "BLOCKED");
    await expect(deny).toHaveAttribute("data-reason-code", "ENTRY_STALE_DATA");
    await expect(deny).toContainText(/Datos obsoletos/i);
    await expect(page.getByTestId("daily-desk-cta-MSFT")).not.toHaveText(
      /^COMPRAR$/i,
    );
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});
