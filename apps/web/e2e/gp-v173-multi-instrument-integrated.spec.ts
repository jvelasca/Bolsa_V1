/**
 * GP-V173 — Multi-instrument integrity integrado (API real).
 *
 * Run:
 *   E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v173
 */
import { test, expect, type Page } from "@playwright/test";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import {
  ensureMultiInstrumentMercadoFixture,
  gateIntegratedE2eEnvironment,
  mercadoEntryPositionWorkspaceDocument,
  mercadoListFocusWorkspaceDocument,
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
  type MercadoInstrumentSlice,
  type MultiInstrumentMercadoFixture,
} from "./integration";

async function ensureCarteraList(page: Page) {
  // Chip del carrusel (no el botón nav «Cartera» de la top bar).
  const cartera = page.locator('button[title^="Cartera ("]');
  await expect(cartera).toBeVisible({ timeout: 20_000 });
  await expect(cartera).toHaveAttribute("title", /Cartera \([1-9]\d*\)/, {
    timeout: 20_000,
  });
  await cartera.click();
}

async function assertPositionIdentity(
  page: Page,
  slice: MercadoInstrumentSlice,
) {
  const chartZone = page.getByTestId("chart-indicators-zone");
  await expect(chartZone).toBeVisible({ timeout: 20_000 });
  await expect(chartZone).toHaveAttribute(
    "data-instrument-id",
    slice.instrumentId,
  );

  const cockpit = page.getByTestId("operativa-cockpit");
  await expect(cockpit).toBeVisible({ timeout: 20_000 });
  await expect(cockpit).toHaveAttribute(
    "data-instrument-id",
    slice.instrumentId,
  );
  await expect(cockpit).toHaveAttribute("data-symbol", slice.symbol);
  await expect(cockpit).toHaveAttribute("data-position-id", slice.positionId);
  if (slice.tradePlanId) {
    await expect(cockpit).toHaveAttribute(
      "data-trade-plan-id",
      slice.tradePlanId,
    );
  }
  if (slice.decisionId) {
    await expect(cockpit).toHaveAttribute("data-decision-id", slice.decisionId);
  }
  await expect(page.getByTestId("position-operational-star-card")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("entry-decision-surface")).toHaveCount(0);
  if (slice.levels?.currentStop != null) {
    const stop = page.getByTestId("position-decision-stop");
    if (await stop.count()) {
      await expect(stop.first()).toContainText(
        slice.levels.currentStop.toFixed(2),
      );
    }
  }
}

test.describe("GP-V173 — Multi-instrument integrated", () => {
  test.describe.configure({ mode: "serial" });

  let environmentSkip: string | null = null;
  let fixture: MultiInstrumentMercadoFixture | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    environmentSkip = await gateIntegratedE2eEnvironment(request, baseURL, {
      e2eEnabled: e2eEnabled(),
      e2eSkipReason: E2E_SKIP_REASON,
    });
    if (environmentSkip || !baseURL) return;
    fixture = await ensureMultiInstrumentMercadoFixture(request, baseURL);
  });

  test.beforeEach(() => {
    if (environmentSkip) {
      test.skip(true, environmentSkip);
    }
    if (!fixture) {
      throw new Error(
        "Multi-instrument Mercado E2E fixture missing after environment gates.",
      );
    }
  });

  test("GP-V173-01: A→B→C→A rematch identity without residual", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
    const [a, b, c] = fixture.instruments;
    if (!a || !b || !c) {
      throw new Error("Requires ≥3 seeded positions");
    }

    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: mercadoListFocusWorkspaceDocument({
        instrumentId: a.instrumentId,
        symbol: a.symbol,
        workspaceId: fixture.workspaceId,
      }),
      operativaOpen: false,
    });
    await page.goto("/trading");
    await ensureCarteraList(page);

    for (const slice of [a, b, c, a]) {
      const listRow = page.getByTestId(`list-instrument-open-${slice.symbol}`);
      await expect(listRow).toBeVisible({ timeout: 20_000 });
      await expect(listRow).toHaveAttribute(
        "data-instrument-id",
        slice.instrumentId,
      );
      await listRow.click();
      await assertPositionIdentity(page, slice);
    }
  });

  test("GP-V173-02: refresh keeps focused instrument identity", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
    const [a, b] = fixture.instruments;
    if (!a || !b) throw new Error("Requires ≥2 seeded positions");

    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: mercadoListFocusWorkspaceDocument({
        instrumentId: a.instrumentId,
        symbol: a.symbol,
        workspaceId: fixture.workspaceId,
      }),
      operativaOpen: false,
    });
    await page.goto("/trading");
    await ensureCarteraList(page);
    await page.getByTestId(`list-instrument-open-${b.symbol}`).click();
    await assertPositionIdentity(page, b);

    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: mercadoWorkspaceDocument({
        instrumentId: b.instrumentId,
        symbol: b.symbol,
        workspaceId: fixture.workspaceId,
      }),
      operativaOpen: true,
    });
    await page.reload();
    await assertPositionIdentity(page, b);
    await expect(page.getByTestId("operativa-cockpit")).not.toHaveAttribute(
      "data-instrument-id",
      a.instrumentId,
    );
  });

  test("GP-V173-03: Entry surface → Position surface on Cartera focus", async ({
    page,
  }) => {
    if (!fixture) throw new Error("fixture required");
    if (!fixture.entryOnly) {
      test.skip(
        true,
        "Catalog has <4 instruments; Entry-only slice unavailable (need ≥4).",
      );
    }
    const entry = fixture.entryOnly!;
    const position = fixture.instruments[0]!;
    const dualDoc = mercadoEntryPositionWorkspaceDocument({
      positionInstrumentId: position.instrumentId,
      positionSymbol: position.symbol,
      entryInstrumentId: entry.instrumentId,
      entrySymbol: entry.symbol,
      workspaceId: fixture.workspaceId,
    });

    await seedMercadoBrowserState(page, {
      accountId: fixture.accountId,
      workspaceId: fixture.workspaceId,
      workspaceDocument: dualDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");

    await assertPositionIdentity(page, position);

    await page
      .locator(
        `[data-symbol="${entry.symbol}"][data-instrument-id="${entry.instrumentId}"]`,
      )
      .click();
    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).toHaveAttribute(
      "data-instrument-id",
      entry.instrumentId,
    );
    await expect(cockpit).toHaveAttribute("data-symbol", entry.symbol);
    await expect(cockpit).not.toHaveAttribute("data-position-id");
    await expect(
      page.getByTestId("position-operational-star-card"),
    ).toHaveCount(0);
    // Entry Decision Surface exige study ARMED; sin seed API → no-levels fail-closed.
    const entrySurface = page.getByTestId("entry-decision-surface");
    const noLevels = page.getByTestId("operativa-cockpit-no-levels");
    await expect(entrySurface.or(noLevels)).toBeVisible({ timeout: 20_000 });

    await ensureCarteraList(page);
    await page.getByTestId(`list-instrument-open-${position.symbol}`).click();
    await assertPositionIdentity(page, position);
  });
});
