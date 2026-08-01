import type { ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChartIndicatorInstance, ChartInstanceConfig, IndicatorPointDto, OhlcvBarDto } from '@bolsa/shared';
import {
  clampPricePanelHeightPct,
  resolvePricePanelHeightPct,
  resolveSubPanelGridLayout,
  resolveSubPanelWeights,
  serializeSubPanelWeights,
  subPanelFlexPoolHeightPx,
  adjustAdjacentSubPanelWeights,
} from '@bolsa/shared';
import { cn } from '@/lib/utils';
import { PanelResizeHandle } from '@/components/layout/panel-resize-handle';
import { shouldDisablePanelResize } from '@/features/charts/chart-draw-tool-utils';
import { requestChartReflow } from '@/features/charts/chart-utils';
import { ensureChartZoomBridge } from '@/features/charts/chart-time-sync';
import { SubIndicatorPanel } from '@/features/charts/sub-indicator-panel';
import { useUiStore } from '@/stores/ui-store';

interface ChartIndicatorStackProps {
  mainChart: ReactNode;
  chartSyncId: string;
  pricePanelHeightPct?: number;
  onPricePanelHeightPctChange?: (pct: number) => void;
  subIndicators: ChartIndicatorInstance[];
  onSubPanelWeightsChange?: (weights: Record<string, number>) => void;
  bars: OhlcvBarDto[];
  apiIndicators: IndicatorPointDto[];
  chartConfig: ChartInstanceConfig;
  onConfigure: (instanceId: string) => void;
  onToggleHidden: (instanceId: string) => void;
  onDelete: (instanceId: string) => void;
  onMoveSubIndicator: (instanceId: string, direction: 'up' | 'down') => void;
  onSubIndicatorScaleZoom: (instanceId: string, scaleZoom: number) => void;
  className?: string;
}

