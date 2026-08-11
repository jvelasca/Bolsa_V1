import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { PanelResizeHandle } from "@/components/layout/panel-resize-handle";
import { Button } from "@/components/ui/button";
import {
  clampScreenerFooterHeightPct,
  clampScreenerRunnerHeightPct,
  clampScreenerSidebarWidthPct,
} from "@/lib/screener-split-layout";
import {
  type ScreenerPanelId,
  useScreenerPreferencesStore,
} from "@/stores/screener-preferences-store";
import { cn } from "@/lib/utils";

interface ScreenerHubLayoutProps {
  className?: string;
  isSplitViewport: boolean;
  showWorkflow: boolean;
  showTools: boolean;
  hasResults: boolean;
  hasWorkflowFooter: boolean;
  runner: ReactNode;
  results: ReactNode;
  workflowFooter: ReactNode;
  sidebarPanels: Array<{
    id: ScreenerPanelId;
    open: boolean;
    node: ReactNode;
  }>;
}

function pxToPct(px: number, total: number): number {
  return total > 0 ? (px / total) * 100 : 0;
}

function ScrollPanel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "scroll-area h-full min-h-0 overflow-auto overscroll-contain",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function ScreenerHubLayout({
  className,
  isSplitViewport,
  showWorkflow,
  showTools,
  hasResults,
  hasWorkflowFooter,
  runner,
  results,
  workflowFooter,
  sidebarPanels,
}: ScreenerHubLayoutProps) {
  const split = useScreenerPreferencesStore((state) => state.layout.split);
  const patchSplitLayout = useScreenerPreferencesStore(
    (state) => state.patchSplitLayout,
  );

  const rootRef = useRef<HTMLDivElement>(null);
  const workflowRef = useRef<HTMLDivElement>(null);

  const [liveToolsPct, setLiveToolsPct] = useState(split.sidebarWidthPct);
  const [liveRunnerPct, setLiveRunnerPct] = useState(split.workflowRunnerPct);
  const [liveFooterPct, setLiveFooterPct] = useState(split.workflowFooterPct);

  const pendingToolsPct = useRef(split.sidebarWidthPct);
  const pendingRunnerPct = useRef(split.workflowRunnerPct);
  const pendingFooterPct = useRef(split.workflowFooterPct);

  useEffect(() => {
    setLiveToolsPct(split.sidebarWidthPct);
    pendingToolsPct.current = split.sidebarWidthPct;
  }, [split.sidebarWidthPct]);

  useEffect(() => {
    setLiveRunnerPct(split.workflowRunnerPct);
    pendingRunnerPct.current = split.workflowRunnerPct;
  }, [split.workflowRunnerPct]);

  useEffect(() => {
    setLiveFooterPct(split.workflowFooterPct);
    pendingFooterPct.current = split.workflowFooterPct;
  }, [split.workflowFooterPct]);

  const adjustToolsWidth = useCallback((deltaPx: number) => {
    const width = rootRef.current?.getBoundingClientRect().width ?? 0;
    if (width <= 0) return;
    const next = clampScreenerSidebarWidthPct(
      pendingToolsPct.current - pxToPct(deltaPx, width),
    );
    pendingToolsPct.current = next;
    setLiveToolsPct(next);
  }, []);

  const adjustRunnerHeight = useCallback((deltaPx: number) => {
    const height = workflowRef.current?.getBoundingClientRect().height ?? 0;
    if (height <= 0) return;
    const next = clampScreenerRunnerHeightPct(
      pendingRunnerPct.current + pxToPct(deltaPx, height),
    );
    pendingRunnerPct.current = next;
    setLiveRunnerPct(next);
  }, []);

  const adjustFooterHeight = useCallback((deltaPx: number) => {
    const height = workflowRef.current?.getBoundingClientRect().height ?? 0;
    if (height <= 0) return;
    const next = clampScreenerFooterHeightPct(
      pendingFooterPct.current + pxToPct(deltaPx, height),
    );
    pendingFooterPct.current = next;
    setLiveFooterPct(next);
  }, []);

  const toolsWidthPct = clampScreenerSidebarWidthPct(liveToolsPct);
  const workflowWidthPct = 100 - toolsWidthPct;

  const workflowPanel = (
    <div
      ref={workflowRef}
      className="flex h-full min-h-0 flex-col overflow-hidden"
    >
      {isSplitViewport && hasResults ? (
        <>
          <div
            className="min-h-0 shrink-0 overflow-hidden"
            style={{
              height: `${clampScreenerRunnerHeightPct(liveRunnerPct)}%`,
            }}
          >
            <ScrollPanel>{runner}</ScrollPanel>
          </div>
          <PanelResizeHandle
            label="Redimensionar formulario de rastreo"
            orientation="horizontal"
            onDrag={adjustRunnerHeight}
            onDragEnd={() =>
              patchSplitLayout({ workflowRunnerPct: pendingRunnerPct.current })
            }
          />
          <div className="min-h-0 flex-1 overflow-hidden">
            <ScrollPanel>{results}</ScrollPanel>
          </div>
        </>
      ) : isSplitViewport ? (
        <div className="min-h-0 flex-1 overflow-hidden">
          <ScrollPanel className="space-y-3">
            {runner}
            {results}
          </ScrollPanel>
        </div>
      ) : (
        <ScrollPanel className="flex-1 space-y-3">
          {runner}
          {results}
        </ScrollPanel>
      )}

      {isSplitViewport && hasWorkflowFooter && (
        <>
          <PanelResizeHandle
            label="Redimensionar tareas recientes y sesión"
            orientation="horizontal"
            onDrag={adjustFooterHeight}
            onDragEnd={() =>
              patchSplitLayout({ workflowFooterPct: pendingFooterPct.current })
            }
          />
          <div
            className="min-h-0 shrink-0 overflow-hidden"
            style={{
              height: `${clampScreenerFooterHeightPct(liveFooterPct)}%`,
              minHeight: 112,
            }}
          >
            <ScrollPanel className="space-y-3 p-0.5">
              {workflowFooter}
            </ScrollPanel>
          </div>
        </>
      )}

      {!isSplitViewport && hasWorkflowFooter ? (
        <div className="shrink-0 space-y-3">{workflowFooter}</div>
      ) : null}
    </div>
  );

  const toolsPanel = (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border bg-muted/20 px-2 py-1.5">
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Herramientas
        </p>
        {isSplitViewport && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => patchSplitLayout({ sidebarOpen: false })}
            title="Ocultar panel de herramientas"
          >
            <PanelLeftClose className="mr-1 h-3.5 w-3.5" />
            Ocultar
          </Button>
        )}
      </div>
      <ScrollPanel className="flex-1 space-y-2 p-2">
        {sidebarPanels.map((panel) => (
          <div key={panel.id} className="min-w-0">
            {panel.node}
          </div>
        ))}
      </ScrollPanel>
    </div>
  );

  if (!isSplitViewport) {
    return (
      <div className={cn("min-w-0 space-y-4", className)}>
        {showWorkflow && workflowPanel}
        {showTools && (
          <aside className="screener-sidebar min-w-0 space-y-2">
            {sidebarPanels.map((panel) => panel.node)}
          </aside>
        )}
      </div>
    );
  }

  const showSidebar = showTools && split.sidebarOpen;
  const showMain = showWorkflow;

  if (!showSidebar) {
    return (
      <div className={cn("flex h-full min-h-0 flex-col", className)}>
        {showMain && (
          <div className="relative min-h-0 flex-1 overflow-hidden">
            {!split.sidebarOpen && showTools && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="absolute right-2 top-2 z-10 h-8 bg-card text-xs shadow-sm"
                onClick={() => patchSplitLayout({ sidebarOpen: true })}
              >
                <PanelLeftOpen className="mr-1 h-3.5 w-3.5" />
                Herramientas
              </Button>
            )}
            {workflowPanel}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      ref={rootRef}
      className={cn("flex h-full min-h-0 overflow-hidden", className)}
    >
      {showMain && (
        <>
          <div
            className="min-h-0 shrink-0 overflow-hidden"
            style={{ width: `${workflowWidthPct}%`, minWidth: 320 }}
          >
            {workflowPanel}
          </div>
          <PanelResizeHandle
            label="Redimensionar panel de herramientas"
            onDrag={adjustToolsWidth}
            onDragEnd={() =>
              patchSplitLayout({ sidebarWidthPct: pendingToolsPct.current })
            }
          />
        </>
      )}
      <div
        className="min-h-0 shrink-0 overflow-hidden"
        style={{
          width: showMain ? `${toolsWidthPct}%` : "100%",
          minWidth: 240,
        }}
      >
        {toolsPanel}
      </div>
    </div>
  );
}
