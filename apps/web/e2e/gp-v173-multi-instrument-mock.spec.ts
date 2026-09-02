/**
 * GP-V173 — Multi-instrument integrity (mock API).
 *
 * Run:
 *   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v173
 */
import { test, expect, type Page } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installMercadoMultiApiMocks,
  setMercadoMockWorkspaceDocument,
} from "./fixtures";
import {
  E2E_ENTRY_ONLY_INSTRUMENT,
  mercadoEntryPositionWorkspaceDocument,
  mercadoListFocusWorkspaceDocument,
  mercadoMultiInstrumentSlicesFromMock,
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
  type MercadoInstrumentSlice,
} from "./integration";

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
  await expect(
    page.getByTestId("position-operational-star-card"),
  ).toBeVisible();
  await expect(page.getByTestId("entry-decision-surface")).toHaveCount(0);
}

test.describe("GP-V173 — Multi-instrument mock", () => {
  const slices = mercadoMultiInstrumentSlicesFromMock();

  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installMercadoMultiApiMocks(page);
  });

  test.afterEach(() => {
    setMercadoMockWorkspaceDocument(null);
  });

  test("GP-V173-01: A→B→C→A rematch identity without residual", async ({
    page,
  }) => {
    expect(slices.length).toBeGreaterThanOrEqual(3);
    const [a, b, c] = slices;
    const listDoc = mercadoListFocusWorkspaceDocument({
      instrumentId: a!.instrumentId,
      symbol: a!.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);

    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: false,
    });
    await page.goto("/trading");

    for (const slice of [a!, b!, c!, a!]) {
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
    const [a, b] = slices;
    const listDoc = mercadoListFocusWorkspaceDocument({
      instrumentId: a!.instrumentId,
      symbol: a!.symbol,
    });
    setMercadoMockWorkspaceDocument(listDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: listDoc,
      operativaOpen: false,
    });
    await page.goto("/trading");
    await page.getByTestId(`list-instrument-open-${b!.symbol}`).click();
    await assertPositionIdentity(page, b!);

    const focusedDoc = mercadoWorkspaceDocument({
      instrumentId: b!.instrumentId,
      symbol: b!.symbol,
    });
    setMercadoMockWorkspaceDocument(focusedDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: focusedDoc,
      operativaOpen: true,
    });
    await page.reload();
    await assertPositionIdentity(page, b!);
    await expect(page.getByTestId("operativa-cockpit")).not.toHaveAttribute(
      "data-instrument-id",
      a!.instrumentId,
    );
  });

  test("GP-V173-03: Entry surface → Position surface on Cartera focus", async ({
    page,
  }) => {
    const position = slices[0]!;
    const dualDoc = mercadoEntryPositionWorkspaceDocument({
      positionInstrumentId: position.instrumentId,
      positionSymbol: position.symbol,
    });
    setMercadoMockWorkspaceDocument(dualDoc);
    await seedMercadoBrowserState(page, {
      workspaceDocument: dualDoc,
      operativaOpen: true,
    });
    await page.goto("/trading");

    await assertPositionIdentity(page, position);

    await page
      .locator('[data-symbol="NVDA"][data-instrument-id="inst-nvda"]')
      .click();
    const cockpit = page.getByTestId("operativa-cockpit");
    await expect(cockpit).toBeVisible({ timeout: 20_000 });
    await expect(cockpit).toHaveAttribute(
      "data-instrument-id",
      E2E_ENTRY_ONLY_INSTRUMENT.id,
    );
    await expect(cockpit).toHaveAttribute(
      "data-symbol",
      E2E_ENTRY_ONLY_INSTRUMENT.symbol,
    );
    await expect(cockpit).not.toHaveAttribute("data-position-id");
    await expect(page.getByTestId("entry-decision-surface")).toBeVisible();
    await expect(
      page.getByTestId("position-operational-star-card"),
    ).toHaveCount(0);

    await page.getByTestId(`list-instrument-open-${position.symbol}`).click();
    await assertPositionIdentity(page, position);
  });
});
