/**
 * Vista previa del valor (antes de Probar + coach):
 * gráfico del periodo del wizard + rentabilidad comprar y mantener.
 */

import { useEffect, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  CandlestickSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import type { ChartTimeframe, OhlcvBarDto } from '@bolsa/shared';
import { api } from '@/lib/api';
import {
  buyHoldReturnFromSeries,
  filterBarsToBacktestWindow,
} from '@/features/backtests/backtest-buy-hold';
import {
  formatDateRangeDdMmYyyy,
} from '@/features/backtests/backtest-date-format';
import {
  PERIOD_PRESET_OPTIONS,
  resolveBacktestWindow,
  type PeriodPreset,
} from '@/features/backtests/backtest-period';
import { barsToChartSeries, CHART_THEME, formatPct, formatPrice } from '@/features/charts/chart-utils';
import { observeStableSize } from '@/features/charts/chart-stable-resize';
import { cn } from '@/lib/utils';

type Props = {
  instrumentId: string;
  symbol: string;
  name?: string | null;
  timeframe: ChartTimeframe | string;
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  /** Hoy simulado (DÍA D). */
  diaD?: string;
};

function PreviewCandleChart({ bars }: { bars: OhlcvBarDto[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      width: Math.max(1, el.clientWidth),
      height: Math.max(220, el.clientHeight || 280),
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
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

    const stop = observeStableSize(el, () => {
      chart.applyOptions({
        width: Math.max(1, el.clientWidth),
        height: Math.max(220, el.clientHeight || 280),
      });
    });

    return () => {
      stop();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart || bars.length < 2) return;
    series.setData(barsToChartSeries(bars));
    chart.timeScale().fitContent();
  }, [bars]);

  return <div ref={containerRef} className="h-full w-full min-h-[220px]" />;
}

export function BacktestInstrumentPreview({
  instrumentId,
  symbol,
  name,
  timeframe,
  periodPreset,
  customDateFrom,
  customDateTo,
  diaD,
}: Props) {
  const window = useMemo(
    () => resolveBacktestWindow(periodPreset, customDateFrom, customDateTo, diaD),
    [periodPreset, customDateFrom, customDateTo, diaD],
  );
  const periodLabel =
    PERIOD_PRESET_OPTIONS.find((o) => o.value === periodPreset)?.label ?? periodPreset;

  const ohlcvQuery = useQuery({
    queryKey: [
      'backtest-instrument-preview',
      instrumentId,
      timeframe,
      window.limit ?? 10_000,
      window.dateFrom ?? '',
      window.dateTo ?? '',
    ],
    queryFn: () =>
      api.getOhlcv(instrumentId, window.limit ?? 10_000, String(timeframe)),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
  });

  const bars = useMemo(
    () => filterBarsToBacktestWindow(ohlcvQuery.data?.data, window),
    [ohlcvQuery.data?.data, window],
  );

  const buyHoldPct = buyHoldReturnFromSeries(bars);
  const first = bars[0];
  const last = bars[bars.length - 1];

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="shrink-0 space-y-1">
        <p className="text-sm font-medium text-foreground">
          {symbol}
          {name ? <span className="font-normal text-muted-foreground"> · {name}</span> : null}
        </p>
        <p className="text-[11px] text-muted-foreground">
          Referencia del periodo (sin estrategia) · {periodLabel} · TF {timeframe}
          {window.dateTo ? ` · hasta ${window.dateTo}` : ''}
        </p>
      </div>

      {ohlcvQuery.isLoading && (
        <p className="text-sm text-muted-foreground">Cargando histórico…</p>
      )}
      {ohlcvQuery.isError && (
        <p className="text-sm text-destructive">
          No se pudo cargar el OHLCV. Sincroniza el valor y reintenta.
        </p>
      )}
      {!ohlcvQuery.isLoading && !ohlcvQuery.isError && bars.length < 2 && (
        <p className="text-sm text-muted-foreground">
          Historial insuficiente en este periodo. Sincroniza OHLCV o amplía el rango.
        </p>
      )}

      {bars.length >= 2 && first && last && (
        <>
          <div className="flex flex-wrap items-end gap-x-6 gap-y-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2.5">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Comprar y mantener
              </p>
              <p
                className={cn(
                  'text-2xl font-semibold tabular-nums',
                  (buyHoldPct ?? 0) >= 0 ? 'text-success' : 'text-destructive',
                )}
              >
                {buyHoldPct != null ? formatPct(buyHoldPct) : '—'}
              </p>
            </div>
            <div className="text-xs text-muted-foreground">
              <p>
                {formatDateRangeDdMmYyyy(first.timestamp, last.timestamp)}
                <span className="text-muted-foreground/80"> · {bars.length} velas</span>
              </p>
              <p className="mt-0.5 tabular-nums">
                {formatPrice(first.close)} → {formatPrice(last.close)}
              </p>
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-hidden rounded-md border border-border/50 bg-background/40">
            <PreviewCandleChart bars={bars} />
          </div>
          <p className="shrink-0 text-[10px] leading-snug text-muted-foreground">
            Solo información: si hubieras comprado en la primera vela y vendido en la última (sin
            costes). Luego compara las estrategias con esta referencia.
          </p>
        </>
      )}
    </div>
  );
}

/** Empty state when no instrument is selected yet. */
export function BacktestResultEmpty() {
  return (
    <div className="space-y-2 text-sm text-muted-foreground">
      <p className="font-medium text-foreground">Sin valor seleccionado</p>
      <p>
        Elige un valor a la izquierda. Verás el gráfico del periodo y comprar-y-mantener; luego{' '}
        <strong className="font-medium text-foreground">Play</strong> (ciclo completo) o{' '}
        <strong className="font-medium text-foreground">Probar + coach</strong>.
      </p>
    </div>
  );
}
