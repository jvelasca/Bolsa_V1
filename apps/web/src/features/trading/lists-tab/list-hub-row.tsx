import type {
  InstrumentListSummaryDto,
  InstrumentWithMetaDto,
} from "@bolsa/shared";
import {
  isVirtualListId,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_VISUALIZATION,
} from "@bolsa/shared";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  History,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { checkboxClassName } from "@/components/ui/dialog";
import { IconButton } from "@/components/ui/icon-button";
import {
  LIST_HUB_ROW_CHART_MEMBERSHIP_WIDTH_PX,
  LIST_HUB_ROW_EXPAND_WIDTH_PX,
  isCenteredListHubColumn,
  isNumericListHubColumn,
  listHubColumnContentClass,
} from "@/lib/list-hub-column-layout";
import { useListHubColumnLayoutContext } from "@/features/trading/lists-tab/list-hub-column-layout-context";
import { ListHubShortcutsSection } from "@/features/trading/lists-tab/list-hub-shortcuts-section";

function formatLastSynced(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function listTypeLabel(list: InstrumentListSummaryDto): string {
  if (isVirtualListId(list.id)) return "sistema";
  if (list.source === "catalog" || list.kind === "linked_universe")
    return "índice";
  if (list.kind === "snapshot") return "copia";
  return "personal";
}

export function ListHubRow({
  list,
  isActive,
  isPinned,
  carouselLocked,
  canMutate,
  expanded,
  onToggleExpand,
  onSelect,
  onToggleCarousel,
  onExport,
  onDelete,
  onFreezeCopy,
  onShowLog,
  chartInstrumentLabel,
  chartMembershipKnown,
  containsChartInstrument,
}: {
  list: InstrumentListSummaryDto;
  isActive: boolean;
  isPinned: boolean;
  carouselLocked: boolean;
  canMutate: boolean;
  expanded: boolean;
  onToggleExpand: () => void;
  onSelect: () => void;
  onToggleCarousel: () => void;
  onExport: () => void;
  onDelete: () => void;
  /** Congelar membresía actual como lista personal editable. */
  onFreezeCopy?: () => void;
  onShowLog?: () => void;
  chartInstrumentLabel?: string;
  /** false mientras carga la pertenencia del valor del gráfico. */
  chartMembershipKnown?: boolean;
  containsChartInstrument?: boolean;
}) {
  const { visibleColumns, dataGridTemplateColumns, rowActionsWidth } =
    useListHubColumnLayoutContext();
  const typeLabel = listTypeLabel(list);
  const isExpandable = !isVirtualListId(list.id);
  const isIndex = list.source === "catalog" || list.kind === "linked_universe";
  const syncedLabel = isIndex ? formatLastSynced(list.lastSyncedAt) : null;

  function hubCellValue(columnId: (typeof visibleColumns)[number]["id"]) {
    if (columnId === "name") {
      return (
        <span className="flex min-w-0 flex-col items-start gap-0 text-left">
          <span className="flex min-w-0 items-center gap-1">
            {isActive && <Check className="h-3 w-3 shrink-0 text-primary" />}
            <span className={listHubColumnContentClass("name", "data")}>
              {list.name}
            </span>
          </span>
          {syncedLabel ? (
            <span
              className="truncate pl-4 text-[9px] text-muted-foreground"
              title="Última sync de constitutivos"
            >
              Últ. sync {syncedLabel}
            </span>
          ) : null}
        </span>
      );
    }
    if (columnId === "type") {
      return (
        <span
          className={cn(
            listHubColumnContentClass("type", "data"),
            "inline-block rounded px-1 py-0.5",
            isVirtualListId(list.id)
              ? "bg-amber-500/15 text-amber-600"
              : "bg-muted/60",
          )}
        >
          {typeLabel}
        </span>
      );
    }
    if (columnId === "carousel") {
      return (
        <label
          className={cn(
            "inline-flex items-center justify-center rounded p-0.5",
            carouselLocked
              ? "cursor-default opacity-60"
              : "cursor-pointer hover:bg-accent/50",
          )}
          title={
            carouselLocked
              ? "Siempre en el carrusel de Valores"
              : isPinned
                ? `Quitar «${list.name}» del carrusel (misma acción que el menú ⋯ del carrusel)`
                : `Mostrar «${list.name}» en el carrusel de Valores (misma acción que el menú ⋯ del carrusel)`
          }
          onClick={(event) => event.stopPropagation()}
        >
          <input
            type="checkbox"
            className={cn(checkboxClassName, "h-3 w-3")}
            checked={isPinned}
            disabled={carouselLocked}
            onChange={() => {
              if (!carouselLocked) onToggleCarousel();
            }}
            aria-label={
              isPinned
                ? `Quitar ${list.name} del carrusel`
                : `Añadir ${list.name} al carrusel`
            }
          />
        </label>
      );
    }
    return (
      <span className={listHubColumnContentClass("count", "data")}>
        {list.itemCount}
      </span>
    );
  }

  return (
    <div
      className={cn(
        "border-b border-border/60",
        isActive && "border-l-2 border-l-primary bg-primary/5",
      )}
    >
      <div className="flex items-center gap-0 px-1 py-1">
        <div
          className="shrink-0"
          style={{ width: LIST_HUB_ROW_EXPAND_WIDTH_PX }}
          onClick={(event) => event.stopPropagation()}
        >
          {isExpandable ? (
            <IconButton
              icon={expanded ? ChevronDown : ChevronRight}
              title={
                expanded
                  ? "Contraer"
                  : "Accesos: Rastreadores, Alertas, Backtesting"
              }
              onClick={onToggleExpand}
            />
          ) : (
            <span className="block h-7" aria-hidden />
          )}
        </div>

        <div
          role="button"
          tabIndex={0}
          className="flex min-w-0 flex-1 cursor-pointer items-center gap-0 rounded-sm hover:bg-accent/40"
          title={`Abrir ${list.name} en Valores`}
          onClick={onSelect}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              onSelect();
            }
          }}
        >
          {chartInstrumentLabel && (
            <div
              className="flex shrink-0 items-center justify-center"
              style={{ width: LIST_HUB_ROW_CHART_MEMBERSHIP_WIDTH_PX }}
              onClick={(event) => event.stopPropagation()}
            >
              <input
                type="checkbox"
                className={cn(
                  checkboxClassName,
                  "pointer-events-none h-3 w-3",
                  !chartMembershipKnown && "opacity-40",
                )}
                checked={Boolean(
                  chartMembershipKnown && containsChartInstrument,
                )}
                ref={(el) => {
                  if (el)
                    el.indeterminate =
                      Boolean(chartInstrumentLabel) && !chartMembershipKnown;
                }}
                readOnly
                tabIndex={-1}
                aria-label={
                  !chartMembershipKnown
                    ? `Comprobando si ${chartInstrumentLabel} está en ${list.name}`
                    : containsChartInstrument
                      ? `${chartInstrumentLabel} está en ${list.name}`
                      : `${chartInstrumentLabel} no está en ${list.name}`
                }
                title={
                  !chartMembershipKnown
                    ? `${chartInstrumentLabel}: comprobando pertenencia a listas…`
                    : containsChartInstrument
                      ? `${chartInstrumentLabel} está en esta lista (solo lectura — edita en Valores)`
                      : `${chartInstrumentLabel} no está en esta lista (solo lectura)`
                }
              />
            </div>
          )}

          <div
            className="grid min-w-0 flex-1 items-center"
            style={{ gridTemplateColumns: dataGridTemplateColumns }}
          >
            {visibleColumns.map((column) => (
              <div
                key={column.id}
                className={cn(
                  "min-w-0 px-1",
                  isCenteredListHubColumn(column.id)
                    ? "flex justify-center"
                    : isNumericListHubColumn(column.id) && "text-right",
                )}
              >
                {hubCellValue(column.id)}
              </div>
            ))}
          </div>
        </div>

        <div
          className="flex shrink-0 items-center justify-end gap-0.5 border-l border-border/40 pl-0.5"
          style={{ width: rowActionsWidth }}
          onClick={(event) => event.stopPropagation()}
        >
          <IconButton
            icon={Download}
            title="Exportar CSV"
            disabled={
              (isVirtualListId(list.id) &&
                list.id === VIRTUAL_LIST_PENDING_ORDERS) ||
              (isVirtualListId(list.id) &&
                list.id === VIRTUAL_LIST_VISUALIZATION &&
                list.itemCount === 0)
            }
            onClick={onExport}
          />
          {isIndex && onFreezeCopy ? (
            <IconButton
              icon={Copy}
              title="Congelar copia personal (snapshot editable; el índice sigue vivo)"
              onClick={onFreezeCopy}
            />
          ) : null}
          {list.id === VIRTUAL_LIST_VISUALIZATION && onShowLog && (
            <IconButton
              icon={History}
              title="Historial de sesión"
              onClick={onShowLog}
            />
          )}
          {canMutate && (
            <IconButton
              icon={Trash2}
              title={isIndex ? "Desuscribir índice" : "Eliminar lista"}
              className="text-destructive hover:text-destructive"
              onClick={onDelete}
            />
          )}
        </div>
      </div>

      {expanded && isExpandable && (
        <div className="border-t border-border/60 bg-muted/10 px-2 py-2">
          <ListHubShortcutsSection listId={list.id} listName={list.name} />
        </div>
      )}
    </div>
  );
}

