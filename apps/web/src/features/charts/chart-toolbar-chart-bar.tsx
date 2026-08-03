import type { ReactNode } from 'react';

import type {
  ChartInspectorBarShortcutId,
  ChartTimeframe,
  ChartSeriesType,
  IndicatorTemplate,
  InstrumentDto,
  OhlcvBarDto,
  ResolvedChartToolbarChart,
} from '@bolsa/shared';
import {
  CHART_INSPECTOR_BAR_SHORTCUT_BAR_TITLES,
} from '@bolsa/shared';
import {
  ChartCandlestick,
  ExternalLink,
  Info,
  Layers,
  MousePointer2,
  Palette,
  Settings2,
  Shapes,
  type LucideIcon,
} from 'lucide-react';

import { ChartIndicatorTemplateZone } from '@/features/charts/chart-indicator-template-zone';
import { ChartFinalistTop1Switch } from '@/features/charts/chart-finalist-top1-switch';
import type { ChartFinalistTop1Control } from '@/features/charts/chart-indicators-bar';
import { ChartCursorZone } from '@/features/charts/chart-cursor-zone';
import {
  inspectorNavigateKey,
  type ChartInspectorNavigateInput,
} from '@/features/charts/chart-inspector-nav';
import { inspectorBarShortcutNavigate } from '@/features/charts/chart-inspector-bar-shortcut-nav';
import { ChartInspectorShortcutButton } from '@/features/charts/chart-inspector-shortcut-button';
import { ChartInstrumentAiButton } from '@/features/charts/chart-instrument-ai-button';
import { ChartInstrumentZone } from '@/features/charts/chart-instrument-zone';
import { instrumentForQuickTrade } from '@/features/charts/chart-quick-trade-buttons';
import { ChartSeriesTypeZone } from '@/features/charts/chart-series-type-zone';
import { ChartTimeframeBar } from '@/features/charts/chart-timeframe-bar';
import { chartTradingViewUrl } from '@/features/charts/chart-trading-view-url';
import { useInspectorBarShortcutFavorites } from '@/features/charts/use-inspector-bar-shortcut-favorites';
import {
  CHART_TOOLBAR_EMBEDDED_CLASS,
  CHART_TOOLBAR_SECTION_DIVIDER,
  CHART_TOOLBAR_ZONE_BLOCK,
  CHART_TOOLBAR_ZONE_PAD,
} from '@/features/charts/chart-bar-zone-styles';
import { IconButton } from '@/components/ui/icon-button';
import { useTradingUiStore } from '@/stores/trading-ui-store';
import { useUiStore } from '@/stores/ui-store';
import { useWorkspaceStore } from '@/stores/workspace-store';
import { cn } from '@/lib/utils';

const INSPECTOR_SHORTCUT_ICONS: Record<ChartInspectorBarShortcutId, LucideIcon> = {
  layers: Layers,
  series: ChartCandlestick,
  objects: Shapes,
  styles: Palette,
  context: MousePointer2,
};

interface ChartToolbarChartBarProps {
  resolved: ResolvedChartToolbarChart;
  chartSyncId: string;
  timeframe: ChartTimeframe;
  onTimeframeChange: (timeframe: ChartTimeframe) => void;
  seriesType: ChartSeriesType;
  onSeriesTypeChange: (seriesType: ChartSeriesType) => void;
  indicatorTemplates: IndicatorTemplate[];
  activeIndicatorTemplateId?: string | null;
  onApplyIndicatorTemplate: (templateId: string) => boolean;
  /** Switch Finalista TOP #1 en la zona de indicadores del gráfico en uso. */
  finalistTop1?: ChartFinalistTop1Control;
  instrument?: InstrumentDto;
  instrumentId?: string;
  symbol: string;
  yahooSymbol?: string;
  listLabel?: string;
  bars: OhlcvBarDto[];
  overlayIndicatorCount?: number;
  subIndicatorCount?: number;
  drawingCount?: number;
  onToggleInspectorShortcut: (target: ChartInspectorNavigateInput) => void;
  onOpenSettings: () => void;
  className?: string;
}

function ToolbarZoneRail({
  zones,
  className,
}: {
  zones: ReactNode[];
  className?: string;
}) {
  if (zones.length === 0) return null;

  return (
    <div className={cn('flex min-w-0 flex-wrap items-center', className)}>
      {zones.map((zone, index) => (
        <div key={index} className="flex min-w-0 max-w-full items-center">
          {index > 0 && <div className={CHART_TOOLBAR_SECTION_DIVIDER} aria-hidden />}
          {zone}
        </div>
      ))}
    </div>
  );
}

