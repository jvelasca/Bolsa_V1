/**
 * Niveles del plan operativo sobre el gráfico de Mercado.
 *
 * V1.23 G0: proyección visual.
 * V1.34 B-γ: drag del **stop vigente** (G3 ghost) → Confirm `signedStop` (G4).
 * No muta Position / currentStop. Trail / T1 / T2 / entry no son draggables.
 *
 * @see docs/engineering/diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md
 */

import { useEffect, useRef, useState, type PointerEvent } from "react";
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
import {
  canDragOperationalStop,
  evaluateChartStopDragGeometry,
} from "@/features/charts/chart-stop-drag-policy";
import { commitChartStopDrag } from "@/features/charts/chart-stop-drag-commit";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { cn } from "@/lib/utils";

type AnySeries = ChartMainPriceSeries | ISeriesApi<"Line"> | null;

const GHOST_LINE_ID = "plan-level:stopVigente:ghost";

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

function ghostLineOptions(price: number, valid: boolean) {
  const color = valid ? "#f87171" : "#a8a29e";
  return {
    id: GHOST_LINE_ID,
    price,
    color,
    lineWidth: 2 as const,
    lineStyle: LineStyle.Dashed,
    lineVisible: true,
    axisLabelVisible: true,
    title: valid ? "Stop (preview)" : "Stop inválido",
    axisLabelColor: color,
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
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActive = useSupervisedF3QueueStore((s) => s.setActive);
  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const linesRef = useRef<Map<string, IPriceLine>>(new Map());
  const ghostRef = useRef<IPriceLine | null>(null);
  const seriesRef = useRef<AnySeries>(series);
  seriesRef.current = series;
  const dragRef = useRef<{
    pointerId: number;
    originStop: number;
  } | null>(null);

  const [handleTop, setHandleTop] = useState<number | null>(null);
  const [ghostPrice, setGhostPrice] = useState<number | null>(null);
  const [ghostValid, setGhostValid] = useState(true);
  const [dragging, setDragging] = useState(false);

  const levels =
    chartReady && series && instrumentId
      ? buildOperationalPlanChartLevels({
          plan: context.plan,
          showLevels: context.showsPlanLevels,
          includeTrailing: context.phase === "posicion",
        })
      : [];
  const signature = operationalPlanChartLevelsSignature(levels);
  const stopLevel = levels.find((l) => l.kind === "stopVigente") ?? null;
  const dragAllowed = canDragOperationalStop({
    phase: context.phase,
    showsPlanLevels: context.showsPlanLevels,
    stopPrice: stopLevel?.price ?? null,
  });

  useEffect(() => {
    const lines = linesRef.current;
    return () => {
      removeLines(seriesRef.current, lines);
      if (ghostRef.current) {
        try {
          seriesRef.current?.removePriceLine(ghostRef.current);
        } catch {
          /* ignore */
        }
        ghostRef.current = null;
      }
    };
  }, [series]);

  useEffect(() => {
    const currentSeries = seriesRef.current;
    if (!chartReady || !currentSeries || levels.length === 0) {
      removeLines(currentSeries, linesRef.current);
      setHandleTop(null);
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
    if (stopLevel && !dragging) {
      const y = currentSeries.priceToCoordinate(stopLevel.price);
      setHandleTop(y != null ? Number(y) : null);
    }
    // `signature` resume precios/niveles; evita recrear líneas en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartReady, series, instrumentId, signature, dragging]);

  useEffect(() => {
    const currentSeries = seriesRef.current;
    if (!currentSeries || ghostPrice == null) {
      if (ghostRef.current) {
        try {
          currentSeries?.removePriceLine(ghostRef.current);
        } catch {
          /* ignore */
        }
        ghostRef.current = null;
      }
      return;
    }
    const opts = ghostLineOptions(ghostPrice, ghostValid);
    if (ghostRef.current) {
      try {
        ghostRef.current.applyOptions(opts);
      } catch {
        ghostRef.current = currentSeries.createPriceLine(opts);
      }
    } else {
      ghostRef.current = currentSeries.createPriceLine(opts);
    }
    const y = currentSeries.priceToCoordinate(ghostPrice);
    if (y != null) setHandleTop(Number(y));
  }, [ghostPrice, ghostValid]);

  function clearGhost() {
    setGhostPrice(null);
    setGhostValid(true);
    dragRef.current = null;
    setDragging(false);
    if (ghostRef.current) {
      try {
        seriesRef.current?.removePriceLine(ghostRef.current);
      } catch {
        /* ignore */
      }
      ghostRef.current = null;
    }
  }

  function onPointerDown(e: PointerEvent<HTMLButtonElement>) {
    if (!dragAllowed || !stopLevel || !seriesRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = { pointerId: e.pointerId, originStop: stopLevel.price };
    setDragging(true);
    setGhostPrice(stopLevel.price);
    setGhostValid(true);
  }

  function onPointerMove(e: PointerEvent<HTMLButtonElement>) {
    if (!dragRef.current || dragRef.current.pointerId !== e.pointerId) return;
    const currentSeries = seriesRef.current;
    if (!currentSeries) return;
    const rect = e.currentTarget.parentElement?.getBoundingClientRect();
    if (!rect) return;
    const y = e.clientY - rect.top;
    const price = currentSeries.coordinateToPrice(y);
    if (price == null || !Number.isFinite(price)) return;
    const geometry = evaluateChartStopDragGeometry({
      direction: context.plan.direction,
      entry: context.plan.entry,
      ghostStop: price,
      target1: context.plan.target1,
      target2: context.plan.target2,
    });
    setGhostPrice(Number(price));
    setGhostValid(geometry.ok);
  }

  function onPointerUp(e: PointerEvent<HTMLButtonElement>) {
    if (!dragRef.current || dragRef.current.pointerId !== e.pointerId) return;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
    const finalStop = ghostPrice;
    const instrument = instrumentId;
    clearGhost();
    if (
      finalStop == null ||
      !instrument ||
      !Number.isFinite(finalStop) ||
      Math.abs(finalStop - (stopLevel?.price ?? finalStop)) < 1e-9
    ) {
      // Sin movimiento neto: no abrir Confirm.
      if (stopLevel && seriesRef.current) {
        const y = seriesRef.current.priceToCoordinate(stopLevel.price);
        setHandleTop(y != null ? Number(y) : null);
      }
      return;
    }

    const result = commitChartStopDrag({
      phase: context.phase,
      showsPlanLevels: context.showsPlanLevels,
      direction: context.plan.direction,
      entry: context.plan.entry,
      ghostStop: finalStop,
      target1: context.plan.target1,
      target2: context.plan.target2,
      instrumentId: instrument,
      accountId: context.accountId,
      position: context.position,
      symbol: context.position?.symbol ?? context.study?.symbol ?? null,
      deps: {
        enqueue,
        setActive,
        findQueueItemIdForInstrument: (id) =>
          queueItems.find((q) => q.payload.instrumentId === id)?.id ?? null,
      },
    });

    if (!result.ok && stopLevel && seriesRef.current) {
      const y = seriesRef.current.priceToCoordinate(stopLevel.price);
      setHandleTop(y != null ? Number(y) : null);
    }
  }

  if (levels.length === 0) return null;

  return (
    <div
      className="pointer-events-none absolute inset-0 z-[4]"
      data-testid="chart-operational-plan-levels"
      data-phase={context.phase}
      data-levels={levels.map((level) => level.kind).join(",")}
      data-stop-drag={dragAllowed ? "allowed" : "blocked"}
      aria-hidden={!dragAllowed}
    >
      {dragAllowed && handleTop != null && Number.isFinite(handleTop) ? (
        <button
          type="button"
          className={cn(
            "pointer-events-auto absolute left-2 z-[5] h-4 w-4 -translate-y-1/2 cursor-ns-resize rounded-sm border border-red-500/80 bg-red-500/30",
            dragging && "bg-red-500/60",
            ghostPrice != null &&
              !ghostValid &&
              "border-stone-400 bg-stone-400/40",
          )}
          style={{ top: handleTop }}
          title="Arrastra el stop → Confirmar (firma SEMI)"
          data-testid="chart-stop-drag-handle"
          aria-label="Arrastrar stop vigente"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        />
      ) : null}
    </div>
  );
}