export function ChartIndicatorStack({
  mainChart,
  chartSyncId,
  pricePanelHeightPct,
  onPricePanelHeightPctChange,
  subIndicators,
  onSubPanelWeightsChange,
  bars,
  apiIndicators,
  chartConfig,
  onConfigure,
  onToggleHidden,
  onDelete,
  onMoveSubIndicator,
  onSubIndicatorScaleZoom,
  className,
}: ChartIndicatorStackProps) {
  const drawTool = useUiStore((s) => s.chartDrawTool);
  const panelResizeDisabled = shouldDisablePanelResize(drawTool);
  const hasSubPanels = subIndicators.length > 0;
  const stackRef = useRef<HTMLDivElement>(null);
  const subScrollRef = useRef<HTMLDivElement>(null);
  const subGridRef = useRef<HTMLDivElement>(null);
  const draggingSubPanelsRef = useRef(false);
  const resolvedPct = resolvePricePanelHeightPct(pricePanelHeightPct);
  const [livePct, setLivePct] = useState(resolvedPct);
  const pendingPct = useRef(resolvedPct);
  const [subGridHeightPx, setSubGridHeightPx] = useState(0);

  const subPanelLayoutKey = useMemo(
    () =>
      subIndicators
        .map(
          (instance) =>
            `${instance.instanceId}:${instance.visible}:${instance.subPanelWeight ?? ''}`,
        )
        .join('|'),
    [subIndicators],
  );

  const resolvedWeights = useMemo(
    () => resolveSubPanelWeights(subIndicators),
    [subPanelLayoutKey, subIndicators],
  );
  const resolvedWeightsKey = useMemo(
    () => serializeSubPanelWeights(resolvedWeights),
    [resolvedWeights],
  );

  const [liveWeights, setLiveWeights] = useState(resolvedWeights);
  const pendingWeights = useRef(resolvedWeights);

  useEffect(() => {
    setLivePct(resolvedPct);
    pendingPct.current = resolvedPct;
  }, [resolvedPct]);

  useEffect(() => {
    if (draggingSubPanelsRef.current) return;
    setLiveWeights(resolvedWeights);
    pendingWeights.current = resolvedWeights;
  }, [resolvedWeightsKey, resolvedWeights]);

  useEffect(() => {
    ensureChartZoomBridge();
  }, []);

  useEffect(() => {
    const viewport = subScrollRef.current;
    if (!viewport || !hasSubPanels) return;
    let raf: number | null = null;
    let lastHeight = 0;
    const observer = new ResizeObserver(() => {
      if (raf != null) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        raf = null;
        const height = Math.round(viewport.getBoundingClientRect().height);
        if (Math.abs(height - lastHeight) < 2) return;
        lastHeight = height;
        setSubGridHeightPx(height);
      });
    });
    observer.observe(viewport);
    const initial = Math.round(viewport.getBoundingClientRect().height);
    lastHeight = initial;
    setSubGridHeightPx(initial);
    return () => {
      if (raf != null) cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [hasSubPanels, subIndicators.length]);

  const subGridLayout = useMemo(
    () => resolveSubPanelGridLayout(subIndicators, liveWeights, subGridHeightPx),
    [subIndicators, liveWeights, subGridHeightPx],
  );

  const adjustPricePanel = useCallback((deltaPx: number) => {
    const height = stackRef.current?.getBoundingClientRect().height ?? 0;
    if (height <= 0) return;
    const deltaPct = (deltaPx / height) * 100;
    const next = clampPricePanelHeightPct(pendingPct.current + deltaPct);
    pendingPct.current = next;
    setLivePct(next);
  }, []);

  const commitPricePanel = useCallback(() => {
    onPricePanelHeightPctChange?.(pendingPct.current);
    requestChartReflow();
  }, [onPricePanelHeightPctChange]);

  const beginSubPanelDrag = useCallback(() => {
    draggingSubPanelsRef.current = true;
  }, []);

  const adjustSubPanelPair = useCallback(
    (upperId: string, lowerId: string, deltaPx: number) => {
      const flexPool = subPanelFlexPoolHeightPx(
        subGridLayout.contentHeightPx || subGridHeightPx,
        subIndicators,
      );
      if (flexPool <= 0) return;
      const deltaPct = (deltaPx / flexPool) * 100;
      const next = adjustAdjacentSubPanelWeights(
        pendingWeights.current,
        upperId,
        lowerId,
        deltaPct,
      );
      if (!next) return;
      pendingWeights.current = next;
      setLiveWeights(new Map(next));
    },
    [subGridHeightPx, subGridLayout.contentHeightPx, subIndicators],
  );

  const commitSubPanelWeights = useCallback(() => {
    draggingSubPanelsRef.current = false;
    const record = Object.fromEntries(pendingWeights.current.entries());
    onSubPanelWeightsChange?.(record);
    requestChartReflow();
  }, [onSubPanelWeightsChange]);

  const subPanelRows: ReactNode[] = [];
  for (let index = 0; index < subIndicators.length; index++) {
    const instance = subIndicators[index]!;
    subPanelRows.push(
      <SubIndicatorPanel
        key={instance.instanceId}
        chartSyncId={chartSyncId}
        instance={instance}
        bars={bars}
        apiIndicators={apiIndicators}
        config={chartConfig}
        fillHeight={instance.visible}
        onConfigure={() => onConfigure(instance.instanceId)}
        onToggleHidden={() => onToggleHidden(instance.instanceId)}
        onDelete={() => onDelete(instance.instanceId)}
        onMoveUp={index > 0 ? () => onMoveSubIndicator(instance.instanceId, 'up') : undefined}
        onMoveDown={
          index < subIndicators.length - 1
            ? () => onMoveSubIndicator(instance.instanceId, 'down')
            : undefined
        }
        scaleZoom={instance.scaleZoom ?? 1}
        onScaleZoomChange={(next) => onSubIndicatorScaleZoom(instance.instanceId, next)}
      />,
    );

    const next = subIndicators[index + 1];
    if (instance.visible && next?.visible) {
      subPanelRows.push(
        <PanelResizeHandle
          key={`${instance.instanceId}-handle`}
          label="Redimensionar entre indicadores"
          orientation="horizontal"
          disabled={panelResizeDisabled}
          onDragStart={beginSubPanelDrag}
          onDrag={(deltaPx) => adjustSubPanelPair(instance.instanceId, next.instanceId, deltaPx)}
          onDragEnd={commitSubPanelWeights}
        />,
      );
    }
  }

  return (
    <div
      ref={stackRef}
      className={cn(
        'min-h-0 flex-1',
        hasSubPanels ? 'grid' : 'flex flex-col',
        className,
      )}
      style={
        hasSubPanels
          ? { gridTemplateRows: `${livePct}fr auto ${100 - livePct}fr` }
          : undefined
      }
    >
      <div
        className={cn(
          'relative min-h-0 w-full min-h-[160px] overflow-hidden [contain:strict]',
          !hasSubPanels && 'min-w-0 flex-1',
        )}
      >
        <div className="relative h-full w-full">{mainChart}</div>
      </div>

      {hasSubPanels && (
        <>
          <PanelResizeHandle
            label="Redimensionar zona de precio e indicadores"
            orientation="horizontal"
            disabled={panelResizeDisabled}
            onDrag={adjustPricePanel}
            onDragEnd={commitPricePanel}
          />
          <div className="flex min-h-0 flex-col overflow-hidden">
            <p
              className="shrink-0 bg-muted/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-muted-foreground"
              title={
                subGridLayout.scrollable
                  ? 'Paneles inferiores. Desplázate para ver todos; arrastra entre ellos para repartir altura.'
                  : 'Paneles inferiores. Arrastra entre ellos para repartir altura.'
              }
            >
              Paneles inferiores
              {subGridLayout.scrollable ? (
                <span className="ml-1 font-normal normal-case text-muted-foreground/80">
                  — desplazar
                </span>
              ) : null}
            </p>
            <div
              ref={subScrollRef}
              className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto"
            >
              <div
                ref={subGridRef}
                className="grid w-full"
                style={{
                  gridTemplateRows: subGridLayout.gridTemplateRows,
                  height: subGridLayout.scrollable
                    ? subGridLayout.contentHeightPx
                    : '100%',
                  minHeight: subGridLayout.scrollable
                    ? subGridLayout.contentHeightPx
                    : '100%',
                }}
              >
                {subPanelRows}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
