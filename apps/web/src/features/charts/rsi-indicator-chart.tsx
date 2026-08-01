import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import type { ChartInstanceConfig, IndicatorPointDto } from '@bolsa/shared';
import { indicatorToLineSeries } from '@/features/charts/chart-utils';
import { cn } from '@/lib/utils';

interface RsiIndicatorChartProps {
  indicators: IndicatorPointDto[];
  config: ChartInstanceConfig;
  className?: string;
}

const MIN_HEIGHT = 72;

export function RsiIndicatorChart({ indicators, config, className }: RsiIndicatorChartProps) {
  const { colors, grid, cursor } = config;
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const rsiRef = useRef<ISeriesApi<'Line'> | null>(null);
  const overboughtRef = useRef<ISeriesApi<'Line'> | null>(null);
  const oversoldRef = useRef<ISeriesApi<'Line'> | null>(null);

  const [layoutReady, setLayoutReady] = useState(false);
  const [chartHeight, setChartHeight] = useState(0);

  const applySeriesData = useCallback(() => {
    if (!rsiRef.current || !chartRef.current) return;
    const series = indicatorToLineSeries(indicators, 'rsi14');
    rsiRef.current.setData(series);
    if (series.length > 0) {
      const refLines = series.map((point) => ({ time: point.time, value: 70 }));
      const refLow = series.map((point) => ({ time: point.time, value: 30 }));
      overboughtRef.current?.setData(refLines);
      oversoldRef.current?.setData(refLow);
      chartRef.current.timeScale().fitContent();
    } else {
      overboughtRef.current?.setData([]);
      oversoldRef.current?.setData([]);
    }
  }, [indicators]);

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const syncLayout = () => {
      const { width, height } = container.getBoundingClientRect();
      const nextHeight = Math.max(MIN_HEIGHT, Math.floor(height));
      setChartHeight(nextHeight);
      setLayoutReady(width > 0 && nextHeight > 0);
    };

    syncLayout();
    const observer = new ResizeObserver(syncLayout);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!layoutReady || !containerRef.current || chartHeight <= 0) return;

    const container = containerRef.current;
    const chart = createChart(container, {
      autoSize: true,
      width: container.clientWidth || undefined,
      height: chartHeight,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: colors.textColor,
      },
      grid: {
        vertLines: { visible: grid.showVertical, color: colors.gridColor },
        horzLines: { visible: grid.showHorizontal, color: colors.gridColor },
      },
      crosshair: {
        mode: cursor.mode === 'magnet' ? CrosshairMode.Magnet : CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: colors.gridColor,
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: colors.gridColor,
        rightOffset: Math.round(grid.rightMarginPct),
        visible: false,
      },
    });

    rsiRef.current = chart.addSeries(LineSeries, {
      color: colors.rsi14Color,
      lineWidth: 2,
      title: 'RSI 14',
      priceScaleId: 'right',
    });

    overboughtRef.current = chart.addSeries(LineSeries, {
      color: 'rgba(239, 68, 68, 0.45)',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceScaleId: 'right',
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    oversoldRef.current = chart.addSeries(LineSeries, {
      color: 'rgba(34, 197, 94, 0.45)',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceScaleId: 'right',
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    chart.priceScale('right').applyOptions({
      autoScale: true,
      scaleMargins: { top: 0.05, bottom: 0.05 },
    });

    chartRef.current = chart;
    applySeriesData();

    const resizeObserver = new ResizeObserver(() => {
      const width = container.clientWidth;
      if (width > 0 && !chart.autoSizeActive()) {
        chart.applyOptions({ width });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      rsiRef.current = null;
      overboughtRef.current = null;
      oversoldRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutReady, chartHeight]);

  useEffect(() => {
    applySeriesData();
  }, [applySeriesData]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.applyOptions({
      height: chartHeight,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: colors.textColor,
      },
      grid: {
        vertLines: { visible: grid.showVertical, color: colors.gridColor },
        horzLines: { visible: grid.showHorizontal, color: colors.gridColor },
      },
    });
    rsiRef.current?.applyOptions({ color: colors.rsi14Color });
  }, [chartHeight, colors, grid]);

  return (
    <div className={cn('flex min-h-0 flex-col border-t border-border bg-muted/10', className)}>
      <div className="flex shrink-0 items-center px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        RSI (14)
      </div>
      <div ref={containerRef} className="min-h-[72px] w-full flex-1" />
    </div>
  );
}
