import {
  AreaSeries,
  BarSeries,
  BaselineSeries,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  LineType,
  type AreaSeriesPartialOptions,
  type IChartApi,
  type ISeriesApi,
  type LineSeriesPartialOptions,
} from "lightweight-charts";
import type { OhlcvBarDto } from "@bolsa/shared";
import {
  isChartSeriesTypeImplemented,
  normalizeChartSeriesType,
  type ChartSeriesType,
  type ChartSeriesTypeParams,
} from "@bolsa/shared";
import {
  barsToKagiSeries,
  barsToLineBreakSeries,
  barsToPointAndFigureSeries,
  barsToRenkoSeries,
  resolveKagiReversalPct,
  resolveLineBreakLines,
  resolvePointAndFigureBox,
  resolvePointAndFigureReversal,
  resolveRenkoBrickSize,
} from "@/features/charts/chart-advanced-series";
import {
  barsToChartSeries,
  barsToCloseColumnSeries,
  barsToCloseLineSeries,
  barsToHeikinAshiSeries,
  barsToHighLowBarSeries,
  barsToHlcBarSeries,
  barsToTypicalPriceLineSeries,
  barsToVolumeCandleSeries,
} from "@/features/charts/chart-utils";

export type MainSeriesEngineKind =
  | "candlestick"
  | "hollow-candlestick"
  | "bar"
  | "hlc-bar"
  | "high-low-bar"
  | "line"
  | "line-markers"
  | "line-step"
  | "area"
  | "area-hlc"
  | "baseline"
  | "columns"
  | "heikin-ashi"
  | "volume-candlestick"
  | "renko"
  | "line-break"
  | "kagi"
  | "point-and-figure";

export type ChartMainPriceSeries =
  | ISeriesApi<"Candlestick">
  | ISeriesApi<"Bar">
  | ISeriesApi<"Line">
  | ISeriesApi<"Area">
  | ISeriesApi<"Baseline">
  | ISeriesApi<"Histogram">;

export interface ChartMainSeriesColors {
  upColor: string;
  downColor: string;
}

export function resolveMainSeriesEngine(
  seriesType: ChartSeriesType,
): MainSeriesEngineKind {
  const type = normalizeChartSeriesType(seriesType);
  if (!isChartSeriesTypeImplemented(type)) return "candlestick";

  switch (type) {
    case "bars":
      return "bar";
    case "hlc-bars":
      return "hlc-bar";
    case "high-low":
      return "high-low-bar";
    case "hollow-candles":
      return "hollow-candlestick";
    case "line":
      return "line";
    case "line-markers":
      return "line-markers";
    case "line-step":
      return "line-step";
    case "area":
      return "area";
    case "area-hlc":
      return "area-hlc";
    case "baseline":
      return "baseline";
    case "columns":
      return "columns";
    case "heikin-ashi":
      return "heikin-ashi";
    case "volume-candles":
      return "volume-candlestick";
    case "renko":
      return "renko";
    case "line-break":
      return "line-break";
    case "kagi":
      return "kagi";
    case "point-and-figure":
      return "point-and-figure";
    case "candles":
    default:
      return "candlestick";
  }
}

function hollowCandleOptions(colors: ChartMainSeriesColors) {
  return {
    upColor: "rgba(0,0,0,0)",
    downColor: colors.downColor,
    borderVisible: true,
    borderUpColor: colors.upColor,
    borderDownColor: colors.downColor,
    wickUpColor: colors.upColor,
    wickDownColor: colors.downColor,
  };
}

function solidCandleOptions(colors: ChartMainSeriesColors) {
  return {
    upColor: colors.upColor,
    downColor: colors.downColor,
    borderVisible: false,
    wickUpColor: colors.upColor,
    wickDownColor: colors.downColor,
  };
}

function lineOptions(
  colors: ChartMainSeriesColors,
  extra?: LineSeriesPartialOptions,
): LineSeriesPartialOptions {
  return {
    color: colors.upColor,
    lineWidth: 2,
    lastValueVisible: true,
    priceLineVisible: false,
    ...extra,
  };
}

function areaOptions(colors: ChartMainSeriesColors): AreaSeriesPartialOptions {
  return {
    lineColor: colors.upColor,
    topColor: `${colors.upColor}66`,
    bottomColor: `${colors.upColor}08`,
    lineWidth: 2,
    lastValueVisible: true,
    priceLineVisible: false,
  };
}

export function createMainPriceSeries(
  chart: IChartApi,
  kind: MainSeriesEngineKind,
  colors: ChartMainSeriesColors,
): ChartMainPriceSeries {
  switch (kind) {
    case "bar":
    case "hlc-bar":
    case "high-low-bar":
      return chart.addSeries(BarSeries, {
        upColor: colors.upColor,
        downColor: colors.downColor,
        thinBars: false,
      });
    case "line":
      return chart.addSeries(LineSeries, lineOptions(colors));
    case "line-markers":
      return chart.addSeries(
        LineSeries,
        lineOptions(colors, {
          pointMarkersVisible: true,
          pointMarkersRadius: 3,
        }),
      );
    case "line-step":
      return chart.addSeries(
        LineSeries,
        lineOptions(colors, { lineType: LineType.WithSteps }),
      );
    case "area":
    case "area-hlc":
      return chart.addSeries(AreaSeries, areaOptions(colors));
    case "baseline":
      return chart.addSeries(BaselineSeries, {
        baseValue: { type: "price", price: 0 },
        topLineColor: colors.upColor,
        topFillColor1: `${colors.upColor}44`,
        topFillColor2: `${colors.upColor}08`,
        bottomLineColor: colors.downColor,
        bottomFillColor1: `${colors.downColor}44`,
        bottomFillColor2: `${colors.downColor}08`,
        lineWidth: 2,
        lastValueVisible: true,
        priceLineVisible: false,
      });
    case "columns":
      return chart.addSeries(HistogramSeries, {
        priceFormat: { type: "price" },
        lastValueVisible: false,
        priceLineVisible: false,
      });
    case "hollow-candlestick":
      return chart.addSeries(CandlestickSeries, hollowCandleOptions(colors));
    case "heikin-ashi":
    case "volume-candlestick":
    case "renko":
    case "line-break":
    case "kagi":
    case "point-and-figure":
      return chart.addSeries(CandlestickSeries, solidCandleOptions(colors));
    case "candlestick":
    default:
      return chart.addSeries(CandlestickSeries, solidCandleOptions(colors));
  }
}

