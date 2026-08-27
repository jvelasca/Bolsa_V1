import { describe, expect, it } from "vitest";
import type { OhlcvBarDto } from "@bolsa/shared";
import sampleBars from "@fixtures/ohlcv-ibe-sample.json";
import {
  barsToChartSeries,
  barsToVolumeSeries,
  CHART_THEME,
  formatPct,
  formatPrice,
  formatChartBarPrice,
  formatBarIntraChangeLabel,
  hasChartData,
  summarizeBars,
} from "./chart-utils";

const fixture = sampleBars as OhlcvBarDto[];

describe("chart-utils", () => {
  it("convierte barras OHLCV al formato del gráfico", () => {
    const series = barsToChartSeries(fixture);

    expect(series).toHaveLength(5);
    expect(series[0]).toEqual({
      time: "2024-01-02",
      open: 10.52,
      high: 10.88,
      low: 10.41,
      close: 10.76,
    });
  });

  it("detecta si hay datos para renderizar", () => {
    expect(hasChartData(fixture)).toBe(true);
    expect(hasChartData([])).toBe(false);
  });

  it("resume el rango de precios del histórico", () => {
    const summary = summarizeBars(fixture);

    expect(summary.count).toBe(5);
    expect(summary.first).toBe("2024-01-02");
    expect(summary.last).toBe("2024-01-08");
    expect(summary.minLow).toBe(10.41);
    expect(summary.maxHigh).toBe(10.98);
  });

  it("resume barras vacías sin errores", () => {
    expect(summarizeBars([])).toEqual({
      count: 0,
      first: null,
      last: null,
      minLow: null,
      maxHigh: null,
    });
  });

  it("convierte volumen al formato del histograma", () => {
    const volume = barsToVolumeSeries(fixture);

    expect(volume).toHaveLength(5);
    expect(volume[0]?.value).toBe(fixture[0]!.volume);
    expect(volume[0]?.color).toContain("rgba");
  });

  it("formatea precio y porcentaje", () => {
    expect(formatPrice(10.5)).toBe("10.50");
    expect(formatPrice(10.5, "EUR")).toBe("10.50 €");
    expect(formatPrice(10.5, "USD")).toBe("$10.50");
    expect(formatChartBarPrice(40.1256)).toBe("40.126");
    expect(formatPct(1.25)).toBe("+1.25%");
    expect(formatPct(-2)).toBe("-2.00%");
    expect(formatPct(null)).toBe("—");
  });

  it("formatea variación intra-vela C−O", () => {
    const bar = {
      open: 40,
      high: 40.5,
      low: 39.8,
      close: 40.055,
      volume: 1000,
      timestamp: "2024-01-02",
    };
    expect(formatBarIntraChangeLabel(bar)).toEqual({
      text: "+0.055 (+0.14%)",
      isUp: true,
    });
    const down = { ...bar, close: 39.9 };
    expect(formatBarIntraChangeLabel(down)?.isUp).toBe(false);
    expect(formatBarIntraChangeLabel(down)?.text).toBe("-0.100 (-0.25%)");
  });

  it("expone colores del tema del gráfico", () => {
    expect(CHART_THEME.upColor).toBe("#22c55e");
    expect(CHART_THEME.downColor).toBe("#ef4444");
    expect(CHART_THEME.sma20Color).toBeDefined();
  });
});
