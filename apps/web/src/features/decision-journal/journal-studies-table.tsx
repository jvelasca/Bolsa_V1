import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  GripVertical,
  MoreHorizontal,
  Star,
} from "lucide-react";
import {
  ESTUDIO_LIST_ID,
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_PERIOD_LABELS,
  JOURNAL_STUDY_STATUS_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  formatJournalStudyAge,
  mapMesaStatusDimensions,
  type DecisionJournalStudyViewV1,
  type JournalStudyOpinion,
  type JournalStudyPeriod,
  type JournalStudyUserStatus,
  type JournalStudyVigencia,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import {
  OpaqueMenuItem,
  OpaqueMenuLabel,
  OpaqueMenuPanel,
} from "@/components/ui/opaque-menu-panel";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";
import {
  JOURNAL_STUDY_COLUMN_LABELS,
  buildJournalStudyGridTemplate,
  cycleJournalStudySort,
  fitJournalStudyColumnsToContent,
  isNumericJournalStudyColumn,
  journalStudyColumnAlign,
  journalStudyGridMinWidth,
  journalStudyStatusRank,
  loadJournalStudyLayout,
  persistJournalStudyLayout,
  reorderJournalStudyColumns,
  resizeJournalStudyColumn,
  SIMPLE_JOURNAL_STUDY_LAYOUT,
  toggleJournalStudyColumn,
  toggleJournalStudyFavorite,
  visibleJournalStudyColumns,
  type JournalStudyColumnId,
  type JournalStudyColumnLayoutItem,
  type JournalStudySortState,
} from "@/lib/journal-study-column-layout";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { focusInstrumentInMercado } from "@/features/trading/focus-instrument-in-mercado";

function statusClass(status: string): string {
  switch (status as JournalStudyUserStatus) {
    case "target_active":
    case "in_progress":
      return "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200";
    case "target_reached":
      return "bg-sky-500/15 text-sky-800 dark:text-sky-200";
    case "invalidated":
    case "cancelled":
      return "bg-rose-500/15 text-rose-800 dark:text-rose-200";
    case "no_target":
      return "bg-amber-500/15 text-amber-900 dark:text-amber-200";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function opinionClass(opinion: string | null): string {
  if (opinion === "bullish") return "text-emerald-700 dark:text-emerald-300";
  if (opinion === "bearish") return "text-rose-700 dark:text-rose-300";
  return "text-muted-foreground";
}

function dash(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  return String(value);
}

function ColumnResizeHandle({
  columnId,
  width,
  onResize,
}: {
  columnId: JournalStudyColumnId;
  width: number;
  onResize: (columnId: JournalStudyColumnId, width: number) => void;
}) {
  const startRef = useRef({ x: 0, width });

  function onMouseDown(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    startRef.current = { x: event.clientX, width };
    function onMouseMove(moveEvent: MouseEvent) {
      onResize(
        columnId,
        startRef.current.width + (moveEvent.clientX - startRef.current.x),
      );
    }
    function onMouseUp() {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    }
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }

  return (
    <button
      type="button"
      aria-label={`Redimensionar ${JOURNAL_STUDY_COLUMN_LABELS[columnId]}`}
      className="absolute -right-1 top-0 z-10 h-full w-2 cursor-col-resize touch-none opacity-0 hover:bg-primary/30 hover:opacity-100"
      onMouseDown={onMouseDown}
    />
  );
}

function StrengthBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  const pct = Math.min(100, Math.max(0, value * 10));
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-1.5 w-10 overflow-hidden rounded-full bg-muted">
        <span
          className="block h-full rounded-full bg-primary"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="tabular-nums">{value.toFixed(1)}</span>
    </span>
  );
}

export function JournalStudiesTable({
  studies,
  selectedSessionId,
  onSelect,
}: {
  studies: DecisionJournalStudyViewV1[];
  selectedSessionId: string | null;
  onSelect: (study: DecisionJournalStudyViewV1) => void;
}) {
  const navigate = useNavigate();
  const openChartTab = useWorkspaceStore((s) => s.openChartTab);
  const focusInstrumentFromList = useWorkspaceStore(
    (s) => s.focusInstrumentFromList,
  );
  const stored = useMemo(() => loadJournalStudyLayout(), []);
  const [advancedMode, setAdvancedMode] = useState(false);
  const [layout, setLayout] = useState<JournalStudyColumnLayoutItem[]>(
    SIMPLE_JOURNAL_STUDY_LAYOUT,
  );
  const [favorites, setFavorites] = useState<JournalStudyColumnId[]>(
    stored.favorites,
  );
  const [sort, setSort] = useState<JournalStudySortState | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [autoFitColumns, setAutoFitColumns] = useState(true);
  const [rowMenuId, setRowMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const dragFrom = useRef<JournalStudyColumnId | null>(null);

  useEffect(() => {
    persistJournalStudyLayout(layout, favorites);
  }, [layout, favorites]);

  const visible = visibleJournalStudyColumns(layout);
  const visibleColumnKey = visible.map((column) => column.id).join(",");
  const gridTemplate = buildJournalStudyGridTemplate(visible);
  const gridMinWidth = journalStudyGridMinWidth(visible);

  const contentSamples = useMemo(() => {
    const samples: Partial<Record<JournalStudyColumnId, string[]>> = {};
    const columns = visibleJournalStudyColumns(layout);
    for (const study of studies) {
      for (const column of columns) {
        const text = cellDisplayText(study, column.id);
        if (!text) continue;
        samples[column.id] = [...(samples[column.id] ?? []), text];
      }
    }
    return samples;
  }, [studies, visibleColumnKey]);

  useEffect(() => {
    if (!autoFitColumns || studies.length === 0) return;
    setLayout((current) => {
      const next = fitJournalStudyColumnsToContent(
        stored.layout,
        contentSamples,
      );
      const changed = next.some(
        (column, index) => column.width !== current[index]?.width,
      );
      return changed ? next : current;
    });
  }, [autoFitColumns, contentSamples, studies.length, stored.layout]);

  const sorted = useMemo(() => {
    if (!sort) return studies;
    const copy = [...studies];
    copy.sort((a, b) => {
      const dir = sort.direction === "asc" ? 1 : -1;
      const av = cellSortValue(a, sort.columnId);
      const bv = cellSortValue(b, sort.columnId);
      if (typeof av === "number" && typeof bv === "number") {
        return (av - bv) * dir;
      }
      return (
        String(av).localeCompare(String(bv), undefined, {
          numeric: true,
        }) * dir
      );
    });
    return copy;
  }, [studies, sort]);

  function persistLayout(next: JournalStudyColumnLayoutItem[]) {
    setLayout(next);
  }

  function handleOpenChart(study: DecisionJournalStudyViewV1) {
    focusInstrumentInMercado(
      navigate,
      { openChartTab, focusInstrumentFromList },
      {
        instrumentId: study.instrumentId,
        symbol: study.symbol ?? study.instrumentId,
      },
      { listId: ESTUDIO_LIST_ID },
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-card">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-2 py-1">
        <p className="text-[10px] text-muted-foreground">
          {sorted.length} tesis
          {advancedMode
            ? " · clic cabecera ordena · arrastra columnas · borde derecho ancho"
            : " · vista simplificada"}
        </p>
        <div className="flex items-center gap-2">
          {advancedMode ? (
            <label className="flex cursor-pointer items-center gap-1.5 text-[10px] text-muted-foreground">
              <input
                type="checkbox"
                checked={autoFitColumns}
                onChange={(event) => setAutoFitColumns(event.target.checked)}
                data-testid="journal-columns-autofit"
              />
              Ajustar al contenido
            </label>
          ) : null}
          <div className="relative" ref={menuRef}>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2"
              onClick={() => setMenuOpen((v) => !v)}
              data-testid="journal-columns-menu"
              aria-label="Opciones de tabla"
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
            {menuOpen ? (
              <OpaqueMenuPanel className="min-w-[200px] p-2">
                <OpaqueMenuLabel>Opciones</OpaqueMenuLabel>
                <OpaqueMenuItem
                  onClick={() => {
                    setAdvancedMode((v) => !v);
                    setLayout(
                      advancedMode
                        ? SIMPLE_JOURNAL_STUDY_LAYOUT
                        : stored.layout,
                    );
                    setMenuOpen(false);
                  }}
                >
                  {advancedMode
                    ? "Vista simplificada"
                    : "Configuración avanzada"}
                </OpaqueMenuItem>
                <OpaqueMenuItem
                  onClick={() => {
                    setLayout(SIMPLE_JOURNAL_STUDY_LAYOUT);
                    setAdvancedMode(false);
                    setMenuOpen(false);
                  }}
                >
                  Restaurar diseño simple
                </OpaqueMenuItem>
                {advancedMode ? (
                  <>
                    <OpaqueMenuLabel>Columnas visibles</OpaqueMenuLabel>
                    {layout
                      .filter((column) => column.id !== "actions")
                      .map((column) => (
                        <label
                          key={column.id}
                          className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
                        >
                          <input
                            type="checkbox"
                            checked={column.visible}
                            disabled={column.id === "symbol"}
                            onChange={() =>
                              persistLayout(
                                toggleJournalStudyColumn(layout, column.id),
                              )
                            }
                          />
                          <span className="flex-1">
                            {JOURNAL_STUDY_COLUMN_LABELS[column.id]}
                          </span>
                          <button
                            type="button"
                            className="text-muted-foreground hover:text-amber-500"
                            onClick={(event) => {
                              event.preventDefault();
                              setFavorites(
                                toggleJournalStudyFavorite(
                                  favorites,
                                  column.id,
                                ),
                              );
                            }}
                            aria-label="Favorita"
                          >
                            <Star
                              className={cn(
                                "h-3 w-3",
                                favorites.includes(column.id) &&
                                  "fill-amber-400 text-amber-400",
                              )}
                            />
                          </button>
                        </label>
                      ))}
                  </>
                ) : null}
              </OpaqueMenuPanel>
            ) : null}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        <div
          className="sticky top-0 z-[1] border-b border-border bg-muted/80 backdrop-blur-sm"
          style={{ minWidth: gridMinWidth }}
        >
          <div
            className="grid items-center"
            style={{
              gridTemplateColumns: gridTemplate,
              width: gridMinWidth,
            }}
          >
            {visible.map((column) => {
              const align = journalStudyColumnAlign(column.id);
              const active = sort?.columnId === column.id;
              return (
                <div
                  key={column.id}
                  className="relative box-border py-1"
                  draggable={advancedMode && column.id !== "actions"}
                  onDragStart={() => {
                    dragFrom.current = column.id;
                  }}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => {
                    if (dragFrom.current) {
                      persistLayout(
                        reorderJournalStudyColumns(
                          layout,
                          dragFrom.current,
                          column.id,
                        ),
                      );
                    }
                    dragFrom.current = null;
                  }}
                >
                  <div
                    className={cn(
                      "flex h-full min-w-0 items-center gap-0.5 px-2 text-[10px] font-medium text-muted-foreground",
                      align === "left" && "justify-start",
                      align === "center" && "justify-center",
                      align === "right" && "justify-end",
                      column.id !== "actions" &&
                        "cursor-pointer select-none hover:text-foreground",
                    )}
                    onClick={() => {
                      if (column.id === "actions") return;
                      setSort(cycleJournalStudySort(sort, column.id));
                    }}
                  >
                    {advancedMode && column.id !== "actions" ? (
                      <GripVertical className="h-3 w-3 shrink-0 cursor-grab opacity-40" />
                    ) : null}
                    <span className="truncate">
                      {JOURNAL_STUDY_COLUMN_LABELS[column.id]}
                    </span>
                    {column.id !== "actions" ? (
                      active ? (
                        sort?.direction === "asc" ? (
                          <ArrowUp className="h-3 w-3 shrink-0" />
                        ) : (
                          <ArrowDown className="h-3 w-3 shrink-0" />
                        )
                      ) : (
                        <ArrowUpDown className="h-3 w-3 shrink-0 opacity-40" />
                      )
                    ) : null}
                  </div>
                  {advancedMode && column.id !== "actions" ? (
                    <ColumnResizeHandle
                      columnId={column.id}
                      width={column.width}
                      onResize={(id, width) => {
                        setAutoFitColumns(false);
                        persistLayout(
                          resizeJournalStudyColumn(layout, id, width),
                        );
                      }}
                    />
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>

        {sorted.length === 0 ? (
          <p
            className="px-3 py-6 text-sm text-muted-foreground"
            data-testid="studies-empty"
          >
            No hay tesis que coincidan con los filtros.
          </p>
        ) : (
          <div
            className="divide-y divide-border/40 text-[11px]"
            style={{ minWidth: gridMinWidth }}
            data-testid="studies-table"
          >
            {sorted.map((study) => (
              <div
                key={study.sessionId}
                data-testid="study-row"
                data-session-id={study.sessionId}
                data-decision-id={study.decisionId ?? undefined}
                data-instrument-id={study.instrumentId}
                role="button"
                tabIndex={0}
                className={cn(
                  "grid cursor-pointer items-center py-1.5 hover:bg-muted/30",
                  selectedSessionId === study.sessionId && "bg-primary/10",
                )}
                style={{
                  gridTemplateColumns: gridTemplate,
                  width: gridMinWidth,
                }}
                onClick={() => onSelect(study)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(study);
                  }
                }}
              >
                {visible.map((column) => {
                  const align = journalStudyColumnAlign(column.id);
                  return (
                    <div
                      key={column.id}
                      className={cn(
                        "box-border min-w-0 px-2",
                        align === "left" && "text-left",
                        align === "center" && "text-center",
                        align === "right" && "text-right",
                        isNumericJournalStudyColumn(column.id) &&
                          "tabular-nums",
                      )}
                      onClick={
                        column.id === "actions"
                          ? (event) => event.stopPropagation()
                          : undefined
                      }
                    >
                      {renderCell(study, column.id, {
                        onOpenFicha: () => onSelect(study),
                        onOpenChart: () => handleOpenChart(study),
                        onOpenInstrument: () =>
                          void navigate(`/instruments/${study.instrumentId}`),
                        onOpenAlerts: () => void navigate("/alerts"),
                        onOpenLists: () => void navigate("/trading"),
                        onOpenVolatility: () => void navigate("/screeners"),
                        menuOpen: rowMenuId === study.sessionId,
                        setMenuOpen: (open) =>
                          setRowMenuId(open ? study.sessionId : null),
                      })}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function cellDisplayText(
  study: DecisionJournalStudyViewV1,
  columnId: JournalStudyColumnId,
): string {
  switch (columnId) {
    case "symbol":
      return study.symbol ?? study.instrumentId;
    case "status":
      return (
        JOURNAL_STUDY_STATUS_LABELS[study.status as JournalStudyUserStatus] ??
        study.status
      );
    case "period":
      return study.period
        ? JOURNAL_STUDY_PERIOD_LABELS[study.period as JournalStudyPeriod]
        : "";
    case "opinion":
      return study.opinion
        ? JOURNAL_STUDY_OPINION_LABELS[study.opinion as JournalStudyOpinion]
        : "";
    case "targets":
      if (!study.hasOperationalPlan || study.target1 == null) return "";
      return study.target2 != null
        ? `${formatPrice(study.target1)} / ${formatPrice(study.target2)}`
        : formatPrice(study.target1);
    case "strength":
      return study.strength != null ? study.strength.toFixed(1) : "";
    case "updated": {
      const d = new Date(study.studiedAt);
      if (Number.isNaN(d.getTime())) return study.studiedAt;
      const label = d.toLocaleString(undefined, {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
      const age = formatJournalStudyAge(study.ageMs);
      return age ? `${label} · ${age}` : label;
    }
    case "entry":
      return study.hasOperationalPlan && study.entry != null
        ? formatPrice(study.entry)
        : "";
    case "vigencia":
      return study.vigencia
        ? JOURNAL_STUDY_VIGENCIA_LABELS[study.vigencia as JournalStudyVigencia]
        : "";
    default:
      return "";
  }
}

function cellSortValue(
  study: DecisionJournalStudyViewV1,
  columnId: JournalStudyColumnId,
): string | number {
  switch (columnId) {
    case "symbol":
      return study.symbol ?? study.instrumentId;
    case "status":
      return journalStudyStatusRank(study.status);
    case "period":
      return study.period ?? "";
    case "opinion":
      return study.opinion ?? "";
    case "targets":
      return study.target1 ?? -1;
    case "strength":
      return study.strength ?? -1;
    case "updated":
      return study.studiedAt;
    case "entry":
      return study.entry ?? -1;
    case "vigencia":
      return study.vigencia ?? "";
    default:
      return "";
  }
}

function renderCell(
  study: DecisionJournalStudyViewV1,
  columnId: JournalStudyColumnId,
  actions: {
    onOpenFicha: () => void;
    onOpenChart: () => void;
    onOpenInstrument: () => void;
    onOpenAlerts: () => void;
    onOpenLists: () => void;
    onOpenVolatility: () => void;
    menuOpen: boolean;
    setMenuOpen: (open: boolean) => void;
  },
) {
  switch (columnId) {
    case "symbol":
      return (
        <div className="min-w-0">
          <p className="truncate font-medium">
            {study.symbol ?? study.instrumentId}
          </p>
          {study.name ? (
            <p className="truncate text-[10px] text-muted-foreground">
              {study.name}
            </p>
          ) : null}
        </div>
      );
    case "status": {
      const dims = mapMesaStatusDimensions({
        study,
        hasOpenPosition: false,
        tradePlanStatus: study.tradePlanStatus,
      });
      return (
        <div className="space-y-0.5 text-[10px] leading-tight">
          <span
            className={cn(
              "inline-flex rounded px-1 py-0.5 font-semibold",
              statusClass(study.status),
            )}
          >
            {JOURNAL_STUDY_STATUS_LABELS[
              study.status as JournalStudyUserStatus
            ] ?? study.status}
          </span>
          <p className="text-muted-foreground">
            Op: {dims.operational} · Pos: {dims.position}
          </p>
        </div>
      );
    }
    case "period":
      return dash(
        study.period
          ? JOURNAL_STUDY_PERIOD_LABELS[study.period as JournalStudyPeriod]
          : null,
      );
    case "opinion":
      return (
        <span className={opinionClass(study.opinion)}>
          {study.opinion
            ? JOURNAL_STUDY_OPINION_LABELS[study.opinion as JournalStudyOpinion]
            : "—"}
        </span>
      );
    case "targets":
      if (!study.hasOperationalPlan || study.target1 == null) return "—";
      return study.target2 != null
        ? `${formatPrice(study.target1)} / ${formatPrice(study.target2)}`
        : formatPrice(study.target1);
    case "strength":
      return <StrengthBar value={study.strength} />;
    case "updated": {
      const age = formatJournalStudyAge(study.ageMs);
      const d = new Date(study.studiedAt);
      const label = Number.isNaN(d.getTime())
        ? study.studiedAt
        : d.toLocaleString(undefined, {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          });
      return (
        <span className="tabular-nums text-muted-foreground">
          {label}
          {age ? ` · ${age}` : ""}
        </span>
      );
    }
    case "entry":
      return study.hasOperationalPlan && study.entry != null
        ? formatPrice(study.entry)
        : "—";
    case "vigencia":
      return study.vigencia
        ? JOURNAL_STUDY_VIGENCIA_LABELS[study.vigencia as JournalStudyVigencia]
        : "—";
    case "actions":
      return (
        <div className="relative flex justify-center">
          <button
            type="button"
            title="Acciones"
            aria-label="Acciones"
            className="inline-flex h-7 w-7 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
            onClick={() => actions.setMenuOpen(!actions.menuOpen)}
            data-testid="study-row-menu"
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </button>
          {actions.menuOpen ? (
            <OpaqueMenuPanel className="right-0 min-w-[180px]">
              <OpaqueMenuItem onClick={actions.onOpenFicha}>
                Ver análisis IA
              </OpaqueMenuItem>
              <OpaqueMenuItem onClick={actions.onOpenChart}>
                Ver gráfico
              </OpaqueMenuItem>
              <OpaqueMenuItem onClick={actions.onOpenVolatility}>
                Estudio de volatilidad
              </OpaqueMenuItem>
              <OpaqueMenuItem onClick={actions.onOpenLists}>
                Ver listas
              </OpaqueMenuItem>
              <OpaqueMenuItem onClick={actions.onOpenAlerts}>
                Gestionar alarmas
              </OpaqueMenuItem>
              <OpaqueMenuItem onClick={actions.onOpenInstrument}>
                Abrir ficha del activo
              </OpaqueMenuItem>
            </OpaqueMenuPanel>
          ) : null}
        </div>
      );
    default:
      return null;
  }
}
