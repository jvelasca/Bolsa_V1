import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  MAX_LISTS_WIDTH_PCT,
  MIN_LISTS_WIDTH_PCT,
  MIN_OPERATIONS_HEIGHT_PCT,
  MAX_OPERATIONS_HEIGHT_PCT,
  MIN_OPERATIVA_WIDTH_PCT,
  MAX_OPERATIVA_WIDTH_PCT,
  useTradingLayoutStore,
} from "@/stores/trading-layout-store";
import { DockZone } from "@/components/layout/dock-zone";
import { PanelResizeHandle } from "@/components/layout/panel-resize-handle";
import { WatchlistPanel } from "@/features/trading/lists-tab/watchlist-panel";
import { ChartsZone } from "@/features/trading/charts-zone";
import { OperationsPanel } from "@/features/trading/operations-panel";
import { TradingOperativaPanel } from "@/features/trading/trading-operativa-panel";
import { HoyCommandStrip } from "@/features/trading/hoy-command-strip";
import { useChartListMembershipSync } from "@/features/trading/lists-tab/use-chart-list-membership-sync";
import { useChartVisualizationSync } from "@/features/trading/lists-tab/use-chart-visualization-sync";

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function pxToPct(px: number, total: number) {
  return total > 0 ? (px / total) * 100 : 0;
}