function inspectorShortcutBadge(
  id: ChartInspectorBarShortcutId,
  overlayIndicatorCount: number,
  subIndicatorCount: number,
  drawingCount: number,
): number | undefined {
  if (id === 'layers') {
    const total = overlayIndicatorCount + subIndicatorCount;
    return total > 0 ? total : undefined;
  }
  if (id === 'objects') {
    return drawingCount > 0 ? drawingCount : undefined;
  }
  return undefined;
}

function isLayersShortcutActive(activeShortcutKey: string | null): boolean {
  if (!activeShortcutKey) return false;
  return (
    activeShortcutKey ===
      inspectorNavigateKey({
        mode: 'config',
        configSection: 'layers',
        layerSection: 'overlay',
      }) ||
    activeShortcutKey ===
      inspectorNavigateKey({ mode: 'config', configSection: 'layers', layerSection: 'sub' })
  );
}

/** Barra de datos del gráfico activo: Escala, Valor, Cursor y atajos al inspector (solo favoritos). */
export function ChartToolbarChartBar({
  resolved,
  chartSyncId,
  timeframe,
  onTimeframeChange,
  seriesType,
  onSeriesTypeChange,
  indicatorTemplates,
  activeIndicatorTemplateId,
  onApplyIndicatorTemplate,
  finalistTop1,
  instrument,
  instrumentId,
  symbol,
  yahooSymbol,
  listLabel,
  bars,
  overlayIndicatorCount = 0,
  subIndicatorCount = 0,
  drawingCount = 0,
  onToggleInspectorShortcut,
  onOpenSettings,
  className,
}: ChartToolbarChartBarProps) {
  const { visibility, layout, chartBarBackground } = resolved;
  const wrapRows = layout.wrapRows;
  const inspectorOpen = useWorkspaceStore((s) => s.workspace.layout.chartInspectorOpen ?? false);
  const activeShortcutKey = useUiStore((s) => s.chartInspectorActiveShortcutKey);
  const openInfoDialog = useTradingUiStore((s) => s.openInfoDialog);
  const { favorites: inspectorShortcutFavorites } = useInspectorBarShortcutFavorites();

  const isShortcutActive = (target: ChartInspectorNavigateInput) =>
    inspectorOpen && activeShortcutKey === inspectorNavigateKey(target);

  const barStyle =
    chartBarBackground && chartBarBackground !== 'transparent'
      ? { backgroundColor: chartBarBackground }
      : undefined;

  const showTimeframe = visibility.timeframe || visibility.timeframeZoom;
  const showSeriesZone = visibility.seriesZone;
  const showIndicatorTemplateZone = visibility.indicatorTemplateZone;
  const showInstrumentZone = visibility.instrumentZone;
  const showCursorZone = visibility.cursorZone;
  const zoneBlock = (node: ReactNode, zoneClassName?: string) => (
    <div className={cn(CHART_TOOLBAR_ZONE_BLOCK, CHART_TOOLBAR_ZONE_PAD, zoneClassName)}>{node}</div>
  );

  const dataZones: ReactNode[] = [];

  if (showTimeframe) {
    dataZones.push(
      zoneBlock(
        <ChartTimeframeBar
          chartSyncId={chartSyncId}
          timeframe={timeframe}
          onTimeframeChange={onTimeframeChange}
          showTimeframe={visibility.timeframe}
          showZoom={visibility.timeframeZoom}
          className={CHART_TOOLBAR_EMBEDDED_CLASS}
        />,
        'chart-toolbar-data-zone',
      ),
    );
  }

  if (showSeriesZone) {
    dataZones.push(
      zoneBlock(
        <ChartSeriesTypeZone
          seriesType={seriesType}
          onSeriesTypeChange={onSeriesTypeChange}
          className={CHART_TOOLBAR_EMBEDDED_CLASS}
        />,
        'chart-toolbar-data-zone',
      ),
    );
  }

  if (showIndicatorTemplateZone || finalistTop1) {
    dataZones.push(
      zoneBlock(
        <div className="flex shrink-0 items-center gap-2">
          {showIndicatorTemplateZone ? (
            <ChartIndicatorTemplateZone
              templates={indicatorTemplates}
              activeTemplateId={activeIndicatorTemplateId}
              onApplyTemplate={onApplyIndicatorTemplate}
              className={CHART_TOOLBAR_EMBEDDED_CLASS}
            />
          ) : null}
          {finalistTop1 ? (
            <ChartFinalistTop1Switch
              checked={finalistTop1.checked}
              disabled={finalistTop1.disabled}
              title={finalistTop1.title}
              onCheckedChange={finalistTop1.onCheckedChange}
              className={CHART_TOOLBAR_EMBEDDED_CLASS}
            />
          ) : null}
        </div>,
        'chart-toolbar-data-zone shrink-0',
      ),
    );
  }

  if (showInstrumentZone) {
    dataZones.push(
      zoneBlock(
        <ChartInstrumentZone instrument={instrument} listLabel={listLabel} />,
        'chart-toolbar-data-zone',
      ),
    );
  }

  if (visibility.tradingView) {
    dataZones.push(
      zoneBlock(
        <a
          href={chartTradingViewUrl(symbol, yahooSymbol)}
          target="_blank"
          rel="noreferrer"
          title="Abrir en TradingView"
          className="inline-flex h-[1.375rem] shrink-0 items-center rounded px-0.5 text-muted-foreground hover:bg-accent hover:text-primary"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>,
        'chart-toolbar-data-zone shrink-0',
      ),
    );
  }

  if (showCursorZone) {
    dataZones.push(
      zoneBlock(
        <ChartCursorZone instrumentId={instrumentId} bars={bars} />,
        'chart-toolbar-data-zone chart-toolbar-cursor-zone',
      ),
    );
  }

  if (visibility.instrumentInfo) {
    dataZones.push(
      zoneBlock(
        <IconButton
          icon={Info}
          title="Información del valor"
          disabled={!instrument}
          onClick={() => {
            if (!instrument) return;
            openInfoDialog(instrumentForQuickTrade(instrument, bars));
          }}
          className="shrink-0"
        />,
        'chart-toolbar-data-zone shrink-0',
      ),
    );
  }

  if (visibility.instrumentAi) {
    dataZones.push(
      zoneBlock(
        <ChartInstrumentAiButton
          instrumentId={instrumentId ?? instrument?.id}
          symbol={symbol}
          className="shrink-0"
        />,
        'chart-toolbar-data-zone shrink-0',
      ),
    );
  }

  const actionZones: ReactNode[] = [];

  if (inspectorShortcutFavorites.length > 0) {
    actionZones.push(
      zoneBlock(
        <div className="flex shrink-0 items-center gap-1" title="Atajos al inspector (favoritos)">
          {inspectorShortcutFavorites.map((shortcutId) => {
            const Icon = INSPECTOR_SHORTCUT_ICONS[shortcutId];
            const navigate = inspectorBarShortcutNavigate(shortcutId);
            const active =
              shortcutId === 'layers'
                ? inspectorOpen && isLayersShortcutActive(activeShortcutKey)
                : isShortcutActive(navigate);
            return (
              <ChartInspectorShortcutButton
                key={shortcutId}
                icon={Icon}
                title={CHART_INSPECTOR_BAR_SHORTCUT_BAR_TITLES[shortcutId]}
                badge={inspectorShortcutBadge(
                  shortcutId,
                  overlayIndicatorCount,
                  subIndicatorCount,
                  drawingCount,
                )}
                active={active}
                onClick={() => onToggleInspectorShortcut(navigate)}
              />
            );
          })}
        </div>,
        'shrink-0',
      ),
    );
  }

  if (visibility.settingsButton) {
    actionZones.push(
      zoneBlock(
        <IconButton
          icon={Settings2}
          title="Configuración de la barra de datos del gráfico"
          onClick={onOpenSettings}
          className="shrink-0"
        />,
      ),
    );
  }

  if (dataZones.length === 0 && actionZones.length === 0) return null;

  return (
    <div
      className={cn(
        'chart-toolbar-chart-stack min-h-[1.75rem] shrink-0 rounded-md border border-border bg-muted/10',
        wrapRows ? 'chart-toolbar--wrap chart-toolbar-chart--adaptive' : 'chart-toolbar--scroll',
        className,
      )}
      style={barStyle}
    >
      <ToolbarZoneRail zones={dataZones} className="chart-toolbar-chart-data min-w-0 flex-1" />
      {actionZones.length > 0 && (
        <>
          <div className="chart-toolbar-chart-rail-break" aria-hidden />
          <ToolbarZoneRail zones={actionZones} className="chart-toolbar-chart-actions shrink-0" />
        </>
      )}
    </div>
  );
}
