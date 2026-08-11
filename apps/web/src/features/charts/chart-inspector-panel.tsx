import { useEffect, useRef, useState, type ReactNode } from "react";
import type {
  ChartDrawing,
  ChartIndicatorInstance,
  ChartInstanceConfig,
  ChartSeriesType,
  ChartSeriesTypeParams,
  ChartTimeframe,
  InstrumentDataStatusDto,
  InstrumentDto,
  OhlcvBarDto,
} from "@bolsa/shared";
import {
  CHART_DRAWING_TYPE_LABELS,
  DEFAULT_DRAWING_TEMPLATES,
  findIndicatorDefinition,
  instanceLabel,
} from "@bolsa/shared";
import {
  Database,
  Eye,
  EyeOff,
  Layers,
  MousePointer2,
  Palette,
  PanelRightClose,
  Plus,
  Settings2,
  Shapes,
  Star,
  Trash2,
  SlidersHorizontal,
  ChartCandlestick,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useChartCursorStore } from "@/stores/chart-cursor-store";
import { useUiStore } from "@/stores/ui-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  type ChartInspectorConfigSection,
  type ChartInspectorMode,
  inspectorSectionElementId,
  normalizeInspectorNavigateInput,
} from "@/features/charts/chart-inspector-nav";
import { useInspectorBarShortcutFavorites } from "@/features/charts/use-inspector-bar-shortcut-favorites";
import type { ChartInspectorBarShortcutId } from "@bolsa/shared";
import {
  ChartDrawingPropertiesPanel,
  drawingTypeTitle,
} from "@/features/charts/chart-drawing-properties-panel";
import { ChartCanvasStylesPanel } from "@/features/charts/chart-canvas-styles-panel";
import { ChartSeriesStylePanel } from "@/features/charts/chart-series-style-panel";
import { IndicatorParametersForm } from "@/features/charts/indicator-parameters-form";
import {
  requestChartReflow,
  formatPct,
  formatPrice,
} from "@/features/charts/chart-utils";
import {
  DATA_STATUS_COLORS,
  DATA_STATUS_LABELS,
} from "@/features/charts/chart-database-panel";

type InspectorMode = ChartInspectorMode;

const MODES: { id: InspectorMode; label: string; icon: typeof Database }[] = [
  { id: "data", label: "Datos", icon: Database },
  { id: "config", label: "Config", icon: SlidersHorizontal },
];

const CONFIG_SECTIONS: {
  id: ChartInspectorConfigSection;
  shortcutId: ChartInspectorBarShortcutId;
  label: string;
  icon: typeof Layers;
}[] = [
  { id: "layers", shortcutId: "layers", label: "Capas", icon: Layers },
  {
    id: "series",
    shortcutId: "series",
    label: "Estilo",
    icon: ChartCandlestick,
  },
  { id: "objects", shortcutId: "objects", label: "Objetos", icon: Shapes },
  { id: "styles", shortcutId: "styles", label: "Canvas", icon: Palette },
  {
    id: "context",
    shortcutId: "context",
    label: "Selección",
    icon: MousePointer2,
  },
];

function InspectorModeBar({
  active,
  onChange,
}: {
  active: InspectorMode;
  onChange: (mode: InspectorMode) => void;
}) {
  return (
    <div className="flex shrink-0 gap-1 border-b border-border px-2 py-1.5">
      {MODES.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={cn(
            "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-medium transition-colors",
            active === id
              ? "bg-accent text-primary"
              : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
          )}
        >
          <Icon className="h-3.5 w-3.5 shrink-0" />
          {label}
        </button>
      ))}
    </div>
  );
}

