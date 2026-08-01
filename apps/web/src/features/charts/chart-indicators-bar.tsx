import { BarChart3 } from 'lucide-react';
import {
  CHART_BAR_ZONE_LABEL_BTN_CLASS,
  CHART_BAR_ZONE_ROW_CLASS,
} from '@/features/charts/chart-bar-zone-styles';
import { cn } from '@/lib/utils';

export function ChartIndicatorsBar({
  onOpenCatalog,
  chartIndicatorCount = 0,
  className,
}: {
  onOpenCatalog: () => void;
  chartIndicatorCount?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(CHART_BAR_ZONE_ROW_CLASS, className)}
      title="Catálogo de indicadores, presets y grupos"
    >
      <button
        type="button"
        title="Catálogo de indicadores: añadir, ocultar y asignar a grupos"
        onClick={onOpenCatalog}
        className={cn(
          CHART_BAR_ZONE_LABEL_BTN_CLASS,
          'inline-flex items-center gap-1.5 pr-1.5',
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
    </div>
  );
}