export function ListHubInstrumentPicker({
  catalog,
  selectedIds,
  onChange,
  filter,
  highlightInstrumentId,
}: {
  catalog: InstrumentWithMetaDto[];
  selectedIds: Set<string>;
  onChange: (ids: Set<string>) => void;
  filter: string;
  highlightInstrumentId?: string;
}) {
  const filtered = catalog.filter((item) => {
    if (!filter.trim()) return true;
    const q = filter.trim().toLowerCase();
    return (
      item.symbol.toLowerCase().includes(q) ||
      item.name.toLowerCase().includes(q) ||
      item.isin?.toLowerCase().includes(q)
    );
  });

  function toggle(id: string) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next);
  }

  return (
    <ul className="scroll-area max-h-40 space-y-1 overflow-auto rounded-md border border-border p-2">
      {filtered.length === 0 && (
        <li className="px-2 py-1 text-xs text-muted-foreground">
          Sin coincidencias
        </li>
      )}
      {filtered.map((item) => (
        <li key={item.id}>
          <label
            className={cn(
              "flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-accent/50",
              highlightInstrumentId === item.id &&
                "bg-primary/10 ring-1 ring-primary/30",
            )}
          >
            <input
              type="checkbox"
              className={checkboxClassName}
              checked={selectedIds.has(item.id)}
              onChange={() => toggle(item.id)}
            />
            <span className="font-medium">{item.symbol}</span>
            <span className="truncate text-xs text-muted-foreground">
              {item.name}
            </span>
          </label>
        </li>
      ))}
    </ul>
  );
}