function InspectorConfigSectionBar({
  active,
  onChange,
  layersCount,
  objectsCount,
  isBarShortcutFavorite,
  onToggleBarShortcutFavorite,
}: {
  active: ChartInspectorConfigSection;
  onChange: (section: ChartInspectorConfigSection) => void;
  layersCount: number;
  objectsCount: number;
  isBarShortcutFavorite: (id: ChartInspectorBarShortcutId) => boolean;
  onToggleBarShortcutFavorite: (id: ChartInspectorBarShortcutId) => void;
}) {
  return (
    <div className="border-b border-border px-1 py-1">
      <p className="px-1 pb-1 text-[9px] text-muted-foreground">
        Estrella = acceso directo en la barra del gráfico
      </p>
      <div className="chart-bar-zone-scroll flex shrink-0 gap-0.5">
        {CONFIG_SECTIONS.map(({ id, shortcutId, label, icon: Icon }) => {
          const favorited = isBarShortcutFavorite(shortcutId);
          return (
            <div key={id} className="relative shrink-0">
              <button
                type="button"
                title={label}
                onClick={() => onChange(id)}
                className={cn(
                  "flex min-w-[2.75rem] flex-col items-center gap-0.5 rounded px-1 py-1 pr-4 text-[9px] font-medium transition-colors",
                  active === id
                    ? "bg-accent text-primary"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{label}</span>
                {id === "layers" && layersCount > 0 && (
                  <span className="tabular-nums text-[8px] opacity-70">
                    {layersCount}
                  </span>
                )}
                {id === "objects" && objectsCount > 0 && (
                  <span className="tabular-nums text-[8px] opacity-70">
                    {objectsCount}
                  </span>
                )}
              </button>
              <button
                type="button"
                title={
                  favorited
                    ? "Quitar acceso directo en la barra del gráfico"
                    : "Añadir acceso directo en la barra del gráfico"
                }
                aria-label={
                  favorited
                    ? `Quitar ${label} de la barra del gráfico`
                    : `Añadir ${label} a la barra del gráfico`
                }
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleBarShortcutFavorite(shortcutId);
                }}
                className="absolute bottom-1 right-0.5 rounded p-0.5 hover:bg-background/80"
              >
                <Star
                  className={cn(
                    "h-3 w-3",
                    favorited
                      ? "fill-amber-400 text-amber-400"
                      : "text-muted-foreground",
                  )}
                />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-2 py-1 text-xs">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium text-foreground">{value}</dd>
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  variant = "default",
}: {
  children: ReactNode;
  onClick: () => void;
  variant?: "default" | "danger";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-md border px-2 py-1.5 text-left text-xs transition-colors",
        variant === "danger"
          ? "border-destructive/30 text-destructive hover:bg-destructive/10"
          : "border-border hover:bg-accent",
      )}
    >
      {children}
    </button>
  );
}

export function ChartInspectorPanel({
  chartId,
  indicatorInstances,
  drawings,
  instrument,
  instrumentId,
  timeframe,
  seriesType,
  seriesTypeParams,
  bars,
  barsCount,
  listLabel,
  activeTemplateName,
  chartConfig,
  dataStatus,
  isOpen = true,
  onClose,
  onOpenSync,
  onOpenIndicatorsCatalog,
  onOpenIndicatorTemplates,
  className,
}: {
  chartId: string;
  indicatorInstances: ChartIndicatorInstance[];
  drawings: ChartDrawing[];
  instrument?: InstrumentDto;
  instrumentId?: string;
  timeframe: ChartTimeframe;
  seriesType: ChartSeriesType;
  seriesTypeParams?: ChartSeriesTypeParams;
  bars: OhlcvBarDto[];
  barsCount: number;
  listLabel?: string;
  activeTemplateName?: string;
  chartConfig: ChartInstanceConfig;
  dataStatus?: InstrumentDataStatusDto;
  isOpen?: boolean;
  onClose?: () => void;
  onOpenSync?: () => void;
  onOpenIndicatorsCatalog?: () => void;
  onOpenIndicatorTemplates?: () => void;
  className?: string;
}) {
  const [mode, setMode] = useState<InspectorMode>("data");
  const [configSection, setConfigSection] =
    useState<ChartInspectorConfigSection>("layers");
  const chartInspectorNav = useUiStore((s) => s.chartInspectorNav);
  const setChartInspectorNav = useUiStore((s) => s.setChartInspectorNav);
  const skipContextAutoTabRef = useRef(false);

  const selectedDrawingId = useUiStore((s) => s.selectedDrawingId);
  const focusDrawing = useUiStore((s) => s.focusDrawing);
  const setSelectedDrawingId = useUiStore((s) => s.setSelectedDrawingId);
  const selectedIndicatorId = useUiStore((s) => s.selectedIndicatorInstanceId);
  const setSelectedIndicatorId = useUiStore(
    (s) => s.setSelectedIndicatorInstanceId,
  );
  const openIndicatorConfig = useUiStore((s) => s.openIndicatorConfig);

  const templates = useWorkspaceStore(
    (s) => s.workspace.drawingTemplates ?? DEFAULT_DRAWING_TEMPLATES,
  );
  const updateIndicatorInstance = useWorkspaceStore(
    (s) => s.updateIndicatorInstance,
  );
  const setIndicatorInstanceParameters = useWorkspaceStore(
    (s) => s.setIndicatorInstanceParameters,
  );
  const removeIndicatorInstance = useWorkspaceStore(
    (s) => s.removeIndicatorInstance,
  );
  const removeDrawing = useWorkspaceStore((s) => s.removeChartDrawing);
  const updateDrawing = useWorkspaceStore((s) => s.updateChartDrawing);
  const applyDrawingTemplate = useWorkspaceStore((s) => s.applyDrawingTemplate);
  const updateChartSeriesType = useWorkspaceStore(
    (s) => s.updateChartSeriesType,
  );
  const updateChartSeriesTypeParams = useWorkspaceStore(
    (s) => s.updateChartSeriesTypeParams,
  );
  const {
    isFavorite: isBarShortcutFavorite,
    toggleFavorite: toggleBarShortcutFavorite,
  } = useInspectorBarShortcutFavorites();

  const hoveredBar = useChartCursorStore((s) =>
    instrumentId && s.instrumentId === instrumentId ? s.hoveredBar : null,
  );
  const activeBar = hoveredBar ?? bars.at(-1) ?? null;

  const selectedDrawing = drawings.find(
    (drawing) => drawing.id === selectedDrawingId,
  );
  const selectedIndicator = indicatorInstances.find(
    (instance) => instance.instanceId === selectedIndicatorId,
  );
  const selectedDefinition = selectedIndicator
    ? findIndicatorDefinition(selectedIndicator.definitionId)
    : undefined;

  const overlayLayers = indicatorInstances.filter((item) => {
    const def = findIndicatorDefinition(item.definitionId);
    return def?.panel === "overlay";
  });
  const subLayers = indicatorInstances.filter((item) => {
    const def = findIndicatorDefinition(item.definitionId);
    return def?.panel === "sub";
  });

  useEffect(() => {
    if (!isOpen || !chartInspectorNav) return;

    const nav = normalizeInspectorNavigateInput(chartInspectorNav);
    skipContextAutoTabRef.current = true;
    setMode(nav.mode);
    if (nav.configSection) setConfigSection(nav.configSection);

    if (nav.instanceId) {
      setSelectedIndicatorId(nav.instanceId);
      setSelectedDrawingId(null);
    }

    const sectionId = nav.dataSection
      ? inspectorSectionElementId(nav.dataSection)
      : nav.layerSection != null
        ? inspectorSectionElementId(nav.layerSection)
        : nav.configSection != null
          ? inspectorSectionElementId(nav.configSection)
          : null;

    const scrollTimer = window.setTimeout(() => {
      if (sectionId) {
        document
          .getElementById(sectionId)
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      setChartInspectorNav(null);
      window.setTimeout(() => {
        skipContextAutoTabRef.current = false;
      }, 0);
    }, 50);

    return () => window.clearTimeout(scrollTimer);
  }, [
    chartInspectorNav,
    isOpen,
    setChartInspectorNav,
    setSelectedDrawingId,
    setSelectedIndicatorId,
  ]);

  useEffect(() => {
    if (skipContextAutoTabRef.current) return;
    if (selectedIndicator || selectedDrawing) {
      setMode("config");
      setConfigSection("context");
    }
  }, [
    selectedIndicatorId,
    selectedDrawingId,
    selectedIndicator,
    selectedDrawing,
  ]);

  const renderLayerRow = (instance: ChartIndicatorInstance) => {
    const def = findIndicatorDefinition(instance.definitionId);
    const panelLabel = def?.panel === "sub" ? "Panel" : "Sobre";
    return (
      <li key={instance.instanceId}>
        <div
          className={cn(
            "flex items-center gap-1 rounded px-1 py-0.5",
            selectedIndicatorId === instance.instanceId && "bg-accent",
          )}
        >
          <button
            type="button"
            onClick={() => {
              setSelectedIndicatorId(instance.instanceId);
              setSelectedDrawingId(null);
              setMode("config");
              setConfigSection("context");
            }}
            className={cn(
              "min-w-0 flex-1 truncate text-left text-xs hover:text-primary",
              !instance.visible && "opacity-40",
            )}
          >
            {instanceLabel(instance)}
          </button>
          <span className="shrink-0 rounded bg-muted px-1 text-[9px] text-muted-foreground">
            {panelLabel}
          </span>
          <button
            type="button"
            title={instance.visible ? "Ocultar" : "Mostrar"}
            onClick={() => {
              updateIndicatorInstance(
                instance.instanceId,
                { visible: !instance.visible },
                chartId,
              );
              requestChartReflow();
            }}
            className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-background"
          >
            {instance.visible ? (
              <Eye className="h-3 w-3" />
            ) : (
              <EyeOff className="h-3 w-3 opacity-50" />
            )}
          </button>
          <button
            type="button"
            title="Configurar"
            onClick={() => openIndicatorConfig(chartId, instance.instanceId)}
            className="shrink-0 rounded p-0.5 hover:bg-background"
          >
            <Settings2 className="h-3 w-3" />
          </button>
        </div>
      </li>
    );
  };

  return (
    <aside
      className={cn(
        "chart-inspector-panel flex flex-col border-l border-border bg-card/30 text-sm",
        isOpen && "is-open",
        className,
      )}
    >
      <header className="flex shrink-0 items-center justify-between gap-1 border-b border-border px-2 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Inspector
        </span>
        {onClose && (
          <button
            type="button"
            title="Colapsar inspector"
            aria-label="Colapsar inspector"
            onClick={onClose}
            className="chart-inspector-close rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <PanelRightClose className="h-3.5 w-3.5" />
          </button>
        )}
      </header>

      <InspectorModeBar active={mode} onChange={setMode} />

      {mode === "config" && (
        <InspectorConfigSectionBar
          active={configSection}
          onChange={setConfigSection}
          layersCount={indicatorInstances.length}
          objectsCount={drawings.length}
          isBarShortcutFavorite={isBarShortcutFavorite}
          onToggleBarShortcutFavorite={toggleBarShortcutFavorite}
        />
      )}

      <div className="min-h-0 flex-1 overflow-auto p-2">
        {mode === "data" && (
          <div className="space-y-4">
            <section id="inspector-data-instrument">
              <h3 className="mb-2 text-[10px] font-semibold uppercase text-muted-foreground">
                Instrumento
              </h3>
              <dl>
                <DetailRow label="Símbolo" value={instrument?.symbol ?? "—"} />
                <DetailRow
                  label="Nombre"
                  value={
                    <span className="line-clamp-2 max-w-[9rem] text-right text-[11px]">
                      {instrument?.name ?? "—"}
                    </span>
                  }
                />
                <DetailRow label="Bolsa" value={instrument?.exchange ?? "—"} />
                <DetailRow label="Lista origen" value={listLabel ?? "—"} />
              </dl>
            </section>

            <section id="inspector-data-chart">
              <h3 className="mb-2 text-[10px] font-semibold uppercase text-muted-foreground">
                Gráfico
              </h3>
              <dl>
                <DetailRow label="Timeframe" value={timeframe.toUpperCase()} />
                <DetailRow
                  label="Velas cargadas"
                  value={barsCount.toLocaleString("es-ES")}
                />
                <DetailRow
                  label="Plantilla ind."
                  value={activeTemplateName ?? "Ninguna"}
                />
                <DetailRow
                  label="Capas"
                  value={`${indicatorInstances.length} (${overlayLayers.length} s/gráf., ${subLayers.length} panel)`}
                />
                <DetailRow
                  label="Objetos gráficos"
                  value={String(drawings.length)}
                />
                <DetailRow
                  label="Cursor"
                  value={
                    chartConfig.cursor.mode === "magnet" ? "Imán" : "Libre"
                  }
                />
                <DetailRow
                  label="Rejilla"
                  value={
                    chartConfig.grid.showHorizontal ||
                    chartConfig.grid.showVertical
                      ? "Visible"
                      : "Oculta"
                  }
                />
              </dl>
            </section>

            {dataStatus && (
              <section id="inspector-data-database">
                <h3 className="mb-2 text-[10px] font-semibold uppercase text-muted-foreground">
                  Datos (BD)
                </h3>
                <dl>
                  <DetailRow
                    label="Estado"
                    value={
                      <span
                        className={
                          DATA_STATUS_COLORS[dataStatus.freshnessStatus] ??
                          "text-foreground"
                        }
                      >
                        {DATA_STATUS_LABELS[dataStatus.freshnessStatus] ??
                          dataStatus.freshnessStatus}
                      </span>
                    }
                  />
                  <DetailRow
                    label="Barras BD"
                    value={dataStatus.barCount.toLocaleString("es-ES")}
                  />
                </dl>
              </section>
            )}

            <section id="inspector-data-candle">
              <h3 className="mb-2 text-[10px] font-semibold uppercase text-muted-foreground">
                Vela
              </h3>
              <p className="mb-2 text-[10px] text-muted-foreground">
                {hoveredBar ? "Bajo el cursor" : "Última del histórico"}
              </p>
              {activeBar ? (
                <dl>
                  <DetailRow label="Fecha" value={activeBar.timestamp} />
                  <DetailRow
                    label="Apertura"
                    value={formatPrice(activeBar.open)}
                  />
                  <DetailRow
                    label="Máximo"
                    value={formatPrice(activeBar.high)}
                  />
                  <DetailRow
                    label="Mínimo"
                    value={formatPrice(activeBar.low)}
                  />
                  <DetailRow
                    label="Cierre"
                    value={formatPrice(activeBar.close)}
                  />
                  <DetailRow
                    label="Rango H-L"
                    value={formatPrice(activeBar.high - activeBar.low)}
                  />
                  <DetailRow
                    label="Cambio sesión"
                    value={
                      activeBar.open
                        ? formatPct(
                            ((activeBar.close - activeBar.open) /
                              activeBar.open) *
                              100,
                          )
                        : "—"
                    }
                  />
                  <DetailRow
                    label="Volumen"
                    value={activeBar.volume.toLocaleString("es-ES")}
                  />
                </dl>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Pasa el cursor sobre el gráfico para inspeccionar una vela.
                </p>
              )}
            </section>

            <section id="inspector-data-alerts">
              <h3 className="mb-2 text-[10px] font-semibold uppercase text-muted-foreground">
                Alertas
              </h3>
              <p className="text-xs text-muted-foreground">
                Las alertas de precio e indicador se configurarán aquí
                (próximamente).
              </p>
            </section>
          </div>
        )}

        {mode === "config" && configSection === "context" && (
          <div id="inspector-config-context">
            {selectedIndicator && selectedDefinition ? (
              <div className="space-y-3">
                <div>
                  <p className="font-medium">{selectedDefinition.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {instanceLabel(selectedIndicator)}
                  </p>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {selectedDefinition.panel === "sub"
                      ? "Panel inferior"
                      : "Sobre el precio"}
                  </p>
                </div>
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={selectedIndicator.showLastValue === true}
                    onChange={(e) => {
                      updateIndicatorInstance(
                        selectedIndicator.instanceId,
                        { showLastValue: e.target.checked },
                        chartId,
                      );
                      requestChartReflow();
                    }}
                  />
                  Etiqueta de precio
                </label>
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={selectedIndicator.visible}
                    onChange={(e) => {
                      updateIndicatorInstance(
                        selectedIndicator.instanceId,
                        { visible: e.target.checked },
                        chartId,
                      );
                      requestChartReflow();
                    }}
                  />
                  Visible
                </label>
                {selectedDefinition.parameters.length > 0 && (
                  <IndicatorParametersForm
                    definition={selectedDefinition}
                    values={selectedIndicator.parameters}
                    onChange={(next) => {
                      setIndicatorInstanceParameters(
                        selectedIndicator.instanceId,
                        next,
                        chartId,
                      );
                      requestChartReflow();
                    }}
                  />
                )}
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-xs text-destructive hover:underline"
                  onClick={() => {
                    removeIndicatorInstance(
                      selectedIndicator.instanceId,
                      chartId,
                    );
                    setSelectedIndicatorId(null);
                    requestChartReflow();
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Quitar del gráfico
                </button>
              </div>
            ) : selectedDrawing ? (
              <div className="space-y-3">
                <div>
                  <p className="font-medium">
                    {drawingTypeTitle(selectedDrawing)}
                  </p>
                  {selectedDrawing.text && (
                    <p className="text-xs text-muted-foreground">
                      {selectedDrawing.text}
                    </p>
                  )}
                </div>
                <ChartDrawingPropertiesPanel
                  mode="instance"
                  drawing={selectedDrawing}
                  templates={templates}
                  compact
                  onUpdateDrawing={(patch) =>
                    updateDrawing(selectedDrawing.id, patch, chartId)
                  }
                  onApplyTemplate={(templateId) =>
                    applyDrawingTemplate(
                      selectedDrawing.id,
                      templateId,
                      chartId,
                    )
                  }
                />
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-xs text-destructive hover:underline"
                  onClick={() => {
                    removeDrawing(selectedDrawing.id, chartId);
                    setSelectedDrawingId(null);
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Eliminar objeto
                </button>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Selecciona un indicador en el gráfico o en la pestaña Capas, o
                un objeto gráfico con el puntero.
              </p>
            )}
          </div>
        )}

        {mode === "config" && configSection === "layers" && (
          <div className="space-y-3" id="inspector-config-layers">
            <section className="space-y-1.5">
              {onOpenIndicatorsCatalog && (
                <ActionButton onClick={onOpenIndicatorsCatalog}>
                  <span className="inline-flex items-center gap-1.5">
                    <Plus className="h-3.5 w-3.5" />
                    Añadir indicador
                  </span>
                </ActionButton>
              )}
              {onOpenIndicatorTemplates && (
                <ActionButton onClick={onOpenIndicatorTemplates}>
                  Gestionar plantillas de indicadores
                </ActionButton>
              )}
              {onOpenSync && (
                <ActionButton onClick={onOpenSync}>
                  Sincronizar histórico 1D
                </ActionButton>
              )}
            </section>
            {indicatorInstances.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Sin indicadores en este gráfico.
              </p>
            ) : (
              <>
                <div id="inspector-layers-overlay">
                  <p className="mb-1 text-[10px] font-semibold uppercase text-muted-foreground">
                    Sobre gráfico ({overlayLayers.length})
                  </p>
                  {overlayLayers.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      Sin indicadores superpuestos al precio.
                    </p>
                  ) : (
                    <ul className="space-y-0.5">
                      {overlayLayers.map(renderLayerRow)}
                    </ul>
                  )}
                </div>
                <div id="inspector-layers-sub">
                  <p className="mb-1 text-[10px] font-semibold uppercase text-muted-foreground">
                    Paneles inferiores ({subLayers.length})
                  </p>
                  {subLayers.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      Sin paneles inferiores.
                    </p>
                  ) : (
                    <ul className="space-y-0.5">
                      {subLayers.map(renderLayerRow)}
                    </ul>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {mode === "config" && configSection === "objects" && (
          <div id="inspector-config-objects">
            {drawings.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Sin objetos gráficos.
              </p>
            ) : (
              <ul className="space-y-0.5">
                {drawings.map((drawing) => (
                  <li key={drawing.id}>
                    <button
                      type="button"
                      onClick={() => {
                        focusDrawing(drawing.id);
                        setSelectedIndicatorId(null);
                        setMode("config");
                        setConfigSection("context");
                      }}
                      className={cn(
                        "w-full rounded px-2 py-1 text-left text-xs hover:bg-accent",
                        selectedDrawingId === drawing.id &&
                          "bg-accent text-primary",
                        drawing.visible === false && "opacity-40",
                      )}
                    >
                      {CHART_DRAWING_TYPE_LABELS[drawing.type] ?? drawing.type}
                      {drawing.text ? ` · ${drawing.text}` : ""}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {mode === "config" && configSection === "series" && (
          <ChartSeriesStylePanel
            seriesType={seriesType}
            seriesTypeParams={seriesTypeParams}
            onSeriesTypeChange={(next) => {
              updateChartSeriesType(next, chartId);
              requestChartReflow();
            }}
            onParamsChange={(patch) =>
              updateChartSeriesTypeParams(patch, chartId)
            }
          />
        )}

        {mode === "config" && configSection === "styles" && (
          <div id="inspector-config-styles">
            <ChartCanvasStylesPanel chartId={chartId} config={chartConfig} />
          </div>
        )}
      </div>
    </aside>
  );
}
