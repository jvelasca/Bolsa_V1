/**
 * Capa de niveles CALCULADOS (S2) sobre el gráfico de Mercado.
 *
 * - Solo pinta `detectado`. Los estados `no_fiable` / `roto` / `en_precio` /
 *   `no_disponible` viven en el panel de lectura, nunca como línea.
 * - Estilo inequívoco: discontinua, `S·calc` / `R·calc` y color propio.
 * - La leyenda declara el hueco (histórico insuficiente, sin pivotes, sin
 *   niveles fiables) en vez de fingir «0 niveles».
 * - La visibilidad es una preferencia local: no toca contrato ni servidor.
 *
 * @see docs/engineering/metodologia-soportes-resistencias-tendencia-2026-11-12.md
 */

import { useEffect, useMemo, useRef } from "react";
import {
  LineStyle,
  type IPriceLine,
  type ISeriesApi,
} from "lightweight-charts";
import {
  MARKET_STRUCTURE_METHOD_LABEL,
  computeMarketStructure,
  type OhlcvBarDto,
} from "@bolsa/shared";
import type { ChartMainPriceSeries } from "@/features/charts/chart-main-series";
import {
  buildMarketStructureChartLevels,
  describeMarketStructureLevels,
  marketStructureChartLevelsSignature,
  type MarketStructureChartLevel,
  type MarketStructurePlanPrice,
} from "@/features/charts/market-structure-chart-levels";
import {
  useMarketStructurePrefs,
  useToggleMarketStructureLevels,
} from "@/features/charts/use-market-structure-prefs";
import { cn } from "@/lib/utils";

type AnySeries = ChartMainPriceSeries | ISeriesApi<"Line"> | null;

function removeLines(
  series: AnySeries,
  lines: Map<string, IPriceLine>,
  keep?: Set<string>,
): void {
  for (const [key, line] of lines) {
    if (keep?.has(key)) continue;
    try {
      series?.removePriceLine(line);
    } catch {
      /* serie ya destruida con el chart */
    }
    lines.delete(key);
  }
}

function priceLineOptions(level: MarketStructureChartLevel) {
  return {
    id: level.id,
    price: level.price,
    color: level.color,
    lineWidth: level.width,
    lineStyle: LineStyle.Dashed,
    lineVisible: true,
    axisLabelVisible: true,
    title: level.title,
    axisLabelColor: level.color,
    axisLabelTextColor: "#fafaf9",
  };
}

export function ChartMarketStructureLevelsLayer({
  series,
  bars,
  chartTimeframe,
  chartReady,
  planLevels,
  className,
}: {
  series: AnySeries;
  bars: readonly OhlcvBarDto[];
  chartTimeframe: string;
  chartReady: boolean;
  /** Entrada / stop / T1 / T2, para declarar coincidencias (no autoriza nada). */
  planLevels?: readonly MarketStructurePlanPrice[];
  className?: string;
}) {
  const { showChartLevels } = useMarketStructurePrefs();
  const setVisible = useToggleMarketStructureLevels();
  const linesRef = useRef<Map<string, IPriceLine>>(new Map());
  const seriesRef = useRef<AnySeries>(series);
  seriesRef.current = series;

  const result = useMemo(
    () => computeMarketStructure({ bars, timeframe: chartTimeframe }),
    [bars, chartTimeframe],
  );
  const levels = useMemo(
    () =>
      buildMarketStructureChartLevels({
        result,
        planLevels: planLevels ?? [],
      }),
    [result, planLevels],
  );
  const summary = useMemo(
    () => describeMarketStructureLevels(result),
    [result],
  );
  const signature = marketStructureChartLevelsSignature(levels);

  // Limpia al desmontar o al cambiar de serie.
  useEffect(() => {
    const lines = linesRef.current;
    return () => {
      removeLines(seriesRef.current, lines);
    };
  }, [series]);

  useEffect(() => {
    const currentSeries = seriesRef.current;
    if (!chartReady || !currentSeries || !showChartLevels || levels.length === 0) {
      removeLines(currentSeries, linesRef.current);
      return;
    }
    const keep = new Set(levels.map((level) => level.id));
    removeLines(currentSeries, linesRef.current, keep);
    for (const level of levels) {
      const options = priceLineOptions(level);
      const existing = linesRef.current.get(level.id);
      if (existing) {
        try {
          existing.applyOptions(options);
          continue;
        } catch {
          linesRef.current.delete(level.id);
        }
      }
      try {
        linesRef.current.set(level.id, currentSeries.createPriceLine(options));
      } catch {
        /* serie destruida entre renders */
      }
    }
    // `signature` resume precios/títulos; evita recrear líneas en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartReady, series, showChartLevels, signature]);

  if (!chartReady || bars.length === 0) return null;

  const drawn = showChartLevels ? levels.length : 0;

  return (
    <div
      className={cn("absolute inset-0 z-[3] pointer-events-none", className)}
      data-testid="chart-market-structure-levels"
      data-method="swing-atr-v1"
      data-measured={summary.measured ? "true" : "false"}
      data-visible={showChartLevels ? "true" : "false"}
      data-levels={levels.map((level) => level.kind).join(",")}
      data-level-count={drawn}
    >
      <div className="pointer-events-auto absolute left-2 top-2 z-20 flex max-w-[240px] flex-wrap items-center gap-1.5 rounded border border-stone-700/70 bg-stone-900/85 px-2 py-1 text-[10px] text-stone-300 shadow">
        <span
          className="font-medium text-stone-200"
          title={`${MARKET_STRUCTURE_METHOD_LABEL} · ${result.window.bars} velas · ${result.window.timeframe}`}
        >
          Niveles calc.
        </span>
        <span className="text-stone-400">{summary.detail}</span>
        {summary.measured ? (
          <span className="text-stone-500 tabular-nums">
            {result.window.bars} velas · {result.window.timeframe}
          </span>
        ) : null}
        <button
          type="button"
          className={cn(
            "rounded border px-1 py-0.5 text-[10px] leading-none",
            showChartLevels
              ? "border-teal-600/70 text-teal-300"
              : "border-stone-600 text-stone-400",
          )}
          aria-pressed={showChartLevels}
          data-testid="chart-market-structure-toggle"
          onClick={() => setVisible(!showChartLevels)}
        >
          {showChartLevels ? "Ocultar" : "Mostrar"}
        </button>
      </div>
    </div>
  );
}
