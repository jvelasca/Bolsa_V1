import { cleanup, render, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReactNode } from "react";
import { DEFAULT_CHART_CONFIG, type OhlcvBarDto } from "@bolsa/shared";
import { OhlcvChart } from "./ohlcv-chart";

const sampleBars: OhlcvBarDto[] = [
  {
    timestamp: "2024-01-02",
    open: 10.52,
    high: 10.88,
    low: 10.41,
    close: 10.76,
    volume: 12450000,
    adjClose: 10.76,
    source: "yahoo",
  },
];

const setData = vi.fn();
const fitContent = vi.fn();
const remove = vi.fn();
const subscribeVisibleLogicalRangeChange = vi.fn();
const unsubscribeVisibleLogicalRangeChange = vi.fn();
const getVisibleLogicalRange = vi.fn(() => ({ from: 1, to: 10 }));

vi.mock("lightweight-charts", () => ({
  CandlestickSeries: "CandlestickSeries",
  HistogramSeries: "HistogramSeries",
  LineSeries: "LineSeries",
  ColorType: { Solid: "solid" },
  CrosshairMode: { Normal: 0, Magnet: 1 },
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({
      setData,
      applyOptions: vi.fn(),
      priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
      createPriceLine: vi.fn(() => ({})),
      removePriceLine: vi.fn(),
      attachPrimitive: vi.fn(),
      detachPrimitive: vi.fn(),
    })),
    removeSeries: vi.fn(),
    applyOptions: vi.fn(),
    remove,
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    priceScale: vi.fn(() => ({
      applyOptions: vi.fn(),
      getVisibleRange: vi.fn(() => null),
    })),
    timeScale: vi.fn(() => ({
      fitContent,
      subscribeVisibleLogicalRangeChange,
      unsubscribeVisibleLogicalRangeChange,
      getVisibleLogicalRange,
      applyOptions: vi.fn(),
      setVisibleLogicalRange: vi.fn(),
      scrollToPosition: vi.fn(),
    })),
  })),
}));

const config = {
  ...DEFAULT_CHART_CONFIG,
  display: { ...DEFAULT_CHART_CONFIG.display, height: 300 },
};

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("OhlcvChart", () => {
  let rectSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // jsdom no mide layout: el motor solo se monta con un contenedor medible.
    rectSpy = vi
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockReturnValue({
        width: 800,
        height: 300,
        top: 0,
        left: 0,
        bottom: 300,
        right: 800,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      } as DOMRect);
  });

  afterEach(() => {
    cleanup();
    rectSpy.mockRestore();
    vi.clearAllMocks();
  });

  it("muestra mensaje cuando no hay barras", () => {
    const { container } = renderWithProviders(
      <OhlcvChart bars={[]} config={config} />,
    );

    expect(within(container).getByText(/Sin datos OHLCV/i)).toBeInTheDocument();
  });

  it("renderiza contenedor del gráfico con datos", () => {
    const { container } = renderWithProviders(
      <OhlcvChart bars={sampleBars} config={config} />,
    );

    expect(
      within(container).queryByText(/Sin datos OHLCV/i),
    ).not.toBeInTheDocument();
    expect(container.querySelector(".w-full")).toBeTruthy();
  });

  it("expone hooks estables de test (instrumento, timeframe, barras)", async () => {
    const { getByTestId } = renderWithProviders(
      <OhlcvChart
        bars={sampleBars}
        config={config}
        instrumentId="i-1"
        chartTimeframe="1d"
        seriesType="candles"
        symbol="AAPL"
      />,
    );

    const host = getByTestId("ohlcv-chart");
    expect(host).toHaveAttribute("data-instrument-id", "i-1");
    expect(host).toHaveAttribute("data-timeframe", "1d");
    expect(host).toHaveAttribute("data-series-type", "candles");
    expect(host).toHaveAttribute("data-bars-count", "1");
    expect(host).toHaveAttribute("data-first-bar", "2024-01-02");
    expect(host).toHaveAttribute("data-last-bar", "2024-01-02");
    expect(host).toHaveAttribute("data-has-data", "true");

    await waitFor(() => {
      expect(host).toHaveAttribute("data-visible-range", "1.00:10.00");
    });
  });

  it("marca data-has-data=false sin barras y publica el setData real", async () => {
    setData.mockClear();
    const { getByTestId } = renderWithProviders(
      <OhlcvChart bars={[]} config={config} instrumentId="i-1" />,
    );

    const host = getByTestId("ohlcv-chart");
    expect(host).toHaveAttribute("data-bars-count", "0");
    expect(host).toHaveAttribute("data-has-data", "false");
    await waitFor(() => {
      expect(setData).toHaveBeenCalledWith([]);
    });
  });

  it("actualiza el tipo de serie sin perder los datos", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { getByTestId, rerender } = render(
      <QueryClientProvider client={queryClient}>
        <OhlcvChart bars={sampleBars} config={config} seriesType="candles" />
      </QueryClientProvider>,
    );

    expect(getByTestId("ohlcv-chart")).toHaveAttribute(
      "data-series-type",
      "candles",
    );
    rerender(
      <QueryClientProvider client={queryClient}>
        <OhlcvChart bars={sampleBars} config={config} seriesType="line" />
      </QueryClientProvider>,
    );
    expect(getByTestId("ohlcv-chart")).toHaveAttribute(
      "data-series-type",
      "line",
    );
    expect(getByTestId("ohlcv-chart")).toHaveAttribute("data-bars-count", "1");
  });
});
