/**
 * GP-V175 — Chaos & stale → no-execute (mock API).
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v175
 */
import { test, expect } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installHoyStaleNoExecuteMocks,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  E2E_ENTRY_ONLY_INSTRUMENT,
  E2E_INSTRUMENT_ID,
  E2E_SYMBOL,
  mercadoEntryPositionWorkspaceDocument,
  mercadoListFocusWorkspaceDocument,
  paperAutonomousDaySlice,
  seedStaleNoExecuteBrowserState,
} from "./integration";

test.describe("GP-V175 — Chaos & stale → no-execute mock", () => {
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

  test("GP-V175-01: Hoy ENTRY_STALE_DATA — deny · 0 COMPRAR", async ({
    page,
  }) => {
    await seedStaleNoExecuteBrowserState(page, { workspaceDocument: listDoc });
    await page.goto("/mesa");
    await expect(page.getByTestId("daily-desk-inbox")).toBeVisible({
      timeout: 20_000,
    });
    // Con incidente abierto la postura visible es Bloqueado (≠ badge AUTO feliz).
    await expect(
      page.getByText(/AUTO armado|Plan armado \(AUTO\)|Estado:\s*Bloqueado/i),
    ).toBeVisible();
    await expect(
      page.getByText(/Datos obsoletos|ENTRY_STALE_DATA/i),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
    await expect(page.getByTestId("daily-desk-cta-MSFT")).toBeVisible();
    await expect(page.getByTestId("daily-desk-cta-MSFT")).not.toHaveText(
      /^COMPRAR$/i,
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
    await expect(
      page.getByText(/Datos obsoletos|ENTRY_STALE_DATA|stale/i).first(),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });

  test("GP-V175-03: Mercado entry surface stale/deny — no COMPRAR", async ({
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

    await page
      .locator(
        `[data-symbol="${E2E_ENTRY_ONLY_INSTRUMENT.symbol}"][data-instrument-id="${E2E_ENTRY_ONLY_INSTRUMENT.id}"]`,
      )
      .first()
      .click();

    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).toHaveAttribute(
      "data-instrument-id",
      E2E_ENTRY_ONLY_INSTRUMENT.id,
    );
    await expect(page.getByTestId("entry-decision-surface")).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
    await expect(
      page.getByText(/stale|obsolet|bloquead|Entradas bloqueadas/i).first(),
    ).toBeVisible();
  });

  test("GP-V175-04: UNKNOWN / recovery — no reenviar · Sin auto-heal", async ({
    page,
  }) => {
    await seedStaleNoExecuteBrowserState(page, { workspaceDocument: listDoc });
    await page.goto("/mesa");
    await expect(page.getByTestId("mesa-hoy-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("mesa-incident-banner")).toBeVisible();
    await expect(page.getByText(/Sin auto-heal/i).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );

    await page.goto("/trading");
    await expect(
      page.getByText(/Orden desconocida|no duplicar|Ver operaciones/i).first(),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );
  });
});
