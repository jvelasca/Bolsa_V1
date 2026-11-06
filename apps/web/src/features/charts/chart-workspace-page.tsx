import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ConfirmActionDialog } from "@/components/ui/confirm-action-dialog";
import type { ChartTimeframe, ChartSeriesType } from "@bolsa/shared";
import {
  drawingHasLinkedOrder,
  isVirtualListId,
  VIRTUAL_LIST_LABELS,
  resolveChartToolbarForTab,
  normalizeChartToolbarGlobalConfig,
  strategyTop1ToChartIndicators,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import {
  ChartQuickTradeButtons,
  instrumentForQuickTrade,
} from "@/features/charts/chart-quick-trade-buttons";
import { ChartDrawingEditPopover } from "@/features/charts/chart-drawing-edit-popover";
import { ChartDrawingTemplatesDialog } from "@/features/charts/chart-drawing-templates-dialog";
import { IndicatorInstanceConfigDialog } from "@/features/charts/indicator-instance-config-dialog";
import { ChartDrawingSidebar } from "@/features/charts/chart-drawing-sidebar";
import {
  isShapeDrawTool,
  resolveEscapeDrawTool,
  shouldExitDrawModeOnEscape,
} from "@/features/charts/chart-draw-tool-utils";
import { ChartInspectorPanel } from "@/features/charts/chart-inspector-panel";
import { ChartToolbarGlobalBar } from "@/features/charts/chart-toolbar-global-bar";
import { ChartToolbarChartBar } from "@/features/charts/chart-toolbar-chart-bar";
import { ChartFinalistTop1EmptyBanner } from "@/features/charts/chart-finalist-top1-switch";
import { OhlcvChart } from "@/features/charts/ohlcv-chart";
import { useMercadoDecisionSurfacePrefs } from "@/features/trading/use-mercado-decision-surface-prefs";
import { ChartIndicatorStack } from "@/features/charts/chart-indicator-stack";
import {
  subPanelInstancesAll,
  overlayManagementInstances,
} from "@/features/charts/indicator-compute";
import { requestChartReflow } from "@/features/charts/chart-utils";
import { chartPerfDebug } from "@/features/charts/chart-perf-debug";
import { clampScaleZoom } from "@/features/charts/chart-scale-utils";
import { cn } from "@/lib/utils";
import { MERCADO_LABEL } from "@/features/confirm/daily-nav";
import {
  useInstrumentDataFreshness,
  invalidateInstrumentDataStatus,
} from "@/features/instruments/use-instrument-data-freshness";
import { useUiStore } from "@/stores/ui-store";
import { useActiveChartTab, useWorkspaceStore } from "@/stores/workspace-store";
import { useTradingUiStore } from "@/stores/trading-ui-store";
import { clearChartSignedStopPrefill } from "@/features/charts/chart-signed-stop-prefill";

export function ChartWorkspacePage() {
  const activeTab = useActiveChartTab();
  const { placement: decisionSurfacePlacement } =
    useMercadoDecisionSurfacePrefs();

  useEffect(() => () => clearChartSignedStopPrefill(), []);

  const openInstrumentSyncDialog = useUiStore(
    (s) => s.openInstrumentSyncDialog,
  );
  const chartInspectorOpen = useWorkspaceStore(
    (s) => s.workspace.layout.chartInspectorOpen ?? false,
  );
  const toggleChartInspector = useWorkspaceStore((s) => s.toggleChartInspector);
  const toggleChartInspectorShortcut = useWorkspaceStore(
    (s) => s.toggleChartInspectorShortcut,
  );
  const addDrawing = useWorkspaceStore((s) => s.addChartDrawing);
  const removeDrawing = useWorkspaceStore((s) => s.removeChartDrawing);
  const updateDrawing = useWorkspaceStore((s) => s.updateChartDrawing);
  const updateChartTimeframe = useWorkspaceStore((s) => s.updateChartTimeframe);
  const updateChartSeriesType = useWorkspaceStore(
    (s) => s.updateChartSeriesType,
  );
  const indicatorTemplates = useWorkspaceStore(
    (s) => s.workspace.indicatorTemplates ?? [],
  );
  const chartListContext = useWorkspaceStore(
    (s) => s.workspace.chartListContext,
  );
  const listConfig = useWorkspaceStore((s) => s.workspace.list);
  const chartToolbarGlobalRaw = useWorkspaceStore(
    (s) => s.workspace.chartToolbarGlobal,
  );
  const chartToolbarGlobal = useMemo(
    () => normalizeChartToolbarGlobalConfig(chartToolbarGlobalRaw),
    [chartToolbarGlobalRaw],
  );
  const resolvedChartToolbar = useMemo(
    () => resolveChartToolbarForTab(chartToolbarGlobal, activeTab?.toolbar),
    [chartToolbarGlobal, activeTab?.toolbar],
  );
  const openChartGlobalBarSettings = useUiStore(
    (s) => s.openChartGlobalBarSettings,
  );
  const openChartDataBarSettings = useUiStore(
    (s) => s.openChartDataBarSettings,
  );
  const openIndicatorConfig = useUiStore((s) => s.openIndicatorConfig);
  const openOrderDialog = useTradingUiStore((s) => s.openOrderDialog);
  const updateIndicatorInstance = useWorkspaceStore(
    (s) => s.updateIndicatorInstance,
  );
  const updateChartConfig = useWorkspaceStore((s) => s.updateChartConfig);
  const updateChartPricePanelHeight = useWorkspaceStore(
    (s) => s.updateChartPricePanelHeight,
  );
  const setSubPanelWeights = useWorkspaceStore((s) => s.setSubPanelWeights);
  const removeIndicatorInstance = useWorkspaceStore(
    (s) => s.removeIndicatorInstance,
  );
  const reorderIndicatorInstances = useWorkspaceStore(
    (s) => s.reorderIndicatorInstances,
  );
  const tool = useUiStore((s) => s.chartDrawTool);
  const setDrawTool = useUiStore((s) => s.setChartDrawTool);
  const openIndicatorsCatalog = useUiStore((s) => s.openIndicatorsCatalog);
  const applyIndicatorTemplate = useWorkspaceStore(
    (s) => s.applyIndicatorTemplate,
  );
  const setShowFinalistTop1Indicators = useWorkspaceStore(
    (s) => s.setShowFinalistTop1Indicators,
  );
  const syncFinalistTop1Indicators = useWorkspaceStore(
    (s) => s.syncFinalistTop1Indicators,
  );
  const setFinalistTop1DefaultForAll = useWorkspaceStore(
    (s) => s.setFinalistTop1DefaultForAll,
  );
  const finalistTop1DefaultOn = useWorkspaceStore((s) =>
    Boolean(s.workspace.preferences.finalistTop1DefaultOn),
  );

  const applyIndicatorGroup = useCallback(
    (templateId: string) => {
      if (!activeTab) return false;
      applyIndicatorTemplate(templateId, activeTab.id);
      requestChartReflow();
      return true;
    },
    [activeTab, applyIndicatorTemplate],
  );
  const selectedId = useUiStore((s) => s.selectedDrawingId);
  const setSelectedId = useUiStore((s) => s.setSelectedDrawingId);
  const focusDrawing = useUiStore((s) => s.focusDrawing);
  const openDrawingEditorId = useUiStore((s) => s.openDrawingEditorId);
  const flushDrawingSave = useWorkspaceStore((s) => s.flushDrawingSave);
  const setDrawingEditorOpen = useWorkspaceStore((s) => s.setDrawingEditorOpen);

  const editorDrawing =
    openDrawingEditorId && activeTab
      ? activeTab.drawings.find((item) => item.id === openDrawingEditorId)
      : null;
  const promptedSyncRef = useRef<string | null>(null);
  const [pendingLinkedOrderDelete, setPendingLinkedOrderDelete] = useState<{
    drawingId: string;
    tabId: string;
  } | null>(null);

  const queryClient = useQueryClient();
  const instrumentId = activeTab?.instrumentId;
  const chartConfig = activeTab?.chart;
  const timeframe = activeTab?.timeframe ?? "1d";
  const seriesType = activeTab?.seriesType ?? "candles";
  const activeTemplateName = indicatorTemplates.find(
    (t) => t.id === activeTab?.activeIndicatorTemplateId,
  )?.name;

  const chartListLabel = useMemo(() => {
    if (!chartListContext) return undefined;
    if (isVirtualListId(chartListContext.listId)) {
      return VIRTUAL_LIST_LABELS[
        chartListContext.listId as keyof typeof VIRTUAL_LIST_LABELS
      ];
    }
    if (listConfig.apiListId === chartListContext.listId)
      return listConfig.name;
    return listConfig.name || chartListContext.listId;
  }, [chartListContext, listConfig.apiListId, listConfig.name]);

  const { status: dataStatus, isSyncing: dataSyncing } =
    useInstrumentDataFreshness(instrumentId, timeframe);

  const indicatorSignature = useMemo(
    () =>
      activeTab?.indicatorInstances
        .map(
          (item) => `${item.instanceId}:${item.visible}:${item.presetId ?? ""}`,
        )
        .join("|") ?? "",
    [activeTab?.indicatorInstances],
  );

  const ohlcvQuery = useQuery({
    queryKey: ["ohlcv", instrumentId, timeframe],
    queryFn: () => api.getOhlcv(instrumentId!, 500, timeframe),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const indicatorsQuery = useQuery({
    queryKey: ["indicators", instrumentId, timeframe],
    queryFn: () => api.getIndicators(instrumentId!, 500, timeframe),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const instrumentQuery = useQuery({
    queryKey: ["instrument", instrumentId],
    queryFn: () => api.getInstrument(instrumentId!),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
  });

  const strategyTopQuery = useQuery({
    queryKey: ["instrument-strategy-top", instrumentId, timeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId!, timeframe),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
    retry: false,
  });

  const top1Slot = useMemo(() => {
    const slots = strategyTopQuery.data?.data?.slots ?? [];
    return slots.find((s) => s.rank === 1) ?? null;
  }, [strategyTopQuery.data?.data?.slots]);

  const strategyDefQuery = useQuery({
    queryKey: ["strategy-definition", top1Slot?.strategyDefinitionId],
    queryFn: () => api.getStrategy(top1Slot!.strategyDefinitionId!),
    enabled: Boolean(top1Slot?.strategyDefinitionId),
    staleTime: 60_000,
    retry: false,
  });

  const top1Chart = useMemo(
    () =>
      strategyTop1ToChartIndicators({
        slot: top1Slot,
        definition: strategyDefQuery.data?.data
          ? {
              indicatorSpecs:
                strategyDefQuery.data.data.definition?.indicatorSpecs ?? [],
              presetKey:
                strategyDefQuery.data.data.definition?.presetKey ??
                strategyDefQuery.data.data.presetKey,
            }
          : null,
      }),
    [top1Slot, strategyDefQuery.data?.data],
  );

  const top1Available = top1Chart.specs.length > 0;
  const top1Loading = strategyTopQuery.isLoading || strategyDefQuery.isLoading;
  const showTop1 = Boolean(activeTab?.showFinalistTop1Indicators);
  const showTop1EmptyBanner = showTop1 && !top1Loading && !top1Available;
  const top1SpecKey = useMemo(
    () =>
      top1Chart.specs
        .map((s) => `${s.definitionId}:${JSON.stringify(s.parameters ?? {})}`)
        .join("|"),
    [top1Chart.specs],
  );

  useEffect(() => {
    if (!activeTab?.id) return;
    if (!showTop1) return;
    syncFinalistTop1Indicators(top1Chart.specs, activeTab.id);
    requestChartReflow();
  }, [
    activeTab?.id,
    showTop1,
    top1SpecKey,
    top1Chart.specs,
    syncFinalistTop1Indicators,
    instrumentId,
    timeframe,
  ]);

  const onFinalistTop1Change = useCallback(
    (next: boolean) => {
      if (!activeTab?.id) return;
      setShowFinalistTop1Indicators(
        next,
        next ? top1Chart.specs : undefined,
        activeTab.id,
      );
      requestChartReflow();
    },
    [activeTab?.id, setShowFinalistTop1Indicators, top1Chart.specs],
  );

  const onFinalistTop1AllChange = useCallback(
    (next: boolean) => {
      setFinalistTop1DefaultForAll(next);
      if (next && activeTab?.id) {
        // Specs del gráfico activo ya; el resto se rellena al enfocar cada pestaña.
        setShowFinalistTop1Indicators(true, top1Chart.specs, activeTab.id);
      }
      requestChartReflow();
    },
    [
      setFinalistTop1DefaultForAll,
      setShowFinalistTop1Indicators,
      activeTab?.id,
      top1Chart.specs,
    ],
  );

  const finalistTop1Title = useMemo(() => {
    if (!instrumentId) {
      return "Selecciona un instrumento para ver el Finalista TOP #1";
    }
    if (strategyTopQuery.isLoading || strategyDefQuery.isLoading) {
      return "Cargando Finalista TOP #1…";
    }
    if (!top1Available) {
      return "Sin Finalista TOP #1 con indicadores para este valor y timeframe";
    }
    const label = top1Chart.label ? ` (${top1Chart.label})` : "";
    return `Este gráfico: indicadores del Finalista TOP #1${label} · mismo timeframe`;
  }, [
    instrumentId,
    strategyTopQuery.isLoading,
    strategyDefQuery.isLoading,
    top1Available,
    top1Chart.label,
  ]);

  const finalistTop1AllTitle =
    "Todos los gráficos: activa Finalista TOP #1 en las pestañas abiertas y en las que abras después. Luego puedes apagarlo en un valor concreto.";

  const onTimeframeChange = useCallback(
    (next: ChartTimeframe) => {
      if (!activeTab) return;
      updateChartTimeframe(next, activeTab.id);
      requestChartReflow();
    },
    [activeTab, updateChartTimeframe],
  );

  const onSeriesTypeChange = useCallback(
    (next: ChartSeriesType) => {
      if (!activeTab) return;
      updateChartSeriesType(next, activeTab.id);
      requestChartReflow();
    },
    [activeTab, updateChartSeriesType],
  );

  const handleDrawingAdded = useCallback(
    (drawingId: string) => {
      const activeTool = useUiStore.getState().chartDrawTool;
      if (isShapeDrawTool(activeTool)) {
        setSelectedId(null);
        return;
      }
      focusDrawing(drawingId);
    },
    [focusDrawing, setSelectedId],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      const state = useUiStore.getState();
      if (!shouldExitDrawModeOnEscape(state.chartDrawTool)) {
        return;
      }

      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      // Un diálogo abierto se queda con el `Escape` (cierra solo él); el
      // siguiente `Escape` ya sale del modo de dibujo.
      if (document.querySelector('[role="dialog"], [role="alertdialog"]')) {
        return;
      }

      // Salir del modo de dibujo cancela el trazo en curso (la capa reinicia
      // borradores al cambiar de herramienta) y devuelve el cursor que el
      // usuario tenía antes de dibujar (p. ej. Cruz), no el puntero por defecto.
      event.preventDefault();
      setDrawTool(
        resolveEscapeDrawTool({
          currentTool: state.chartDrawTool,
          lastDrawToolByGroup: state.lastDrawToolByGroup,
        }),
      );
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setDrawTool]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      const target = event.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }
      if (!selectedId || !activeTab) return;
      const drawing = activeTab.drawings.find((item) => item.id === selectedId);
      if (!drawing) return;

      // Un dibujo bloqueado (o una capa bloqueada) no debe poder borrarse con
      // el teclado: evita pérdidas accidentales mientras el usuario "congela"
      // la capa para hacer zoom/pan sin tocar los objetos.
      if (drawing.locked || activeTab.drawingsLayerLocked === true) {
        event.preventDefault();
        return;
      }

      if (drawingHasLinkedOrder(drawing)) {
        event.preventDefault();
        setPendingLinkedOrderDelete({
          drawingId: selectedId,
          tabId: activeTab.id,
        });
        return;
      }

      event.preventDefault();
      removeDrawing(selectedId, activeTab.id);
      setSelectedId(null);
      setDrawingEditorOpen(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    activeTab,
    removeDrawing,
    selectedId,
    setDrawingEditorOpen,
    setSelectedId,
  ]);

  useLayoutEffect(() => {
    if (!activeTab) return;
    chartPerfDebug("reflow:tab-change", {
      tabId: activeTab.id,
      instrumentId: activeTab.instrumentId,
      timeframe: activeTab.timeframe,
    });
    requestChartReflow("tab-change");
    // Deps por campo del tab: animar solo al cambiar id/instrument/timeframe. Usar el
    // objeto `activeTab` entero re-dispararía por cambios no relacionados (dibujos/overlays).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab?.id, activeTab?.instrumentId, activeTab?.timeframe]);

  const bars = ohlcvQuery.data?.data ?? [];
  const indicators = indicatorsQuery.data?.data ?? [];
  const chartInitialLoading = ohlcvQuery.isLoading && bars.length === 0;

  const dataStatusInvalidatedRef = useRef("");
  useEffect(() => {
    if (!instrumentId || bars.length === 0) return;
    const token = `${instrumentId}:${timeframe}:${bars.length}`;
    if (dataStatusInvalidatedRef.current === token) return;
    dataStatusInvalidatedRef.current = token;
    invalidateInstrumentDataStatus(queryClient, instrumentId, timeframe);
  }, [instrumentId, timeframe, bars.length, queryClient]);

  const needsSync =
    Boolean(instrumentId && activeTab) &&
    timeframe === "1d" &&
    !ohlcvQuery.isLoading &&
    !ohlcvQuery.isFetching &&
    bars.length === 0;

  useEffect(() => {
    if (!needsSync || !instrumentId || !activeTab) return;
    if (promptedSyncRef.current === instrumentId) return;
    promptedSyncRef.current = instrumentId;
    openInstrumentSyncDialog(instrumentId, activeTab.label);
  }, [needsSync, instrumentId, activeTab, openInstrumentSyncDialog]);

  useEffect(() => {
    if (bars.length > 0) {
      promptedSyncRef.current = null;
    }
  }, [bars.length, instrumentId]);

  useEffect(() => {
    if (!activeTab || chartInitialLoading) return;
    chartPerfDebug("reflow:ohlcv-ready", {
      tabId: activeTab.id,
      bars: bars.length,
    });
    requestChartReflow("ohlcv-ready");
    // Deps por campo de tab + bars.length; se evita el objeto `activeTab` completo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeTab?.id,
    activeTab?.instrumentId,
    chartInitialLoading,
    ohlcvQuery.dataUpdatedAt,
    bars.length,
  ]);

  useEffect(() => {
    if (!activeTab) return;
    chartPerfDebug("reflow:indicators", {
      tabId: activeTab.id,
      signature: indicatorSignature,
    });
    requestChartReflow("indicators");
    // Deps por campo de tab + firma de indicadores; se evita el objeto `activeTab` completo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab?.id, indicatorSignature]);

  useEffect(() => {
    if (ohlcvQuery.isFetching && bars.length > 0) {
      chartPerfDebug("ohlcv:background-fetch", { instrumentId, timeframe });
    }
  }, [ohlcvQuery.isFetching, bars.length, instrumentId, timeframe]);

  if (!activeTab || !chartConfig) {
    return (
      <div className="flex h-full min-h-0 flex-col gap-1">
        <h1 className="shrink-0 px-0.5 text-2xl font-semibold tracking-tight">
          {MERCADO_LABEL}
        </h1>
        <p className="text-sm text-muted-foreground">
          Selecciona un instrumento en el panel de listas para abrir un gráfico.
        </p>
      </div>
    );
  }

  const emptyData =
    !chartInitialLoading && !ohlcvQuery.isFetching && bars.length === 0;
  const chartTab = activeTab;
  const overlayIndicators = overlayManagementInstances(
    chartTab.indicatorInstances,
  );
  const subIndicators = subPanelInstancesAll(chartTab.indicatorInstances);

  function moveIndicatorInGroup(
    instanceId: string,
    direction: "up" | "down",
    group: typeof chartTab.indicatorInstances,
  ) {
    const index = group.findIndex((item) => item.instanceId === instanceId);
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (index < 0 || targetIndex < 0 || targetIndex >= group.length) return;
    reorderIndicatorInstances(
      group[index]!.instanceId,
      group[targetIndex]!.instanceId,
      chartTab.id,
    );
    requestChartReflow();
  }

  function moveSubIndicator(instanceId: string, direction: "up" | "down") {
    moveIndicatorInGroup(instanceId, direction, subIndicators);
  }

  function toggleIndicatorHidden(instanceId: string) {
    const current = chartTab.indicatorInstances.find(
      (item) => item.instanceId === instanceId,
    );
    if (!current) return;
    updateIndicatorInstance(
      instanceId,
      { visible: !current.visible },
      chartTab.id,
    );
    requestChartReflow();
  }

  function deleteIndicator(instanceId: string) {
    removeIndicatorInstance(instanceId, chartTab.id);
    requestChartReflow();
  }

  function setSubIndicatorScaleZoom(instanceId: string, scaleZoom: number) {
    updateIndicatorInstance(instanceId, { scaleZoom }, chartTab.id);
  }

  function handleSubPanelWeights(weights: Record<string, number>) {
    setSubPanelWeights(weights, chartTab.id);
  }

  function setPriceScaleZoom(scaleZoom: number) {
    updateChartConfig({
      chartId: chartTab.id,
      grid: { priceScaleZoom: clampScaleZoom(scaleZoom) },
    });
  }

  const canQuickTrade = Boolean(instrumentQuery.data?.data);
  // UI5-17 — acción ≠ información: la barra de estado/densidad del gráfico no
  // intercala los botones de compra/venta; la acción se agrupa aparte del status.
  const infoBarConfig = {
    ...chartToolbarGlobal,
    visibility: {
      ...chartToolbarGlobal.visibility,
      tradeButtons: false,
    },
  };
  function openQuickTrade(side: "buy" | "sell") {
    const data = instrumentQuery.data?.data;
    if (data) openOrderDialog(instrumentForQuickTrade(data, bars), null, side);
  }
  const showQuickTrade =
    chartToolbarGlobal.visibility.tradeButtons && canQuickTrade;

  return (
    <div className="chart-workspace-shell flex h-full min-h-0 flex-col gap-1">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 px-0.5">
        <h1 className="text-2xl font-semibold tracking-tight">
          {MERCADO_LABEL}
        </h1>
        {showQuickTrade ? (
          <div
            role="group"
            aria-label="Acciones rápidas de mercado"
            data-testid="mercado-quick-actions"
            className="flex shrink-0 items-center gap-1.5"
          >
            <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Acciones
            </span>
            <ChartQuickTradeButtons
              onBuy={() => openQuickTrade("buy")}
              onSell={() => openQuickTrade("sell")}
            />
          </div>
        ) : null}
      </div>
      <ChartToolbarGlobalBar
        config={infoBarConfig}
        symbol={activeTab.label}
        timeframe={timeframe}
        instrumentId={instrumentId}
        barsLoaded={bars.length}
        chartIndicatorCount={chartTab.indicatorInstances.length}
        chartInspectorOpen={chartInspectorOpen}
        dataStatus={dataStatus}
        dataSyncing={dataSyncing}
        canTrade={canQuickTrade}
        onOpenIndicatorsCatalog={openIndicatorsCatalog}
        onToggleChartInspector={toggleChartInspector}
        finalistTop1={{
          checked: finalistTop1DefaultOn,
          title: finalistTop1AllTitle,
          scope: "all",
          onCheckedChange: onFinalistTop1AllChange,
        }}
        onQuickBuy={() => openQuickTrade("buy")}
        onQuickSell={() => openQuickTrade("sell")}
        onOpenSettings={openChartGlobalBarSettings}
        onSyncData={
          instrumentId
            ? () => openInstrumentSyncDialog(instrumentId, activeTab.label)
            : undefined
        }
      />
      <ChartToolbarChartBar
        resolved={resolvedChartToolbar}
        chartSyncId={chartTab.id}
        timeframe={timeframe}
        onTimeframeChange={onTimeframeChange}
        seriesType={seriesType}
        onSeriesTypeChange={onSeriesTypeChange}
        indicatorTemplates={indicatorTemplates}
        activeIndicatorTemplateId={chartTab.activeIndicatorTemplateId}
        onApplyIndicatorTemplate={applyIndicatorGroup}
        finalistTop1={{
          checked: showTop1,
          title: finalistTop1Title,
          scope: "chart",
          onCheckedChange: onFinalistTop1Change,
        }}
        instrument={instrumentQuery.data?.data}
        instrumentId={instrumentId}
        symbol={activeTab.label}
        yahooSymbol={instrumentQuery.data?.data.yahooSymbol}
        listLabel={chartListLabel}
        bars={bars}
        overlayIndicatorCount={overlayIndicators.length}
        subIndicatorCount={subIndicators.length}
        drawingCount={activeTab.drawings.length}
        onToggleInspectorShortcut={toggleChartInspectorShortcut}
        onOpenSettings={openChartDataBarSettings}
      />
      {ohlcvQuery.isError && (
        <p className="shrink-0 text-sm text-destructive">
          No se pudo cargar el histórico OHLCV.
        </p>
      )}
      {emptyData && (
        <p className="shrink-0 text-sm text-amber-400">
          Sin datos OHLCV para {timeframe.toUpperCase()}
          {timeframe === "1d"
            ? ". Sincroniza el histórico desde el panel de datos."
            : " (se cachea en BD para backtests)."}
        </p>
      )}
      <div className="relative flex min-h-0 w-full flex-1 overflow-hidden">
        <ChartDrawingSidebar chartId={activeTab.id} />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <ChartIndicatorStack
            chartSyncId={chartTab.id}
            pricePanelHeightPct={chartTab.pricePanelHeightPct}
            onPricePanelHeightPctChange={(pct) =>
              updateChartPricePanelHeight(pct, chartTab.id)
            }
            subIndicators={subIndicators}
            bars={bars}
            apiIndicators={indicators}
            chartConfig={chartConfig}
            onConfigure={(instanceId) =>
              openIndicatorConfig(chartTab.id, instanceId)
            }
            onToggleHidden={toggleIndicatorHidden}
            onDelete={deleteIndicator}
            onMoveSubIndicator={moveSubIndicator}
            onSubIndicatorScaleZoom={setSubIndicatorScaleZoom}
            onSubPanelWeightsChange={handleSubPanelWeights}
            mainChart={
              <>
                <div className="relative h-full min-h-0 w-full">
                  {/* Sin `key` por pestaña/escala/estilo: el canvas se reutiliza y
                      actualiza sus series. Remontarlo destruía el chart con un
                      repintado pendiente (`Object is disposed`) y perdía el rango. */}
                  <OhlcvChart
                    fillContainer
                    chartSyncId={chartTab.id}
                    seriesType={seriesType}
                    seriesTypeParams={activeTab.seriesTypeParams}
                    isLoading={chartInitialLoading}
                    instrumentId={instrumentId}
                    symbol={activeTab.label}
                    showOperationalPlanLevels
                    decisionSurfacePlacement={decisionSurfacePlacement}
                    onOpenSyncDialog={() =>
                      openInstrumentSyncDialog(instrumentId!, activeTab.label)
                    }
                    bars={bars}
                    indicators={indicators}
                    indicatorInstances={activeTab.indicatorInstances}
                    config={chartConfig}
                    onPriceScaleZoomChange={setPriceScaleZoom}
                    onVolumeScaleZoomChange={(scaleZoom) => {
                      const volume = chartTab.indicatorInstances.find(
                        (item) => item.definitionId === "volume",
                      );
                      if (volume)
                        setSubIndicatorScaleZoom(volume.instanceId, scaleZoom);
                    }}
                    drawings={activeTab.drawings}
                    drawTool={tool}
                    chartTimeframe={timeframe}
                    selectedDrawingId={selectedId}
                    onAddDrawing={(drawing) =>
                      addDrawing(drawing, activeTab.id)
                    }
                    onUpdateDrawing={(drawingId, patch) =>
                      updateDrawing(drawingId, patch, activeTab.id)
                    }
                    onSelectDrawing={setSelectedId}
                    onDrawingAdded={handleDrawingAdded}
                    onDrawingDragEnd={flushDrawingSave}
                    onOpenDrawingEditor={(drawingId) =>
                      setDrawingEditorOpen(drawingId)
                    }
                    onConfigureIndicator={(instanceId) =>
                      openIndicatorConfig(chartTab.id, instanceId)
                    }
                    drawingsLayerHidden={activeTab.drawingsLayerHidden}
                    drawingsLayerLocked={activeTab.drawingsLayerLocked}
                  />
                  {showTop1EmptyBanner ? (
                    <ChartFinalistTop1EmptyBanner />
                  ) : null}
                </div>
                {editorDrawing && (
                  <ChartDrawingEditPopover
                    chartId={activeTab.id}
                    drawing={editorDrawing}
                    onClose={() => setDrawingEditorOpen(null)}
                  />
                )}
              </>
            }
          />
        </div>
        {chartInspectorOpen && (
          <button
            type="button"
            aria-label="Cerrar inspector"
            className={cn("chart-inspector-backdrop is-open")}
            onClick={toggleChartInspector}
          />
        )}
        <ChartInspectorPanel
          chartId={activeTab.id}
          indicatorInstances={activeTab.indicatorInstances}
          drawings={activeTab.drawings}
          instrument={instrumentQuery.data?.data}
          instrumentId={instrumentId}
          timeframe={timeframe}
          seriesType={seriesType}
          seriesTypeParams={activeTab.seriesTypeParams}
          bars={bars}
          barsCount={bars.length}
          listLabel={chartListLabel}
          activeTemplateName={activeTemplateName}
          chartConfig={chartConfig}
          dataStatus={dataStatus}
          isOpen={chartInspectorOpen}
          onClose={toggleChartInspector}
          onOpenSync={
            instrumentId
              ? () => openInstrumentSyncDialog(instrumentId, activeTab.label)
              : undefined
          }
          onOpenIndicatorsCatalog={openIndicatorsCatalog}
          onOpenIndicatorTemplates={openIndicatorsCatalog}
        />
      </div>
      <ChartDrawingTemplatesDialog />
      <IndicatorInstanceConfigDialog />
      <ConfirmActionDialog
        open={pendingLinkedOrderDelete !== null}
        title="Eliminar dibujo con orden asociada"
        description="Este dibujo tiene una orden vinculada. Si lo eliminas, la orden asociada dejará de mostrarse sobre el gráfico."
        confirmLabel="Eliminar dibujo"
        onCancel={() => setPendingLinkedOrderDelete(null)}
        onConfirm={() => {
          if (!pendingLinkedOrderDelete) return;
          removeDrawing(
            pendingLinkedOrderDelete.drawingId,
            pendingLinkedOrderDelete.tabId,
          );
          setSelectedId(null);
          setDrawingEditorOpen(null);
          setPendingLinkedOrderDelete(null);
        }}
      />
    </div>
  );
}
