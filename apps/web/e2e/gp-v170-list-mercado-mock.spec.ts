/**
 * GP-V170 — LISTA→GRÁFICO→ACCIÓN (mock API).
 *
 * Run:
 *   E2E_RUN=1 pnpm e2e -- gp-v170-list
 */
import { test, expect } from "@playwright/test";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installMercadoApiMocks,
} from "./fixtures";
import {
  E2E_INSTRUMENT_ID,
  E2E_SYMBOL,
  mercadoListFocusWorkspaceDocument,
  seedMercadoBrowserState,
} from "./integration";

test.describe("GP-V170 — Lista→Gráfico→Acción mock", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installMercadoApiMocks(page);
    await seedMercadoBrowserState(page, {
      workspaceDocument: mercadoListFocusWorkspaceDocument(),
      operativaOpen: false,
    });
  });

  test("GP-V170-02: mock list click aligns list badge phase with cockpit", async ({
    page,
  }) => {
    await page.goto("/trading");
    const listRow = page.getByTestId(`list-instrument-open-${E2E_SYMBOL}`);
    await expect(listRow).toBeVisible({ timeout: 20_000 });

    const listPhase = await listRow
      .locator('[data-testid="list-operativa-phase"]')
      .getAttribute("data-phase");
    expect(listPhase).toBeTruthy();

    await listRow.click();

    await expect(page.getByTestId("chart-indicators-zone")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("chart-indicators-zone")).toHaveAttribute(
      "data-instrument-id",
      E2E_INSTRUMENT_ID,
    );
    await expect(page.getByTestId("operativa-cockpit")).toHaveAttribute(
      "data-phase",
      listPhase!,
    );
    await expect(page.getByTestId("operativa-cockpit")).toHaveAttribute(
      "data-instrument-id",
      E2E_INSTRUMENT_ID,
    );
    await expect(page.getByTestId("operativa-cockpit")).toHaveAttribute(
      "data-symbol",
      E2E_SYMBOL,
    );
  });

  /**
   * Panel estrecho (18 % de 1024 px ≈ 184 px): las pistas de columna conservan su
   * ancho (nunca 0 px), cabecera y filas comparten `minWidth` y la lista scrollea
   * en horizontal con la zona de acciones pegada a la derecha.
   */
  test("GP-V170-04: panel estrecho mantiene columnas legibles y scrollea en horizontal", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1024, height: 800 });
    await seedMercadoBrowserState(page, {
      workspaceDocument: mercadoListFocusWorkspaceDocument(),
      operativaOpen: false,
      listsWidthPct: 18,
    });

    await page.goto("/trading");
    await expect(
      page.getByTestId(`list-instrument-open-${E2E_SYMBOL}`),
    ).toBeVisible({ timeout: 20_000 });

    const metrics = await page.evaluate(() => {
      const header = [...document.querySelectorAll("div")].find(
        (el): el is HTMLDivElement =>
          el instanceof HTMLDivElement &&
          typeof el.className === "string" &&
          el.className.includes("text-[10px] text-muted-foreground") &&
          Boolean(el.style.minWidth),
      );
      if (!header) return null;
      const scroller = header.parentElement as HTMLElement;
      const grid = header.children[1] as HTMLElement;
      const tracks = [...grid.children].map(
        (cell) => cell.getBoundingClientRect().width,
      );
      const actions = (
        header.children[header.children.length - 1] as HTMLElement
      ).getBoundingClientRect();
      const row = document.querySelector("div[data-instrument-id]");
      const rowInner = row?.children[0] as HTMLElement | undefined;
      return {
        panelWidth: scroller.clientWidth,
        scrollWidth: scroller.scrollWidth,
        headerMinWidth: header.style.minWidth,
        rowMinWidth: rowInner?.style.minWidth ?? null,
        minTrack: Math.min(...tracks),
        zeroTracks: tracks.filter((width) => width === 0).length,
        actionsInsidePanel:
          actions.right <= scroller.getBoundingClientRect().right + 1,
      };
    });

    expect(metrics).not.toBeNull();
    // Toda cabecera conserva ancho real (antes 8 de 9 medían 0 px).
    expect(metrics!.zeroTracks).toBe(0);
    expect(metrics!.minTrack).toBeGreaterThanOrEqual(40);
    // Cabecera y filas alineadas ⇒ mismo ancho mínimo y scroll horizontal compartido.
    expect(metrics!.rowMinWidth).toBe(metrics!.headerMinWidth);
    expect(metrics!.scrollWidth).toBeGreaterThan(metrics!.panelWidth);
    // Los 3 iconos de fila no se salen del marco.
    expect(metrics!.actionsInsidePanel).toBe(true);
  });
});
