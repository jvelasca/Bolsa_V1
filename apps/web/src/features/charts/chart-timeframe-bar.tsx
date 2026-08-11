import {
  CHART_TIMEFRAME_MENU_GROUPS,
  CHART_TIMEFRAME_OPTIONS,
  findChartTimeframeOption,
  type ChartTimeframe,
} from "@bolsa/shared";
import { Clock, Maximize2, ZoomIn, ZoomOut } from "lucide-react";

import { ChartBarZonePicker } from "@/features/charts/chart-bar-zone-picker";
import { ChartBarZoneIconAnchor } from "@/features/charts/chart-bar-zone-rail-button";
import {
  CHART_BAR_ZONE_ROW_CLASS,
  CHART_BAR_ZONE_SCROLL_ROW_CLASS,
} from "@/features/charts/chart-bar-zone-styles";
import { requestChartZoom } from "@/features/charts/chart-utils";
import { useChartTimeframeFavorites } from "@/features/charts/use-chart-timeframe-favorites";
import { cn } from "@/lib/utils";

const TIMEFRAME_OPTIONS = Object.fromEntries(
  CHART_TIMEFRAME_OPTIONS.map((option) => [
    option.id,
    { id: option.id, label: option.label, hint: option.hint ?? option.label },
  ]),
) as Record<
  ChartTimeframe,
  { id: ChartTimeframe; label: string; hint: string }
>;

function ChartTimeframeZoomControls({ chartSyncId }: { chartSyncId?: string }) {
  return (
    <div className="flex h-[1.375rem] shrink-0 items-center gap-0.5 pl-0.5">
      <button
        type="button"
        title="Alejar"
        className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        onClick={() => requestChartZoom("out", chartSyncId)}
      >
        <ZoomOut className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        title="Acercar"
        className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        onClick={() => requestChartZoom("in", chartSyncId)}
      >
        <ZoomIn className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        title="Ajustar a ventana"
        className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        onClick={() => requestChartZoom("reset", chartSyncId)}
      >
        <Maximize2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function ChartTimeframeBar({
  chartSyncId,
  timeframe,
  onTimeframeChange,
  showTimeframe = true,
  showZoom = true,
  className,
}: {
  chartSyncId?: string;
  timeframe: ChartTimeframe;
  onTimeframeChange: (timeframe: ChartTimeframe) => void;
  showTimeframe?: boolean;
  showZoom?: boolean;
  className?: string;
}) {
  const { favorites, toggleFavorite, isFavorite } =
    useChartTimeframeFavorites();

  const zoomControls = showZoom ? (
    <ChartTimeframeZoomControls chartSyncId={chartSyncId} />
  ) : null;

  if (!showTimeframe) {
    return zoomControls ? (
      <div
        className={cn(CHART_BAR_ZONE_ROW_CLASS, className)}
        title="Zoom del gráfico"
      >
        <ChartBarZoneIconAnchor
          icon={Clock}
          title="Escala"
          hint="Zoom del gráfico"
          showMenu={false}
          onOpenMenu={() => {}}
        />
        <div className={CHART_BAR_ZONE_SCROLL_ROW_CLASS}>{zoomControls}</div>
      </div>
    ) : null;
  }

  return (
    <ChartBarZonePicker
      zoneIcon={Clock}
      zoneTitle="Escala"
      zoneHint="Resolución temporal y zoom. Icono muestra la escala activa; estrella = chip opcional."
      activeId={timeframe}
      favorites={favorites}
      menuGroups={CHART_TIMEFRAME_MENU_GROUPS}
      options={TIMEFRAME_OPTIONS}
      isFavorite={isFavorite}
      onToggleFavorite={toggleFavorite}
      onSelectOption={onTimeframeChange}
      getButtonLabel={(id) => findChartTimeframeOption(id).shortLabel}
      isOptionDisabled={(id) => !findChartTimeframeOption(id).dataAvailable}
      inlineTail={zoomControls}
      className={className}
    />
  );
}
