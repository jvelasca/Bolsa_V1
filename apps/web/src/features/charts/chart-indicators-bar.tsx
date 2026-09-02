/**
 * Zona Indicadores (catálogo) + switch Finalista TOP #1 del valor/TF del gráfico.
 */

import { BarChart3 } from "lucide-react";
import {
  CHART_BAR_ZONE_LABEL_BTN_CLASS,
  CHART_BAR_ZONE_ROW_CLASS,
} from "@/features/charts/chart-bar-zone-styles";
import { ChartFinalistTop1Switch } from "@/features/charts/chart-finalist-top1-switch";
import type { ChartFinalistTop1Scope } from "@/features/charts/chart-finalist-top1-switch";
import { cn } from "@/lib/utils";

export type ChartFinalistTop1Control = {
  checked: boolean;
  disabled?: boolean;
  title?: string;
  scope?: ChartFinalistTop1Scope;
  onCheckedChange: (next: boolean) => void;
};

export function ChartIndicatorsBar({
  onOpenCatalog,
  chartIndicatorCount = 0,
  finalistTop1,
  instrumentId,
  symbol,
  className,
}: {
  onOpenCatalog: () => void;
  chartIndicatorCount?: number;
  /** Switch overlay Finalista TOP #1 (política «todos» o por gráfico). */
  finalistTop1?: ChartFinalistTop1Control;
  instrumentId?: string;
  symbol?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(CHART_BAR_ZONE_ROW_CLASS, "shrink-0", className)}
      title="Catálogo de indicadores y overlay del Finalista TOP #1"
      data-testid="chart-indicators-zone"
      data-instrument-id={instrumentId}
      data-symbol={symbol}
    >
      <button
        type="button"
        title="Catálogo de indicadores: añadir, ocultar y asignar a grupos"
        onClick={onOpenCatalog}
        className={cn(
          CHART_BAR_ZONE_LABEL_BTN_CLASS,
          "inline-flex items-center gap-1.5 pr-1.5",
        )}
      >
        <BarChart3 className="h-3.5 w-3.5 shrink-0 text-primary" />
        <span className="chart-indicators-label-text">Indicadores</span>
        <span className="chart-indicators-label-short">Ind.</span>
        {chartIndicatorCount > 0 && (
          <span className="rounded-full bg-primary/20 px-1.5 py-0 text-[10px] font-semibold tabular-nums text-primary">
            {chartIndicatorCount}
          </span>
        )}
      </button>
      {finalistTop1 ? (
        <ChartFinalistTop1Switch
          checked={finalistTop1.checked}
          disabled={finalistTop1.disabled}
          title={finalistTop1.title}
          scope={finalistTop1.scope ?? "all"}
          onCheckedChange={finalistTop1.onCheckedChange}
        />
      ) : null}
    </div>
  );
}
