/**
 * GP-V190 — MERCADO · operativa gráfica completa (mock API).
 *
 * Cubre la checklist de certificación del gráfico sin depender de Yahoo/BD:
 * host + metadatos, timeframes, estilos de serie, zoom/reset, dibujos,
 * indicadores, inspector, estados vacío/error/stale, multi-pestaña y persistencia.
 *
 * Run:
 *   $env:E2E_RUN="1"; pnpm --filter @bolsa/web exec playwright test gp-v190-mercado-chart
 */
import { expect, test, type Page } from "@playwright/test";

import { E2E_SKIP_REASON, e2eEnabled } from "./fixtures";
import {
  buildChartMarketFixture,
  chartMarketIndicatorInstances,
  chartMarketWorkspaceDocument,
  installChartMarketMocks,
  type ChartMarketFixtureOptions,
} from "./helpers/chart-market";
import { E2E_INSTRUMENT_ID, E2E_SYMBOL } from "./helpers/ids";
import { seedMercadoBrowserState } from "./helpers/mercado";

const NOISE = [
  /ResizeObserver loop/i,
  /Failed to load resource/i,
  /favicon/i,
  /net::ERR_/i,
];

async function openChart(page: Page, opts?: ChartMarketFixtureOptions) {
  const fixture = await installChartMarketMocks(page, opts);
  await seedMercadoBrowserState(page, {
    workspaceDocument: chartMarketWorkspaceDocument(opts),
    operativaOpen: false,
  });
  await page.goto("/trading");
  await expect(page.getByTestId("ohlcv-chart")).toBeVisible({
    timeout: 25_000,
  });
  return fixture;
}

function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) =>
    errors.push(`pageerror: ${error.stack ?? error.message}`),
  );
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (NOISE.some((pattern) => pattern.test(text))) return;
    errors.push(`console: ${text}`);
  });
  return errors;
}

async function openZoneMenu(page: Page, zone: "Escala" | "Estilo") {
  // El ancla lleva el valor activo como insignia + `sr-only` con el nombre de zona.
  await page
    .getByRole("button", { name: new RegExp(zone) })
    .first()
    .click();
}

async function selectZoneOption(
  page: Page,
  zone: "Escala" | "Estilo",
  optionId: string,
) {
  await openZoneMenu(page, zone);
  await page
    .getByTestId("chart-zone-menu")
    .locator(`[data-zone-option-id="${optionId}"]`)
    .click();
}

function tabFor(page: Page, tabId: string) {
  return page.locator(`[data-chart-tab-id="${tabId}"]`);
}

function drawTool(page: Page, title: RegExp) {
  return page.locator(".chart-drawing-sidebar").getByTitle(title).first();
}

/**
 * Selecciona un dibujo desde el inspector (ruta determinista): abre el panel
 * si hace falta, entra en Config → Objetos y pulsa la fila del dibujo.
 */
async function selectDrawingFromInspector(page: Page, name: RegExp) {
  const panel = page.getByTestId("chart-inspector-panel");
  if ((await panel.getAttribute("data-open")) !== "true") {
    await page
      .getByTitle("Mostrar inspector de gráficos", { exact: true })
      .click();
  }
  await expect(panel).toHaveAttribute("data-open", "true");
  await panel.getByRole("button", { name: "Config", exact: true }).click();
  await panel.getByTitle("Objetos", { exact: true }).click();
  await panel.getByRole("button", { name }).first().click();
  await expect(panel).toHaveAttribute("data-open", "true");
}

/**
 * Amplitud del rango lógico visible (`from:to`). El reset de lightweight-charts
 * (`fitContent`) recoloca el borde a `0.00` mientras el rango inicial puede
 * conservar una fracción dependiente del ancho del contenedor: comparar la
 * cadena EXACTA es frágil y no mide lo que el test dice medir (que el zoom
 * cambie la amplitud y que el reset la restaure).
 *
 * Se lee el atributo CRUDO y se deja que el `expect.poll` del test reintente:
 * envolverlo en un polling de «estabilización» anidaba dos `expect.poll` y
 * hacía que el exterior esperase una muestra quieta que llega un frame tarde.
 */
async function visibleSpan(page: Page): Promise<number> {
  const raw =
    (await page
      .getByTestId("ohlcv-chart")
      .getAttribute("data-visible-range")) ?? "";
  const [from, to] = raw.split(":").map(Number);
  return to - from;
}

