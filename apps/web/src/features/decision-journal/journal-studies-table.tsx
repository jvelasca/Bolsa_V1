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
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_PERIOD_LABELS,
  JOURNAL_STUDY_STATUS_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  formatJournalStudyAge,
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
  isNumericJournalStudyColumn,
  journalStudyStatusRank,
  loadJournalStudyLayout,
  persistJournalStudyLayout,
  reorderJournalStudyColumns,
  resizeJournalStudyColumn,
  toggleJournalStudyColumn,
  toggleJournalStudyFavorite,
  visibleJournalStudyColumns,
  type JournalStudyColumnId,
  type JournalStudyColumnLayoutItem,
  type JournalStudySortState,
} from "@/lib/journal-study-column-layout";
import { useWorkspaceStore } from "@/stores/workspace-store";

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
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
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
  const stored = useMemo(() => loadJournalStudyLayout(), []);
  const [layout, setLayout] = useState<JournalStudyColumnLayoutItem[]>(
    stored.layout,
  );
  const [favorites, setFavorites] = useState<JournalStudyColumnId[]>(
    stored.favorites,
  );
  const [sort, setSort] = useState<JournalStudySortState | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [rowMenuId, setRowMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const dragFrom = useRef<JournalStudyColumnId | null>(null);

  useEffect(() => {
    persistJournalStudyLayout(layout, favorites);
  }, [layout, favorites]);

  const visible = visibleJournalStudyColumns(layout);
  const gridTemplate = buildJournalStudyGridTemplate(visible);

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
    openChartTab(study.instrumentId, study.symbol ?? study.instrumentId);
    void navigate("/trading");
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border px-2 py-1">
        <p className="text-[10px] text-muted-foreground">
          Clic en cabecera para ordenar · arrastra para mover · borde derecho
          para ancho
        </p>
        <div className="relative" ref={menuRef}>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 px-2"
            onClick={() => setMenuOpen((v) => !v)}
            data-testid="journal-columns-menu"
            aria-label="Columnas"
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
          {menuOpen ? (
            <OpaqueMenuPanel className="min-w-[200px] p-2">
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
                          toggleJournalStudyFavorite(favorites, column.id),
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
            </OpaqueMenuPanel>
          ) : null}
        </div>
      </div>

      <div
        className="grid border-b border-border bg-muted/40 px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
        style={{ gridTemplateColumns: gridTemplate }}
      >
        {visible.map((column) => {
          const active = sort?.columnId === column.id;
          return (
            <div
              key={column.id}
              className="relative flex min-w-0 items-center gap-1 pr-1"
              draggable={column.id !== "actions"}
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
              {column.id !== "actions" ? (
                <GripVertical className="h-3 w-3 shrink-0 opacity-40" />
              ) : null}
              <button
                type="button"
                className={cn(
                  "flex min-w-0 items-center gap-0.5 text-left",
                  isNumericJournalStudyColumn(column.id) && "tabular-nums",
                )}
                onClick={() => setSort(cycleJournalStudySort(sort, column.id))}
              >
                <span className="truncate">
                  {JOURNAL_STUDY_COLUMN_LABELS[column.id]}
                </span>
                {column.id !== "actions" ? (
                  active ? (
                    sort?.direction === "asc" ? (
                      <ArrowUp className="h-3 w-3" />
                    ) : (
                      <ArrowDown className="h-3 w-3" />
                    )
                  ) : (
                    <ArrowUpDown className="h-3 w-3 opacity-40" />
                  )
                ) : null}
              </button>
              {column.id !== "actions" ? (
                <ColumnResizeHandle
                  columnId={column.id}
                  width={column.width}
                  onResize={(id, width) =>
                    persistLayout(resizeJournalStudyColumn(layout, id, width))
                  }
                />
              ) : null}
            </div>
          );
        })}
      </div>

      {sorted.length === 0 ? (
        <p
          className="px-3 py-6 text-sm text-muted-foreground"
          data-testid="studies-empty"
        >
          No hay tesis que coincidan con los filtros.
        </p>
      ) : (
        <ul data-testid="studies-table">
          {sorted.map((study) => (
            <li
              key={study.sessionId}
              data-testid="study-row"
              data-session-id={study.sessionId}
              className={cn(
                "relative grid cursor-pointer border-b border-border/60 px-2 py-2 text-xs hover:bg-muted/40",
                selectedSessionId === study.sessionId && "bg-primary/10",
              )}
              style={{ gridTemplateColumns: gridTemplate }}
              onClick={() => onSelect(study)}
            >
              {visible.map((column) => (
                <div
                  key={column.id}
                  className={cn(
                    "min-w-0 pr-2",
                    isNumericJournalStudyColumn(column.id) && "tabular-nums",
                  )}
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
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
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
        <div>
          <p className="font-semibold">{study.symbol ?? study.instrumentId}</p>
          {study.name ? (
            <p className="truncate text-[10px] text-muted-foreground">
              {study.name}
            </p>
          ) : null}
        </div>
      );
    case "status":
      return (
        <span
          className={cn(
            "inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold",
            statusClass(study.status),
          )}
        >
          {JOURNAL_STUDY_STATUS_LABELS[
            study.status as JournalStudyUserStatus
          ] ?? study.status}
        </span>
      );
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
        <div
          className="relative flex justify-end gap-1"
          onClick={(event) => event.stopPropagation()}
        >
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 px-2 text-[10px]"
            onClick={actions.onOpenFicha}
            data-testid="study-open-ficha"
          >
            Análisis
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 px-1.5"
            onClick={() => actions.setMenuOpen(!actions.menuOpen)}
            aria-label="Más acciones"
            data-testid="study-row-menu"
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </Button>
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