export function setMainPriceSeriesData(
  series: ChartMainPriceSeries,
  kind: MainSeriesEngineKind,
  bars: OhlcvBarDto[],
  colors: ChartMainSeriesColors,
  params?: ChartSeriesTypeParams,
): void {
  if (bars.length === 0) {
    series.setData([]);
    return;
  }

  switch (kind) {
    case "line":
    case "line-markers":
    case "line-step":
      (series as ISeriesApi<"Line">).setData(barsToCloseLineSeries(bars));
      return;
    case "area":
      (series as ISeriesApi<"Area">).setData(barsToCloseLineSeries(bars));
      return;
    case "area-hlc":
      (series as ISeriesApi<"Area">).setData(
        barsToTypicalPriceLineSeries(bars),
      );
      return;
    case "baseline": {
      const baseline = series as ISeriesApi<"Baseline">;
      const basePrice =
        bars[Math.floor(bars.length / 2)]?.close ?? bars[0]!.close;
      baseline.applyOptions({ baseValue: { type: "price", price: basePrice } });
      baseline.setData(barsToCloseLineSeries(bars));
      return;
    }
    case "columns":
      (series as ISeriesApi<"Histogram">).setData(
        barsToCloseColumnSeries(bars, colors.upColor, colors.downColor),
      );
      return;
    case "hlc-bar":
      (series as ISeriesApi<"Bar">).setData(barsToHlcBarSeries(bars));
      return;
    case "high-low-bar":
      (series as ISeriesApi<"Bar">).setData(barsToHighLowBarSeries(bars));
      return;
    case "bar":
      (series as ISeriesApi<"Bar">).setData(barsToChartSeries(bars));
      return;
    case "hollow-candlestick":
      (series as ISeriesApi<"Candlestick">).setData(barsToChartSeries(bars));
      return;
    case "heikin-ashi":
      (series as ISeriesApi<"Candlestick">).setData(
        barsToHeikinAshiSeries(bars),
      );
      return;
    case "volume-candlestick":
      (series as ISeriesApi<"Candlestick">).setData(
        barsToVolumeCandleSeries(bars, colors.upColor, colors.downColor),
      );
      return;
    case "renko":
      (series as ISeriesApi<"Candlestick">).setData(
        barsToRenkoSeries(
          bars,
          resolveRenkoBrickSize(bars, params),
          colors.upColor,
          colors.downColor,
        ),
      );
      return;
    case "line-break":
      (series as ISeriesApi<"Candlestick">).setData(
        barsToLineBreakSeries(
          bars,
          resolveLineBreakLines(params),
          colors.upColor,
          colors.downColor,
        ),
      );
      return;
    case "kagi":
      (series as ISeriesApi<"Candlestick">).setData(
        barsToKagiSeries(
          bars,
          resolveKagiReversalPct(params),
          colors.upColor,
          colors.downColor,
        ),
      );
      return;
    case "point-and-figure":
      (series as ISeriesApi<"Candlestick">).setData(
        barsToPointAndFigureSeries(
          bars,
          resolvePointAndFigureBox(bars, params),
          resolvePointAndFigureReversal(params),
          colors.upColor,
          colors.downColor,
        ),
      );
      return;
    case "candlestick":
    default:
      (series as ISeriesApi<"Candlestick">).setData(barsToChartSeries(bars));
  }
}

export function applyMainPriceSeriesColors(
  series: ChartMainPriceSeries,
  kind: MainSeriesEngineKind,
  colors: ChartMainSeriesColors,
): void {
  switch (kind) {
    case "line":
    case "line-markers":
    case "line-step":
      (series as ISeriesApi<"Line">).applyOptions({ color: colors.upColor });
      return;
    case "area":
    case "area-hlc":
      (series as ISeriesApi<"Area">).applyOptions(areaOptions(colors));
      return;
    case "baseline":
      (series as ISeriesApi<"Baseline">).applyOptions({
        topLineColor: colors.upColor,
        topFillColor1: `${colors.upColor}44`,
        topFillColor2: `${colors.upColor}08`,
        bottomLineColor: colors.downColor,
        bottomFillColor1: `${colors.downColor}44`,
        bottomFillColor2: `${colors.downColor}08`,
      });
      return;
    case "bar":
    case "hlc-bar":
    case "high-low-bar":
      (series as ISeriesApi<"Bar">).applyOptions({
        upColor: colors.upColor,
        downColor: colors.downColor,
      });
      return;
    case "hollow-candlestick":
      (series as ISeriesApi<"Candlestick">).applyOptions(
        hollowCandleOptions(colors),
      );
      return;
    case "heikin-ashi":
      (series as ISeriesApi<"Candlestick">).applyOptions(
        solidCandleOptions(colors),
      );
      return;
    case "volume-candlestick":
    case "renko":
    case "line-break":
    case "kagi":
    case "point-and-figure":
    case "columns":
      return;
    case "candlestick":
    default:
      (series as ISeriesApi<"Candlestick">).applyOptions(
        solidCandleOptions(colors),
      );
  }
}
