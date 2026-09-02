import type { ReactNode } from "react";

import type {
  ChartTimeframe,
  ChartToolbarGlobalConfig,
  InstrumentDataStatusDto,
} from "@bolsa/shared";
import { PanelRight, Settings2 } from "lucide-react";

import { ChartAnalysisScoreButtons } from "@/features/charts/chart-analysis-score-buttons";
import { ChartDataStatusBadge } from "@/features/charts/chart-data-status-badge";
import {
  ChartIndicatorsBar,
  type ChartFinalistTop1Control,
} from "@/features/charts/chart-indicators-bar";
import { ChartNewChartTemplatePinButton } from "@/features/charts/chart-new-chart-template-pin-button";
import { ChartQuickTradeButtons } from "@/features/charts/chart-quick-trade-buttons";
import {
  CHART_TOOLBAR_EMBEDDED_CLASS,
  CHART_TOOLBAR_SECTION_DIVIDER,
  CHART_TOOLBAR_ZONE_BLOCK,
  CHART_TOOLBAR_ZONE_PAD,
} from "@/features/charts/chart-bar-zone-styles";
import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";

function ToolbarZoneRail({
  zones,
  className,
}: {
  zones: ReactNode[];
  className?: string;
}) {
  if (zones.length === 0) return null;

  return (
    <div className={cn("flex min-w-0 flex-wrap items-center", className)}>
      {zones.map((zone, index) => (
        <div key={index} className="flex min-w-0 max-w-full items-center">
          {index > 0 && (
            <div className={CHART_TOOLBAR_SECTION_DIVIDER} aria-hidden />
          )}
          {zone}
        </div>
      ))}
    </div>
  );
}

interface ChartToolbarGlobalBarProps {
  config: ChartToolbarGlobalConfig;
  symbol: string;
  timeframe: ChartTimeframe;
  instrumentId?: string;
  barsLoaded?: number;
  chartIndicatorCount?: number;
  chartInspectorOpen: boolean;
  dataStatus?: InstrumentDataStatusDto;
  dataSyncing?: boolean;
  canTrade?: boolean;
  onOpenIndicatorsCatalog: () => void;
  /** Switch Finalista TOP #1 → indicadores en el gráfico (zona Indicadores). */
  finalistTop1?: ChartFinalistTop1Control;
  onToggleChartInspector: () => void;
  onQuickBuy: () => void;
  onQuickSell: () => void;
  onOpenSettings: () => void;
  onSyncData?: () => void;
  className?: string;
}

export function ChartToolbarGlobalBar({
  config,
  symbol,
  timeframe,
  instrumentId,
  barsLoaded = 0,
  chartIndicatorCount = 0,
  chartInspectorOpen,
  dataStatus,
  dataSyncing,
  canTrade,
  onOpenIndicatorsCatalog,
  finalistTop1,
  onToggleChartInspector,
  onQuickBuy,
  onQuickSell,
  onOpenSettings,
  onSyncData,
  className,
}: ChartToolbarGlobalBarProps) {
  const { visibility, appearance } = config;
  const wrapRows = true;

  const barStyle =
    appearance.globalBarBackground &&
    appearance.globalBarBackground !== "transparent"
      ? { backgroundColor: appearance.globalBarBackground }
      : undefined;

  const zoneBlock = (node: ReactNode) => (
    <div className={cn(CHART_TOOLBAR_ZONE_BLOCK, CHART_TOOLBAR_ZONE_PAD)}>
      {node}
    </div>
  );

  const mainZones: ReactNode[] = [];
  const actionZones: ReactNode[] = [];

  if (visibility.indicators) {
    mainZones.push(
      zoneBlock(
        <div className="flex shrink-0 items-center gap-2">
          <ChartIndicatorsBar
            onOpenCatalog={onOpenIndicatorsCatalog}
            chartIndicatorCount={chartIndicatorCount}
            finalistTop1={finalistTop1}
            instrumentId={instrumentId}
            symbol={symbol}
            className={CHART_TOOLBAR_EMBEDDED_CLASS}
          />
          <ChartNewChartTemplatePinButton className="shrink-0" />
        </div>,
      ),
    );
  }

  if (visibility.tradeButtons && canTrade) {
    mainZones.push(
      zoneBlock(
        <ChartQuickTradeButtons onBuy={onQuickBuy} onSell={onQuickSell} />,
      ),
    );
  }

  if (visibility.dataStatus) {
    mainZones.push(
      zoneBlock(
        <ChartDataStatusBadge
          status={dataStatus}
          syncing={dataSyncing}
          timeframe={timeframe}
          barsLoaded={barsLoaded}
          instrumentId={instrumentId}
          symbol={symbol}
          onSync={onSyncData}
          className="shrink-0"
        />,
      ),
    );
  }

  if (visibility.chartInspector) {
    mainZones.push(
      zoneBlock(
        <button
          type="button"
          title={
            chartInspectorOpen
              ? "Ocultar inspector de gráficos"
              : "Mostrar inspector de gráficos"
          }
          onClick={onToggleChartInspector}
          className={cn(
            "inline-flex h-[1.375rem] shrink-0 items-center rounded px-0.5 hover:bg-accent",
            chartInspectorOpen && "bg-accent text-primary",
          )}
        >
          <PanelRight className="h-3.5 w-3.5" />
        </button>,
      ),
    );
  }

  if (visibility.analysisScores && instrumentId) {
    actionZones.push(
      zoneBlock(<ChartAnalysisScoreButtons instrumentId={instrumentId} />),
    );
  }

  if (visibility.settingsButton) {
    actionZones.push(
      zoneBlock(
        <IconButton
          icon={Settings2}
          title="Configuración de la barra del workspace"
          onClick={onOpenSettings}
          className="shrink-0"
        />,
      ),
    );
  }

  if (mainZones.length === 0 && actionZones.length === 0) return null;

  return (
    <div
      className={cn(
        "chart-toolbar-global-stack min-h-[1.75rem] shrink-0 rounded-md border border-border bg-muted/15",
        wrapRows
          ? "chart-toolbar--wrap chart-toolbar-global--adaptive"
          : "chart-toolbar--scroll",
        className,
      )}
      style={barStyle}
    >
      <ToolbarZoneRail
        zones={mainZones}
        className="chart-toolbar-global-main min-w-0 flex-1"
      />
      {actionZones.length > 0 && (
        <>
          <div className="chart-toolbar-global-rail-break" aria-hidden />
          <ToolbarZoneRail
            zones={actionZones}
            className="chart-toolbar-global-actions shrink-0"
          />
        </>
      )}
    </div>
  );
}
