import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OhlcvBarDto } from "@bolsa/shared";
import type { ChartMainPriceSeries } from "@/features/charts/chart-main-series";
import { ChartMarketStructureLevelsLayer } from "@/features/charts/chart-market-structure-levels-layer";
import { patchMarketStructurePrefs } from "@/features/charts/market-structure-prefs";

const START = Date.UTC(2026, 0, 1);
const DAY = 86_400_000;

function zigzag(points: readonly number[], legBars = 10): OhlcvBarDto[] {
  const bars: OhlcvBarDto[] = [];
  let index = 0;
  const push = (price: number) => {
    bars.push({
      timestamp: new Date(START + index * DAY).toISOString(),
      open: price,
      high: price + 0.15,
      low: price - 0.15,
      close: price,
      volume: 1_000,
      adjClose: null,
      source: "yahoo",
    });
    index += 1;
  };
  for (let p = 0; p < points.length - 1; p += 1) {
    const from = points[p]!;
    const to = points[p + 1]!;
    for (let k = 0; k < legBars; k += 1) {
      push(from + ((to - from) * k) / legBars);
    }
  }
  push(points[points.length - 1]!);
  return bars;
}

/** Soportes con dos toques; resistencias de un solo toque (no fiables). */
const ascendingBars = zigzag([
  11.5, 10.0, 11.8, 10.2, 12.1, 10.4, 12.4, 10.6, 12.6,
]);

const createPriceLine = vi.fn();
const removePriceLine = vi.fn();

function fakeSeries(): ChartMainPriceSeries {
  return {
    createPriceLine,
    removePriceLine,
  } as unknown as ChartMainPriceSeries;
}

beforeEach(() => {
  createPriceLine.mockReset();
  removePriceLine.mockReset();
  createPriceLine.mockImplementation((options: unknown) => ({
    options,
    applyOptions: vi.fn(),
  }));
  patchMarketStructurePrefs({ showChartLevels: true });
});

afterEach(() => {
  cleanup();
});

describe("ChartMarketStructureLevelsLayer", () => {
  it("solo pinta los niveles detectados", async () => {
    const { container } = render(
      <ChartMarketStructureLevelsLayer
        series={fakeSeries()}
        bars={ascendingBars}
        chartTimeframe="1d"
        chartReady
      />,
    );
    await waitFor(() => expect(createPriceLine).toHaveBeenCalled());
    const ids = createPriceLine.mock.calls.map(
      (call) => (call[0] as { id: string }).id,
    );
    expect(ids.length).toBe(1);
    expect(ids[0]).toContain(":support:");
    expect(ids.some((id) => id.includes("resistance"))).toBe(false);

    const layer = container.querySelector(
      '[data-testid="chart-market-structure-levels"]',
    );
    expect(layer?.getAttribute("data-level-count")).toBe("1");
    expect(layer?.getAttribute("data-levels")).toBe("support");
  });

  it("declara los no fiables sin dibujarlos", async () => {
    const { container } = render(
      <ChartMarketStructureLevelsLayer
        series={fakeSeries()}
        bars={ascendingBars}
        chartTimeframe="1d"
        chartReady
      />,
    );
    await waitFor(() => expect(createPriceLine).toHaveBeenCalled());
    const layer = container.querySelector(
      '[data-testid="chart-market-structure-levels"]',
    );
    expect(layer?.textContent).toContain("1 soporte · 0 resistencias");
    expect(layer?.textContent).toContain("Niveles calc.");
  });

  it("con la preferencia oculta no se crea ninguna línea", async () => {
    patchMarketStructurePrefs({ showChartLevels: false });
    const { container } = render(
      <ChartMarketStructureLevelsLayer
        series={fakeSeries()}
        bars={ascendingBars}
        chartTimeframe="1d"
        chartReady
      />,
    );
    await waitFor(() =>
      expect(
        container.querySelector(
          '[data-testid="chart-market-structure-levels"]',
        )?.getAttribute("data-visible"),
      ).toBe("false"),
    );
    expect(createPriceLine).not.toHaveBeenCalled();
  });

  it("el botón oculta y vuelve a mostrar sin tocar el contrato", async () => {
    const { container, getByTestId } = render(
      <ChartMarketStructureLevelsLayer
        series={fakeSeries()}
        bars={ascendingBars}
        chartTimeframe="1d"
        chartReady
      />,
    );
    await waitFor(() => expect(createPriceLine).toHaveBeenCalled());

    fireEvent.click(getByTestId("chart-market-structure-toggle"));
    await waitFor(() => expect(removePriceLine).toHaveBeenCalled());
    expect(
      container
        .querySelector('[data-testid="chart-market-structure-levels"]')
        ?.getAttribute("data-visible"),
    ).toBe("false");

    fireEvent.click(getByTestId("chart-market-structure-toggle"));
    await waitFor(() =>
      expect(
        container
          .querySelector('[data-testid="chart-market-structure-levels"]')
          ?.getAttribute("data-visible"),
      ).toBe("true"),
    );
  });

  it("sin histórico suficiente declara el hueco y no pinta", async () => {
    const { container } = render(
      <ChartMarketStructureLevelsLayer
        series={fakeSeries()}
        bars={ascendingBars.slice(0, 20)}
        chartTimeframe="1d"
        chartReady
      />,
    );
    const layer = container.querySelector(
      '[data-testid="chart-market-structure-levels"]',
    );
    expect(layer?.getAttribute("data-measured")).toBe("false");
    expect(layer?.textContent).toContain("Histórico insuficiente");
    expect(createPriceLine).not.toHaveBeenCalled();
  });
});
