import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { IChartApi, ISeriesApi } from "lightweight-charts";
import type { ChartDrawing } from "@bolsa/shared";
import { ChartDrawingsLayer } from "./chart-drawings-layer";

const container = document.createElement("div");

const chart = {
  subscribeCrosshairMove: vi.fn(),
  unsubscribeCrosshairMove: vi.fn(),
  subscribeClick: vi.fn(),
  unsubscribeClick: vi.fn(),
  timeScale: () => ({
    timeToCoordinate: () => 120,
    coordinateToTime: () => 1_700_000_000,
    subscribeVisibleLogicalRangeChange: vi.fn(),
    unsubscribeVisibleLogicalRangeChange: vi.fn(),
  }),
} as unknown as IChartApi;

const series = {
  priceToCoordinate: (price: number) => 300 - price,
  coordinateToPrice: (coordinate: number) => 300 - coordinate,
} as unknown as ISeriesApi<"Candlestick">;

const drawings: ChartDrawing[] = [
  { id: "d1", type: "hline", price: 100, color: "#22c55e" },
  {
    id: "d2",
    type: "line",
    p1: { time: "2026-10-01", price: 100 },
    p2: { time: "2026-10-31", price: 120 },
    color: "#f97316",
    locked: true,
  },
];

function renderLayer(
  overrides: Partial<Parameters<typeof ChartDrawingsLayer>[0]> = {},
) {
  return render(
    <ChartDrawingsLayer
      chart={chart}
      series={series}
      container={container}
      height={400}
      bars={[]}
      drawings={drawings}
      tool="select"
      selectedId="d2"
      onAdd={vi.fn()}
      onUpdate={vi.fn()}
      onSelect={vi.fn()}
      {...overrides}
    />,
  );
}

describe("ChartDrawingsLayer · hooks de test", () => {
  afterEach(cleanup);

  it("expone capa, número de dibujos y estado por dibujo", () => {
    const { container: root } = renderLayer();

    const layer = screen.getByTestId("chart-drawings-layer");
    expect(layer).toHaveAttribute("data-drawing-count", "2");
    expect(layer).toHaveAttribute("data-draw-tool", "select");
    expect(layer).toHaveAttribute("data-selected-drawing-id", "d2");

    const line = root.querySelector('g[data-drawing-id="d2"]');
    expect(line).toHaveAttribute("data-drawing-kind", "line");
    expect(line).toHaveAttribute("data-selected", "true");
    expect(line).toHaveAttribute("data-locked", "true");

    const hline = root.querySelector('g[data-drawing-id="d1"]');
    expect(hline).toHaveAttribute("data-drawing-kind", "hline");
    expect(hline).toHaveAttribute("data-selected", "false");
  });

  it("no renderiza la capa si está oculta", () => {
    renderLayer({ layerHidden: true });
    expect(
      screen.queryByTestId("chart-drawings-layer"),
    ).not.toBeInTheDocument();
  });
});