/** Dibuja una línea de tendencia con el rectángulo actual de la capa. */
async function drawTrendLine(page: Page) {
  const layer = page.getByTestId("chart-drawings-layer");
  const box = await layer.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.click(
    box!.x + box!.width * 0.35,
    box!.y + box!.height * 0.6,
  );
  await page.mouse.click(
    box!.x + box!.width * 0.55,
    box!.y + box!.height * 0.35,
  );
  await expect(layer).toHaveAttribute("data-drawing-count", "1", {
    timeout: 5_000,
  });
}

test.describe("GP-V190 — MERCADO gráficos operativa (mock)", () => {
  test.skip(!e2eEnabled(), E2E_SKIP_REASON);

  test("GP-V190-01: el host del gráfico expone instrumento, escala, estilo y barras", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const fixture = await openChart(page);
    const chart = page.getByTestId("ohlcv-chart");
    const dailyBars = fixture.barsByTimeframe["1d"]!;

    await expect(chart).toHaveAttribute(
      "data-instrument-id",
      E2E_INSTRUMENT_ID,
    );
    await expect(chart).toHaveAttribute("data-symbol", E2E_SYMBOL);
    await expect(chart).toHaveAttribute("data-timeframe", "1d");
    await expect(chart).toHaveAttribute("data-series-type", "candles");
    await expect(chart).toHaveAttribute(
      "data-bars-count",
      String(dailyBars.length),
    );
    await expect(chart).toHaveAttribute("data-has-data", "true");
    await expect(chart).toHaveAttribute(
      "data-first-bar",
      dailyBars[0]!.timestamp,
    );
    await expect(chart).toHaveAttribute(
      "data-last-bar",
      dailyBars.at(-1)!.timestamp,
    );
    await expect(page.getByTestId("chart-data-status")).toHaveAttribute(
      "data-freshness-status",
      "current",
    );
    expect(errors).toEqual([]);
  });

  test("GP-V190-02: cambiar de escala recalcula query, barras y metadatos", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const fixture = await openChart(page);
    const chart = page.getByTestId("ohlcv-chart");

    await selectZoneOption(page, "Escala", "1wk");
    await expect(chart).toHaveAttribute("data-timeframe", "1wk");
    await expect(chart).toHaveAttribute(
      "data-bars-count",
      String(fixture.barsByTimeframe["1wk"]!.length),
    );

    await selectZoneOption(page, "Escala", "1h");
    await expect(chart).toHaveAttribute("data-timeframe", "1h");
    await expect(chart).toHaveAttribute(
      "data-bars-count",
      String(fixture.barsByTimeframe["1h"]!.length),
    );
    await expect(chart).toHaveAttribute("data-has-data", "true");
    expect(errors).toEqual([]);
  });

  test("GP-V190-03: estilos de serie velas, línea, Heikin-Ashi y Renko", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const fixture = await openChart(page);
    const chart = page.getByTestId("ohlcv-chart");
    const barCount = String(fixture.barsByTimeframe["1d"]!.length);

    await selectZoneOption(page, "Estilo", "line");
    await expect(chart).toHaveAttribute("data-series-type", "line");

    await selectZoneOption(page, "Estilo", "heikin-ashi");
    await expect(chart).toHaveAttribute("data-series-type", "heikin-ashi");
    await expect(chart).toHaveAttribute("data-bars-count", barCount);

    await selectZoneOption(page, "Estilo", "renko");
    await expect(chart).toHaveAttribute("data-series-type", "renko");

    await selectZoneOption(page, "Estilo", "candles");
    await expect(chart).toHaveAttribute("data-series-type", "candles");
    expect(errors).toEqual([]);
  });

  test("GP-V190-04: zoom mueve data-visible-range y el reset lo restaura", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openChart(page);

    // Normaliza con un reset explícito: `fitContent` es determinista, mientras
    // el rango del primer montaje conserva una fracción según el ancho.
    await page.getByTitle("Ajustar a ventana", { exact: true }).click();
    await expect
      .poll(() => visibleSpan(page), { timeout: 10_000 })
      .toBeGreaterThan(0);
    const initial = await visibleSpan(page);

    await page.getByTitle("Acercar", { exact: true }).click();
    await expect
      .poll(() => visibleSpan(page), { timeout: 10_000 })
      .toBeLessThan(initial - 0.5);

    await page.getByTitle("Ajustar a ventana", { exact: true }).click();
    await expect
      .poll(() => visibleSpan(page), { timeout: 10_000 })
      .toBeCloseTo(initial, 1);

    await page.getByTitle("Alejar", { exact: true }).click();
    await expect
      .poll(() => visibleSpan(page), { timeout: 10_000 })
      .toBeGreaterThan(initial + 0.5);
    expect(errors).toEqual([]);
  });

  test("GP-V190-05: crear dibujo, ocultarlo, borrarlo con teclado y respetar el bloqueo", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openChart(page);
    const layer = page.getByTestId("chart-drawings-layer");
    await expect(layer).toHaveAttribute("data-drawing-count", "0");

    await drawTool(page, /Línea de tendencia$/).click();
    await drawTrendLine(page);
    await expect(layer.locator("[data-drawing-id]")).toHaveCount(1);
    await expect(layer.locator("[data-drawing-id]")).toHaveAttribute(
      "data-drawing-kind",
      "line",
    );

    // Con la herramienta de forma la selección se limpia: se recupera desde el
    // inspector (determinista) en vez de depender de un hit-test del canvas.
    await drawTool(page, /Puntero$/).click();
    await expect(layer).toHaveAttribute("data-draw-tool", "select");
    await selectDrawingFromInspector(page, /^Línea tendencia/);
    await expect
      .poll(() => layer.getAttribute("data-selected-drawing-id"))
      .not.toBe("");
    await expect(layer.locator("[data-drawing-id]").first()).toHaveAttribute(
      "data-selected",
      "true",
    );

    await page.getByTitle("Ocultar todos los dibujos", { exact: true }).click();
    await expect(layer).toHaveCount(0);
    await page.getByTitle("Mostrar dibujos", { exact: true }).click();
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-drawing-count",
      "1",
    );
    await selectDrawingFromInspector(page, /^Línea tendencia/);

    await page.keyboard.press("Delete");
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-drawing-count",
      "0",
    );

    // Un dibujo bloqueado (o capa bloqueada) no debe borrarse con el teclado.
    await drawTool(page, /Línea de tendencia$/).click();
    await drawTrendLine(page);
    await drawTool(page, /Puntero$/).click();
    await selectDrawingFromInspector(page, /^Línea tendencia/);

    await page
      .getByTitle("Bloquear todos los dibujos", { exact: true })
      .click();
    await expect(
      page.getByTitle("Desbloquear dibujos", { exact: true }),
    ).toBeVisible();
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-layer-locked",
      "true",
    );

    await page.keyboard.press("Delete");
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-drawing-count",
      "1",
    );

    await page.getByTitle("Desbloquear dibujos", { exact: true }).click();
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-layer-locked",
      "false",
    );
    await selectDrawingFromInspector(page, /^Línea tendencia/);
    await page.keyboard.press("Delete");
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-drawing-count",
      "0",
    );
    expect(errors).toEqual([]);
  });

  test("GP-V190-06: indicadores overlay + subpanel, ocultar/mostrar y eliminar", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openChart(page, {
      indicatorInstances: chartMarketIndicatorInstances(),
    });

    await expect(page.getByTestId("chart-indicators-zone")).toHaveAttribute(
      "data-indicator-count",
      "2",
    );
    const subPanel = page.getByTestId("sub-indicator-panel");
    await expect(subPanel).toHaveCount(1);
    await expect(subPanel).toHaveAttribute("data-definition-id", "rsi");
    await expect(subPanel).toHaveAttribute("data-visible", "true");

    await subPanel.getByTitle("Ocultar indicador", { exact: true }).click();
    await expect(page.getByTestId("sub-indicator-panel")).toHaveAttribute(
      "data-visible",
      "false",
    );

    await page
      .getByTestId("sub-indicator-panel")
      .getByTitle("Mostrar indicador", { exact: true })
      .click();
    await expect(page.getByTestId("sub-indicator-panel")).toHaveAttribute(
      "data-visible",
      "true",
    );

    await page
      .getByTestId("sub-indicator-panel")
      .getByTitle("Eliminar indicador", { exact: true })
      .click();
    await expect(page.getByTestId("sub-indicator-panel")).toHaveCount(0);
    await expect(page.getByTestId("chart-indicators-zone")).toHaveAttribute(
      "data-indicator-count",
      "1",
    );
    expect(errors).toEqual([]);
  });

  test("GP-V190-07: inspector abre, identifica el instrumento y colapsa", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openChart(page);

    await page
      .getByTitle("Mostrar inspector de gráficos", { exact: true })
      .click();
    const panel = page.getByTestId("chart-inspector-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-open", "true");
    await expect(panel).toHaveAttribute("data-timeframe", "1d");
    await expect(
      panel.getByText(E2E_SYMBOL, { exact: false }).first(),
    ).toBeVisible();

    await panel.getByTitle("Colapsar inspector", { exact: true }).click();
    await expect(page.getByTestId("chart-inspector-panel")).toHaveAttribute(
      "data-open",
      "false",
    );
    expect(errors).toEqual([]);
  });

  test("GP-V190-08a: estado vacío con CTA de sincronización", async ({
    page,
  }) => {
    await openChart(page, { mode: "empty" });
    const chart = page.getByTestId("ohlcv-chart");
    await expect(chart).toHaveAttribute("data-has-data", "false");
    await expect(chart).toHaveAttribute("data-bars-count", "0");
    await expect(page.getByText("Sin datos OHLCV para 1D")).toBeVisible();
    await expect(page.getByTestId("chart-data-status")).toHaveAttribute(
      "data-freshness-status",
      "empty",
    );
  });

  test("GP-V190-08b: error de OHLCV se comunica sin romper la página", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await openChart(page, { mode: "error", freshness: "error" });
    await expect(
      page.getByText("No se pudo cargar el histórico OHLCV."),
    ).toBeVisible();
    await expect(page.getByTestId("ohlcv-chart")).toHaveAttribute(
      "data-has-data",
      "false",
    );
    await expect(page.getByTestId("chart-data-status")).toHaveAttribute(
      "data-freshness-status",
      "error",
    );
    expect(errors).toEqual([]);
  });

  test("GP-V190-08c: BD stale dispara autosanado y mantiene el badge honesto", async ({
    page,
  }) => {
    const syncRequests: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().includes("/sync")) {
        syncRequests.push(request.url());
      }
    });
    await openChart(page, { freshness: "stale" });
    await expect(page.getByTestId("chart-data-status")).toHaveAttribute(
      "data-freshness-status",
      "stale",
    );
    await expect
      .poll(() => syncRequests.length, { timeout: 10_000 })
      .toBeGreaterThan(0);
    await expect(page.getByTestId("ohlcv-chart")).toHaveAttribute(
      "data-has-data",
      "true",
    );
  });

  test("GP-V190-09: dos pestañas aíslan instrumento y dibujos", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const fixture = buildChartMarketFixture({ tabs: "two" });
    await openChart(page, {
      tabs: "two",
      drawings: [
        {
          id: "e2e-draw-tab-1",
          type: "hline",
          price: 210,
          color: "#14b8a6",
          lineWidth: 1.5,
        },
      ],
    });
    const chart = page.getByTestId("ohlcv-chart");
    await expect(chart).toHaveAttribute(
      "data-instrument-id",
      fixture.instrumentId,
    );
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-drawing-count",
      "1",
    );

    await tabFor(page, "e2e-tab-mercado-msft")
      .getByRole("button", { name: "MSFT", exact: true })
      .click();
    await expect(chart).toHaveAttribute("data-instrument-id", "inst-msft");
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-drawing-count",
      "0",
    );

    await tabFor(page, "e2e-tab-mercado")
      .getByRole("button", { name: E2E_SYMBOL, exact: true })
      .click();
    await expect(chart).toHaveAttribute(
      "data-instrument-id",
      E2E_INSTRUMENT_ID,
    );
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-drawing-count",
      "1",
    );
    expect(errors).toEqual([]);
  });

  test("GP-V190-10: recargar restaura escala y dibujos del gráfico", async ({
    page,
  }) => {
    await openChart(page);
    const layer = page.getByTestId("chart-drawings-layer");
    await drawTool(page, /Línea de tendencia$/).click();
    const box = await layer.boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.click(
      box!.x + box!.width * 0.3,
      box!.y + box!.height * 0.65,
    );
    await page.mouse.click(
      box!.x + box!.width * 0.5,
      box!.y + box!.height * 0.4,
    );
    await expect(layer).toHaveAttribute("data-drawing-count", "1");

    await page.getByRole("button", { name: "1W", exact: true }).click();
    await expect(page.getByTestId("ohlcv-chart")).toHaveAttribute(
      "data-timeframe",
      "1wk",
    );

    const persistedMeta = await page.evaluate(() =>
      localStorage.getItem("bolsa-workspace-meta"),
    );
    expect(persistedMeta).toBeTruthy();
    // El seed de `addInitScript` se re-ejecuta en cada navegación: este script
    // posterior reinyecta el estado real antes de que arranque la app.
    await page.addInitScript((meta) => {
      if (meta) localStorage.setItem("bolsa-workspace-meta", meta);
    }, persistedMeta);

    await page.reload();
    const chart = page.getByTestId("ohlcv-chart");
    await expect(chart).toBeVisible({ timeout: 25_000 });
    await expect(chart).toHaveAttribute("data-timeframe", "1wk");
    await expect(page.getByTestId("chart-drawings-layer")).toHaveAttribute(
      "data-drawing-count",
      "1",
    );
  });
});
