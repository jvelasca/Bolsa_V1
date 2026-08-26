import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CandlestickSeries,
  ColorType,
  LineStyle,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
} from "lightweight-charts";
import {
  NO_OPERATIONAL_PLAN_COPY,
  type DecisionJournalStudyViewV1,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import {
  barsToChartSeries,
  CHART_THEME,
  formatPrice,
} from "@/features/charts/chart-utils";
import { observeStableSize } from "@/features/charts/chart-stable-resize";

export function DecisionStudyChart({
  study,
}: {
  study: DecisionJournalStudyViewV1;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const timeframe = study.timeframe || "1d";
  const ohlcvQuery = useQuery({
    queryKey: ["ohlcv", study.instrumentId, timeframe, "journal-study"],
    queryFn: () => api.getOhlcv(study.instrumentId, 120, timeframe),
  });
  const bars = ohlcvQuery.data?.data ?? [];

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, {
      width: Math.max(1, el.clientWidth),
      height: 220,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: CHART_THEME.textColor,
      },
      grid: {
        vertLines: { color: CHART_THEME.gridColor },
        horzLines: { color: CHART_THEME.gridColor },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 1 },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: CHART_THEME.upColor,
      downColor: CHART_THEME.downColor,
      borderVisible: false,
      wickUpColor: CHART_THEME.upColor,
      wickDownColor: CHART_THEME.downColor,
    });
    chartRef.current = chart;
    seriesRef.current = series;
    const stop = observeStableSize(el, (width) => {
      chart.applyOptions({ width: Math.max(1, width) });
    });
    return () => {
      stop();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [study.sessionId]);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;
    series.setData(barsToChartSeries(bars));
    chart.timeScale().fitContent();

    const lines: IPriceLine[] = [];
    if (study.hasOperationalPlan) {
      if (study.entry != null) {
        lines.push(
          series.createPriceLine({
            price: study.entry,
            color: "#38bdf8",
            title: "Entrada",
            lineStyle: LineStyle.Dashed,
            lineWidth: 1,
          }),
        );
      }
      if (study.stop != null) {
        lines.push(
          series.createPriceLine({
            price: study.stop,
            color: "#ef4444",
            title: "SL ↓",
            lineStyle: LineStyle.Solid,
            lineWidth: 2,
          }),
        );
      }
      if (study.target1 != null) {
        lines.push(
          series.createPriceLine({
            price: study.target1,
            color: "#22c55e",
            title: "TP1 ↑",
            lineStyle: LineStyle.Solid,
            lineWidth: 2,
          }),
        );
      }
      if (study.target2 != null) {
        lines.push(
          series.createPriceLine({
            price: study.target2,
            color: "#4ade80",
            title: "TP2",
            lineStyle: LineStyle.Dashed,
            lineWidth: 1,
          }),
        );
      }
    }
    return () => {
      for (const line of lines) {
        try {
          series.removePriceLine(line);
        } catch {
          /* chart torn down */
        }
      }
    };
  }, [
    bars,
    study.hasOperationalPlan,
    study.entry,
    study.stop,
    study.target1,
    study.target2,
  ]);

  const indicatorBits = [
    study.indicators.primary
      ? `Indicador principal: ${study.indicators.primary}`
      : null,
    study.indicators.confirmation
      ? `Confirmación: ${study.indicators.confirmation}`
      : null,
  ].filter(Boolean);

  return (
    <div data-testid="decision-study-chart">
      <div ref={containerRef} className="h-[220px] w-full" />
      {!study.hasOperationalPlan ? (
        <p
          className="mt-2 text-[11px] text-muted-foreground"
          data-testid="no-operational-plan"
        >
          {NO_OPERATIONAL_PLAN_COPY}
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-3 text-[11px]">
          {study.stop != null ? (
            <span className="text-rose-600">SL {formatPrice(study.stop)}</span>
          ) : null}
          {study.target1 != null ? (
            <span className="text-emerald-600">
              TP1 {formatPrice(study.target1)}
            </span>
          ) : null}
          {study.expectedRR != null ? (
            <span className="text-muted-foreground">
              R/R 1 : {study.expectedRR.toFixed(1)}
            </span>
          ) : null}
        </div>
      )}
      {indicatorBits.length > 0 ? (
        <p className="mt-1 text-[10px] text-muted-foreground">
          {indicatorBits.join(" · ")}
        </p>
      ) : (
        <p className="mt-1 text-[10px] text-muted-foreground">
          Indicadores del snapshot no disponibles.
        </p>
      )}
    </div>
  );
}
