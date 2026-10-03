/**
 * DÍA-D AUTO · FEEDBACK — curva de R ACUMULADO por valor.
 *
 * Reutiliza `lightweight-charts` (LineSeries, el mismo motor que la curva de patrimonio de
 * backtests). Una línea por instrumento con ciclos medidos; el eje X son los días de la
 * ventana. Nunca se dibuja un punto inventado para un día sin medición.
 */

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import type { components } from "@/api/schema";
import { cn } from "@/lib/utils";

type DiaDFeedbackValueDto = components["schemas"]["DiaDFeedbackValueDto"];

/** Paleta estable: la misma en cada render para no "parpadear" por orden de inserción. */
const LINE_COLORS = [
  "#38bdf8",
  "#f472b6",
  "#facc15",
  "#34d399",
  "#a78bfa",
  "#fb923c",
];

/** Valores con ciclos medidos, ordenados por muestra y expectativa (los más informativos). */
export function selectChartValues(
  values: DiaDFeedbackValueDto[],
): DiaDFeedbackValueDto[] {
  return values
    .filter((value) => value.measuredCycles > 0)
    .sort((a, b) => {
      if (b.measuredCycles !== a.measuredCycles) {
        return b.measuredCycles - a.measuredCycles;
      }
      return (b.expectancyR ?? 0) - (a.expectancyR ?? 0);
    })
    .slice(0, LINE_COLORS.length);
}

/** R acumulado por día: los días sin ciclo NO aportan punto (no se inventa un valor). */
export function buildCumulativeRPoints(
  value: DiaDFeedbackValueDto,
  days: string[],
): Array<{ time: Time; value: number }> {
  const points: Array<{ time: Time; value: number }> = [];
  let total = 0;
  for (const day of days) {
    const cell = value.byDay?.[day];
    if (!cell || cell.cycles === 0 || cell.realizedR == null) {
      continue;
    }
    total += cell.realizedR;
    points.push({ time: day as Time, value: total });
  }
  return points;
}

export function DiaDAutoFeedbackChart({
  values,
  days,
  className,
}: {
  values: DiaDFeedbackValueDto[];
  days: string[];
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const selected = selectChartValues(values);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || selected.length === 0) return undefined;

    const chart = createChart(container, {
      width: Math.max(1, container.clientWidth),
      height: 240,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.12)" },
        horzLines: { color: "rgba(148, 163, 184, 0.12)" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: {
        borderVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      crosshair: { mode: CrosshairMode.Magnet },
      handleScroll: false,
      handleScale: false,
    });
    chartRef.current = chart;

    selected.forEach((value, index) => {
      const series = chart.addSeries(LineSeries, {
        color: LINE_COLORS[index % LINE_COLORS.length],
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(buildCumulativeRPoints(value, days));
    });

    chart.timeScale().fitContent();
    return () => {
      chart.remove();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- remount on data identity only
  }, [values, days]);

  if (selected.length === 0) {
    return (
      <p
        className="text-[11px] text-muted-foreground"
        data-testid="dia-d-auto-feedback-chart-empty"
      >
        Sin valores con ciclos medidos en esta ventana.
      </p>
    );
  }

  return (
    <div
      className={cn("space-y-1", className)}
      data-testid="dia-d-auto-feedback-chart"
    >
      <div
        ref={containerRef}
        className="w-full overflow-hidden rounded-lg border border-border bg-card/40"
      />
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground">
        {selected.map((value, index) => (
          <span key={value.symbol} className="inline-flex items-center gap-1">
            <span
              className="inline-block h-1.5 w-3 rounded-full"
              style={{
                backgroundColor: LINE_COLORS[index % LINE_COLORS.length],
              }}
            />
            <span className="font-mono">{value.symbol}</span>
            <span className="tabular-nums">
              {value.expectancyR == null
                ? "NO MEDIDO"
                : `${value.expectancyR > 0 ? "+" : ""}${value.expectancyR.toFixed(2)}R`}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
