/**
 * Niveles del plan operativo sobre el gráfico de Mercado (visual only).
 *
 * Hermana de `ChartF3OrderProjectionLayer`: aquí no hay cola F3, se pinta la
 * proyección `OperationalPlanView` del valor activo (entrada, stop vigente,
 * T1, T2 y trailing **sugerido** en estilo advisory).
 *
 * - VIGILAR / DESCUBIERTO no pintan nada (anti-ruido).
 * - Nunca escribe `currentStop` ni firma nada.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md §2
 */

import { useEffect, useRef } from "react";
import {
  LineStyle,
  type IPriceLine,
  type ISeriesApi,
} from "lightweight-charts";
import type { ChartMainPriceSeries } from "@/features/charts/chart-main-series";
import {
  buildOperationalPlanChartLevels,
  operationalPlanChartLevelsSignature,
  type OperationalPlanChartLevel,
} from "@/features/charts/operational-plan-chart-levels";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";

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

function priceLineOptions(level: OperationalPlanChartLevel) {
  return {
    id: level.id,
    price: level.price,
    color: level.color,
    lineWidth: level.width,
    lineStyle: level.style === "dashed" ? LineStyle.Dashed : LineStyle.Solid,
    lineVisible: true,
    axisLabelVisible: true,
    title: level.title,
    axisLabelColor: level.color,
    axisLabelTextColor: "#fafaf9",
  };
}

export function ChartOperationalPlanLevelsLayer({
  series,
  instrumentId,
  chartReady,
}: {
  series: AnySeries;
  instrumentId?: string;
  chartReady: boolean;
}) {
  const context = useInstrumentOperationalContext(instrumentId ?? null);
  const linesRef = useRef<Map<string, IPriceLine>>(new Map());
  const seriesRef = useRef<AnySeries>(series);
  seriesRef.current = series;

  const levels =
    chartReady && series && instrumentId
      ? buildOperationalPlanChartLevels({
          plan: context.plan,
          showLevels: context.showsPlanLevels,
          includeTrailing: context.phase === "posicion",
        })
      : [];
  const signature = operationalPlanChartLevelsSignature(levels);

  useEffect(() => {
    const lines = linesRef.current;
    return () => {
      removeLines(seriesRef.current, lines);
    };
  }, [series]);

  useEffect(() => {
    const currentSeries = seriesRef.current;
    if (!chartReady || !currentSeries || levels.length === 0) {
      removeLines(currentSeries, linesRef.current);
      return;
    }
    const keep = new Set(levels.map((level) => level.id));
    removeLines(currentSeries, linesRef.current, keep);
    for (const level of levels) {
      const opts = priceLineOptions(level);
      const existing = linesRef.current.get(level.id);
      if (existing) {
        try {
          existing.applyOptions(opts);
          continue;
        } catch {
          linesRef.current.delete(level.id);
        }
      }
      try {
        linesRef.current.set(level.id, currentSeries.createPriceLine(opts));
      } catch {
        /* serie destruida entre renders */
      }
    }
    // `signature` resume precios/niveles; evita recrear líneas en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartReady, series, instrumentId, signature]);

  if (levels.length === 0) return null;

  return (
    <div
      className="pointer-events-none absolute inset-0 z-[4]"
      data-testid="chart-operational-plan-levels"
      data-phase={context.phase}
      data-levels={levels.map((level) => level.kind).join(",")}
      aria-hidden
    />
  );
}