/**
 * Mesa TRADING (ADR-019):
 * columna izq. = Watchlist | Gráfico + Operaciones;
 * columna der. = Operativa a altura completa (hasta TradingStatusBar).
 * Verificar D→hoy vive en LAB / Backtesting.
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */
export function TradingLayout({ children }: { children: ReactNode }) {
  useChartListMembershipSync();
  useChartVisualizationSync();
  const containerRef = useRef<HTMLDivElement>(null);
  const leftColumnRef = useRef<HTMLDivElement>(null);
  const layout = useTradingLayoutStore();

  const [liveListsPct, setLiveListsPct] = useState(layout.listsWidthPct);
  const [liveOpsPct, setLiveOpsPct] = useState(layout.operationsHeightPct);
  const [liveOperativaPct, setLiveOperativaPct] = useState(
    layout.operativaWidthPct,
  );
  const pendingLists = useRef(layout.listsWidthPct);
  const pendingOps = useRef(layout.operationsHeightPct);
  const pendingOperativa = useRef(layout.operativaWidthPct);

  useEffect(() => {
    setLiveListsPct(layout.listsWidthPct);
    pendingLists.current = layout.listsWidthPct;
  }, [layout.listsWidthPct]);

  useEffect(() => {
    setLiveOpsPct(layout.operationsHeightPct);
    pendingOps.current = layout.operationsHeightPct;
  }, [layout.operationsHeightPct]);

  useEffect(() => {
    setLiveOperativaPct(layout.operativaWidthPct);
    pendingOperativa.current = layout.operativaWidthPct;
  }, [layout.operativaWidthPct]);

  const adjustLists = useCallback((deltaPx: number) => {
    const width = leftColumnRef.current?.getBoundingClientRect().width ?? 0;
    if (width <= 0) return;
    const next = clamp(
      pendingLists.current + pxToPct(deltaPx, width),
      MIN_LISTS_WIDTH_PCT,
      MAX_LISTS_WIDTH_PCT,
    );
    pendingLists.current = next;
    setLiveListsPct(next);
  }, []);

  const adjustOps = useCallback((deltaPx: number) => {
    const height = leftColumnRef.current?.getBoundingClientRect().height ?? 0;
    if (height <= 0) return;
    const next = clamp(
      pendingOps.current - pxToPct(deltaPx, height),
      MIN_OPERATIONS_HEIGHT_PCT,
      MAX_OPERATIONS_HEIGHT_PCT,
    );
    pendingOps.current = next;
    setLiveOpsPct(next);
  }, []);

  const adjustOperativa = useCallback((deltaPx: number) => {
    const width = containerRef.current?.getBoundingClientRect().width ?? 0;
    if (width <= 0) return;
    // Drag handle is to the left of Operativa: dragging right grows Operativa.
    const next = clamp(
      pendingOperativa.current - pxToPct(deltaPx, width),
      MIN_OPERATIVA_WIDTH_PCT,
      MAX_OPERATIVA_WIDTH_PCT,
    );
    pendingOperativa.current = next;
    setLiveOperativaPct(next);
  }, []);

  if (layout.listsMaximized && layout.listsOpen) {
    return (
      <div
        ref={containerRef}
        className="flex min-h-0 flex-1 flex-col overflow-hidden"
      >
        <DockZone
          title="Watchlist"
          open
          maximized
          onClose={layout.toggleLists}
          onToggleMaximize={layout.maximizeLists}
          className="flex-1"
        >
          <WatchlistPanel />
        </DockZone>
      </div>
    );
  }

  if (layout.operationsMaximized && layout.operationsOpen) {
    return (
      <div
        ref={containerRef}
        className="flex min-h-0 flex-1 flex-col overflow-hidden"
      >
        <DockZone
          title="Operaciones"
          open
          maximized
          onClose={layout.toggleOperations}
          onToggleMaximize={layout.maximizeOperations}
          className="flex-1"
        >
          <OperationsPanel />
        </DockZone>
      </div>
    );
  }

  const showLists =
    layout.listsOpen && (layout.listsMaximized || !layout.chartsMaximized);
  const showCharts = true;
  const splitTop =
    showLists &&
    showCharts &&
    !layout.listsMaximized &&
    !layout.chartsMaximized;
  const showOperativa = layout.operativaOpen;

  return (
    <div
      ref={containerRef}
      className="flex min-h-0 flex-1 flex-col overflow-hidden"
    >
      <HoyCommandStrip />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div
          ref={leftColumnRef}
          className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden"
        >
          <div className="flex min-h-0 flex-1 overflow-hidden">
            {showLists && (
              <>
                <DockZone
                  title="Watchlist"
                  open
                  maximized={layout.listsMaximized}
                  onClose={layout.toggleLists}
                  onToggleMaximize={layout.maximizeLists}
                  className={splitTop ? "shrink-0" : "shrink-0 border-r"}
                  style={
                    splitTop
                      ? {
                          width: `${clamp(liveListsPct, MIN_LISTS_WIDTH_PCT, MAX_LISTS_WIDTH_PCT)}%`,
                          minWidth: "min(240px, 40vw)",
                        }
                      : { flex: 1, minWidth: "min(240px, 40vw)" }
                  }
                >
                  <WatchlistPanel />
                </DockZone>
                {splitTop && (
                  <PanelResizeHandle
                    label="Redimensionar panel listas"
                    onDrag={adjustLists}
                    onDragEnd={() =>
                      layout.setListsWidthPct(pendingLists.current)
                    }
                  />
                )}
              </>
            )}

            {showCharts && (
              <DockZone
                title="Gráfico"
                open
                maximized={layout.chartsMaximized}
                onClose={layout.toggleCharts}
                onToggleMaximize={layout.maximizeCharts}
                closable={false}
                maximizable={false}
                className="min-w-0 flex-1"
              >
                <ChartsZone>{children}</ChartsZone>
              </DockZone>
            )}

            {!showLists && !showCharts && (
              <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                Abre la watchlist desde la barra superior.
              </div>
            )}
          </div>

          {layout.operationsOpen && (
            <>
              <PanelResizeHandle
                label="Redimensionar panel operaciones"
                orientation="horizontal"
                onDrag={adjustOps}
                onDragEnd={() =>
                  layout.setOperationsHeightPct(pendingOps.current)
                }
              />
              <DockZone
                title="Operaciones"
                open
                maximized={false}
                onClose={layout.toggleOperations}
                onToggleMaximize={layout.maximizeOperations}
                className="shrink-0"
                style={{
                  height: `${clamp(liveOpsPct, MIN_OPERATIONS_HEIGHT_PCT, MAX_OPERATIONS_HEIGHT_PCT)}%`,
                  minHeight: 96,
                }}
              >
                <OperationsPanel />
              </DockZone>
            </>
          )}
        </div>

        {showOperativa ? (
          <>
            <PanelResizeHandle
              label="Redimensionar panel operativa"
              className="hidden md:flex"
              onDrag={adjustOperativa}
              onDragEnd={() =>
                layout.setOperativaWidthPct(pendingOperativa.current)
              }
            />
            <DockZone
              title="Operativa"
              open
              maximized={false}
              onClose={layout.toggleOperativa}
              onToggleMaximize={() => {}}
              maximizable={false}
              className="hidden h-full shrink-0 border-l border-border md:flex md:flex-col"
              style={{
                width: `${clamp(
                  liveOperativaPct,
                  MIN_OPERATIVA_WIDTH_PCT,
                  MAX_OPERATIVA_WIDTH_PCT,
                )}%`,
                minWidth: 180,
                maxWidth: 420,
              }}
            >
              <TradingOperativaPanel />
            </DockZone>
          </>
        ) : null}
      </div>
    </div>
  );
}
