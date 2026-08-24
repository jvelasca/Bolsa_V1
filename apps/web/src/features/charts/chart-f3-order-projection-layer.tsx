/**
 * U5 — priceLine efímera de propuesta F3 en el gráfico (visual only).
 *
 * - Aparece si el instrumento activo tiene ítem en cola F3 con precio resoluble.
 * - Se limpia al cambiar instrumento, vaciar cola, o quitar el ítem.
 * - Nunca llama confirmOrderIntent / ExecuteTrade; «Firmar» abre el drawer U3.
 */

import { useEffect, useRef, useState } from "react";
import {
  LineStyle,
  type IPriceLine,
  type ISeriesApi,
} from "lightweight-charts";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import {
  F3_ORDER_PROJECTION_LINE_ID,
  resolveF3OrderProjectionForInstrument,
  type F3OrderProjectionView,
} from "@/features/trading/f3-order-projection";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import type { ChartMainPriceSeries } from "@/features/charts/chart-main-series";
import { cn } from "@/lib/utils";

type AnySeries = ChartMainPriceSeries | ISeriesApi<"Line"> | null;

function clearPriceLine(series: AnySeries, line: IPriceLine | null): void {
  if (!series || !line) return;
  try {
    series.removePriceLine(line);
  } catch {
    /* serie ya destruida con el chart */
  }
}

export function ChartF3OrderProjectionLayer({
  series,
  instrumentId,
  chartReady,
  className,
}: {
  series: AnySeries;
  instrumentId?: string;
  chartReady: boolean;
  className?: string;
}) {
  const items = useSupervisedF3QueueStore((s) => s.items);
  const activeId = useSupervisedF3QueueStore((s) => s.activeId);
  const lineRef = useRef<IPriceLine | null>(null);
  const seriesRef = useRef<AnySeries>(series);
  seriesRef.current = series;

  const projection: F3OrderProjectionView | null =
    chartReady && series && instrumentId
      ? resolveF3OrderProjectionForInstrument(items, instrumentId, activeId)
      : null;

  const [cueTop, setCueTop] = useState<number | null>(null);

  // Limpia la línea al destruir / cambiar serie.
  useEffect(() => {
    return () => {
      clearPriceLine(seriesRef.current, lineRef.current);
      lineRef.current = null;
    };
  }, [series]);

  useEffect(() => {
    const currentSeries = seriesRef.current;
    if (!chartReady || !currentSeries || !projection) {
      clearPriceLine(currentSeries, lineRef.current);
      lineRef.current = null;
      setCueTop(null);
      return;
    }

    const opts = {
      id: F3_ORDER_PROJECTION_LINE_ID,
      price: projection.price,
      color: projection.color,
      lineWidth: 1 as const,
      lineStyle: LineStyle.Dashed,
      lineVisible: true,
      axisLabelVisible: true,
      title: projection.label,
      axisLabelColor: projection.color,
      axisLabelTextColor: "#fafaf9",
    };

    if (lineRef.current) {
      try {
        lineRef.current.applyOptions(opts);
      } catch {
        lineRef.current = currentSeries.createPriceLine(opts);
      }
    } else {
      lineRef.current = currentSeries.createPriceLine(opts);
    }

    const y = currentSeries.priceToCoordinate(projection.price);
    setCueTop(y != null ? Number(y) : null);
  }, [
    chartReady,
    projection?.queueItemId,
    projection?.price,
    projection?.label,
    projection?.color,
    series,
    instrumentId,
  ]);

  if (!projection || cueTop == null || !Number.isFinite(cueTop)) {
    return null;
  }

  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 z-[5] overflow-hidden",
        className,
      )}
      data-testid="chart-f3-order-projection"
      data-queue-item={projection.queueItemId}
      data-price={String(projection.price)}
    >
      <button
        type="button"
        className="pointer-events-auto absolute right-12 -translate-y-1/2 rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide shadow-sm transition-colors hover:brightness-95"
        style={{
          top: cueTop,
          borderColor: projection.color,
          backgroundColor: "var(--background, #fff)",
          color: projection.color,
        }}
        title={`${projection.label} — abrir Confirmar (firma SEMI)`}
        data-testid="chart-f3-order-projection-firmar"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          openConfirmDrawer();
        }}
      >
        Firmar
      </button>
    </div>
  );
}
