import { useEffect, useMemo, useRef, useState } from 'react';
import type { InstrumentWithMetaDto } from '@bolsa/shared';

import { useQuery } from '@tanstack/react-query';

import {

  ChevronDown,

  ChevronRight,

  Info,

  ListPlus,

  Plus,

} from 'lucide-react';

import { api } from '@/lib/api';

import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { useExpandedInstrumentLiveQuote } from '@/features/trading/lists-tab/use-expanded-instrument-live-quote';
import { getListCellDisplay } from '@/lib/list-utils';
import { listColumnContentClass, LIST_ROW_EXPAND_WIDTH_PX, LIST_ROW_SELECT_WIDTH_PX, listRowLeftGutterWidthPx } from '@/lib/list-column-layout';
import { useListColumnLayoutContext } from '@/features/trading/lists-tab/list-column-layout-context';
import {
  isRecommendationListColumn,
  useListRecommendationRow,
} from '@/features/trading/lists-tab/list-recommendation-scores-context';
import { ListMembershipPopover } from '@/features/trading/lists-tab/list-membership-popover';
import { ListSyncStatusCell } from '@/features/trading/lists-tab/list-sync-status-cell';
import {
  ListProcessStatusCell,
  ListProcessTimestampCell,
} from '@/features/trading/lists-tab/list-process-status-cell';
import { ListNameProcessSubtitle } from '@/features/trading/lists-tab/list-name-process-subtitle';
import {
  formatEstudioProcessTimestamp,
  resolveEstudioProcessStatus,
} from '@/features/trading/estudio-process-status';
import { ESTUDIO_LANE_STAMPS_EVENT } from '@/features/trading/estudio-lane-stamps';
import { loadEstudioSupervisionPrefs } from '@/features/trading/estudio-supervision';
import { useEstudioProcessRunningStore } from '@/stores/estudio-process-running-store';

import { IconButton } from '@/components/ui/icon-button';

import { cn } from '@/lib/utils';

import { useTradingUiStore } from '@/stores/trading-ui-store';



interface ListItemAccordionProps {
  item: InstrumentWithMetaDto;
  isChartActive: boolean;
  isListSource?: boolean;
  onOpenChart: () => void;
  /** Texto secundario bajo el símbolo (p. ej. posición en cartera). */
  subtitle?: string;
  /** Estudio: resumen de procesos (vigilia/frescura/redesc.) bajo el nombre. */
  processSubtitle?: boolean;
  selected?: boolean;
  onToggleSelect?: (detail: {
    checked: boolean;
    ctrlKey: boolean;
    metaKey: boolean;
    shiftKey: boolean;
  }) => void;
}

export function ListItemAccordion({
  item,
  isChartActive,
  isListSource = false,
  onOpenChart,
  subtitle,
  processSubtitle = false,
  selected = false,
  onToggleSelect,
}: ListItemAccordionProps) {
  const membershipRef = useRef<HTMLButtonElement>(null);
  const [membershipOpen, setMembershipOpen] = useState(false);
  const selectModsRef = useRef({ ctrlKey: false, metaKey: false, shiftKey: false });
  const { visibleColumns, dataGridTemplateColumns, rowActionsWidth } = useListColumnLayoutContext();
  const recommendation = useListRecommendationRow(item.id);

  const expanded = useTradingUiStore((s) => s.expandedInstrumentIds[item.id] ?? false);

  const toggleExpanded = useTradingUiStore((s) => s.toggleExpanded);

  const openOrderDialog = useTradingUiStore((s) => s.openOrderDialog);

  const openInfoDialog = useTradingUiStore((s) => s.openInfoDialog);



  const liveQuery = useExpandedInstrumentLiveQuote(item.id, expanded);



  const dayBarQuery = useQuery({

    queryKey: ['day-bar', item.id],

    queryFn: () => api.getOhlcv(item.id, 1),

    enabled: expanded,

    staleTime: 60_000,

  });



  const lastClose = item.meta.lastClose;

  const changePct = item.meta.changePct ?? 0;

  const isUp = changePct >= 0;

  const live = liveQuery.quote;

  const dayBar = dayBarQuery.data?.data.at(-1);

  const dayOpen = dayBar?.open ?? null;

  const dayHigh = dayBar?.high ?? null;

  const dayLow = dayBar?.low ?? null;

  const dayClose = dayBar?.close ?? lastClose;

  return (

    <div
      data-instrument-id={item.id}
      className={cn(

        'border-b border-border/60',

        isListSource &&
          'border-l-2 border-l-emerald-500 ring-1 ring-inset ring-emerald-500/40',
        isChartActive && !isListSource && 'bg-primary/5',

      )}

    >

      <div className="flex items-center gap-0 px-1 py-1">
        <div
          className="flex shrink-0 items-center"
          style={{ width: listRowLeftGutterWidthPx(Boolean(onToggleSelect)) }}
        >
          {onToggleSelect ? (
            <div
              className="flex shrink-0 items-center justify-center"
              style={{ width: LIST_ROW_SELECT_WIDTH_PX }}
            >
              <input
                type="checkbox"
                className="h-3.5 w-3.5 accent-primary"
                checked={selected}
                aria-label={`Seleccionar ${item.symbol}`}
                title="Clic para marcar/desmarcar · Mayús = rango · Ctrl+Mayús = sumar rango"
                onMouseDown={(event) => {
                  selectModsRef.current = {
                    ctrlKey: event.ctrlKey,
                    metaKey: event.metaKey,
                    shiftKey: event.shiftKey,
                  };
                }}
                onClick={(event) => event.stopPropagation()}
                onChange={(event) => {
                  event.stopPropagation();
                  onToggleSelect?.({
                    checked: event.target.checked,
                    ...selectModsRef.current,
                  });
                }}
              />
            </div>
          ) : null}
          <div
            className="flex shrink-0 items-center justify-center"
            style={{ width: LIST_ROW_EXPAND_WIDTH_PX }}
          >
            <IconButton
              icon={expanded ? ChevronDown : ChevronRight}
              title={expanded ? 'Contraer' : 'Expandir'}
              onClick={() => toggleExpanded(item.id)}
            />
          </div>
        </div>

        <div
          className="grid min-w-0 flex-1 items-center"
          style={{ gridTemplateColumns: dataGridTemplateColumns }}
        >
          {visibleColumns.map((column) => {
            const cell = getListCellDisplay(item, column.id);

            if (column.id === 'syncStatus') {
              return (
                <div
                  key={column.id}
                  className={cn(
                    'flex min-w-0 items-center justify-center',
                    listColumnContentClass(column.id, 'data'),
                  )}
                >
                  <ListSyncStatusCell item={item} />
                </div>
              );
            }

            if (column.id === 'processStatus') {
              return (
                <div
                  key={column.id}
                  className={cn(
                    'flex min-w-0 items-center justify-center',
                    listColumnContentClass(column.id, 'data'),
                  )}
                >
                  <ListProcessStatusCell instrumentId={item.id} />
                </div>
              );
            }

            if (column.id === 'lastLabAt' || column.id === 'lastCoreRAt') {
              return (
                <div
                  key={column.id}
                  className={cn(
                    'flex min-w-0 items-center justify-end',
                    listColumnContentClass(column.id, 'data'),
                  )}
                >
                  <ListProcessTimestampCell
                    instrumentId={item.id}
                    kind={column.id === 'lastLabAt' ? 'lab' : 'coreR'}
                  />
                </div>
              );
            }

            if (isRecommendationListColumn(column.id)) {
              const text =
                column.id === 'ioScore'
                  ? recommendation?.io != null
                    ? String(recommendation.io)
                    : '—'
                  : column.id === 'taScore'
                    ? recommendation?.ta != null
                      ? String(Math.round(recommendation.ta))
                      : '—'
                    : column.id === 'faScore'
                      ? recommendation?.fa != null
                        ? String(Math.round(recommendation.fa))
                        : '—'
                      : column.id === 'dictamenStars'
                        ? recommendation?.dictamenStars != null
                          ? `★${recommendation.dictamenStars}`
                          : '—'
                        : (recommendation?.stanceLabel ?? '—');
              return (
                <div
                  key={column.id}
                  className={cn(
                    'min-w-0 truncate text-[10px] tabular-nums',
                    listColumnContentClass(column.id, 'data'),
                    column.id === 'recStance' && 'text-[9px]',
                  )}
                  title={
                    column.id === 'ioScore'
                      ? 'Índice Operativo 0–100'
                      : column.id === 'dictamenStars'
                        ? 'Estrellas del dictamen diario'
                        : undefined
                  }
                >
                  {text}
                </div>
              );
            }

            if (column.id === 'name') {
              return (
                <button
                  key={column.id}
                  type="button"
                  className={cn(
                    'min-w-0 truncate text-left text-[10px]',
                    listColumnContentClass(column.id, 'data'),
                    cell.className,
                  )}
                  title={
                    processSubtitle
                      ? cell.text
                      : subtitle
                        ? `${cell.text} · ${subtitle}`
                        : cell.text
                  }
                  onClick={onOpenChart}
                >
                  <span className="block truncate font-medium text-foreground">{cell.text}</span>
                  {processSubtitle ? (
                    <ListNameProcessSubtitle instrumentId={item.id} />
                  ) : subtitle ? (
                    <span className="block truncate text-[9px] text-muted-foreground">{subtitle}</span>
                  ) : null}
                </button>
              );
            }

            return (
              <button
                key={column.id}
                type="button"
                className={cn(
                  'min-w-0 truncate text-[10px]',
                  listColumnContentClass(column.id, 'data'),
                  cell.className,
                  isListSource &&
                    (column.id === 'symbol' || column.id === 'lastClose') &&
                    'font-semibold text-emerald-600 dark:text-emerald-400',
                )}
                onClick={onOpenChart}
              >
                {cell.text}
              </button>
            );
          })}
        </div>

        <div
          className={cn(
            'sticky right-0 z-[1] flex shrink-0 items-center border-l border-border/50 bg-card pl-0.5',
            isChartActive && !isListSource && 'bg-primary/5',
          )}
          style={{ width: rowActionsWidth }}
        >
          <IconButton icon={Info} title="Información del valor" onClick={() => openInfoDialog(item)} />
          <IconButton
            ref={membershipRef}
            icon={ListPlus}
            title="Listas del valor"
            className={membershipOpen ? 'bg-accent text-primary' : undefined}
            onClick={() => setMembershipOpen((open) => !open)}
          />
          <IconButton icon={Plus} title="Operar" onClick={() => openOrderDialog(item)} />
        </div>
      </div>

      {membershipOpen && (
        <ListMembershipPopover
          instrument={item}
          anchorRef={membershipRef}
          onClose={() => setMembershipOpen(false)}
        />
      )}



      {expanded && (
        <ListItemExpandedDetail
          itemId={item.id}
          dayOpen={dayOpen}
          dayClose={dayClose}
          dayHigh={dayHigh}
          dayLow={dayLow}
          changePct={changePct}
          isUp={isUp}
          spreadPct={live?.spreadPct ?? null}
          onOrder={() => openOrderDialog(item)}
        />
      )}

    </div>

  );

}

function ListItemExpandedDetail({
  itemId,
  dayOpen,
  dayClose,
  dayHigh,
  dayLow,
  changePct,
  isUp,
  spreadPct,
  onOrder,
}: {
  itemId: string;
  dayOpen: number | null;
  dayClose: number | null;
  dayHigh: number | null;
  dayLow: number | null;
  changePct: number | null;
  isUp: boolean;
  spreadPct: number | null;
  onOrder: () => void;
}) {
  const runningId = useEstudioProcessRunningStore((s) => s.instrumentId);
  const runningLane = useEstudioProcessRunningStore((s) => s.lane);
  const [stampTick, setStampTick] = useState(0);
  useEffect(() => {
    const onStamps = () => setStampTick((n) => n + 1);
    window.addEventListener(ESTUDIO_LANE_STAMPS_EVENT, onStamps);
    return () => window.removeEventListener(ESTUDIO_LANE_STAMPS_EVENT, onStamps);
  }, []);
  const processView = useMemo(
    () =>
      resolveEstudioProcessStatus({
        instrumentId: itemId,
        prefs: loadEstudioSupervisionPrefs(),
        runningLane: runningId === itemId ? runningLane : null,
      }),
    [itemId, runningId, runningLane, stampTick],
  );

  return (
    <div
      className="space-y-2 border-t border-border/40 bg-muted/10 px-2 py-2 text-[10px]"
      data-testid="list-item-expanded-detail"
    >
      {/* Precio del día en una sola línea tabulada */}
      <div
        className="grid grid-cols-5 gap-1 tabular-nums text-foreground"
        title="Apertura · Cierre · Máx/Mín · Spread · % día"
      >
        <div className="min-w-0">
          <div className="text-[9px] text-muted-foreground">Apert.</div>
          <div className="truncate font-medium">
            {dayOpen != null ? formatPrice(dayOpen) : '—'}
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-[9px] text-muted-foreground">Cierre</div>
          <div className="truncate font-medium">
            {dayClose != null ? formatPrice(dayClose) : '—'}
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-[9px] text-muted-foreground">Máx/Mín</div>
          <div className="truncate font-medium">
            {dayHigh != null && dayLow != null
              ? `${formatPrice(dayHigh)}/${formatPrice(dayLow)}`
              : '—'}
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-[9px] text-muted-foreground">Spread</div>
          <div className="truncate font-medium">
            {spreadPct != null ? formatPct(spreadPct) : '—'}
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-[9px] text-muted-foreground">% día</div>
          <div
            className={cn(
              'truncate font-medium',
              isUp ? 'text-emerald-500' : 'text-red-500',
            )}
          >
            {changePct != null ? formatPct(changePct) : '—'}
          </div>
        </div>
      </div>

      {/* Operativa / procesos debajo */}
      <div className="rounded border border-border/50 bg-background/40 px-1.5 py-1.5">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-[9px] font-semibold uppercase tracking-wide text-foreground/80">
            Operativa
          </span>
          <ListProcessStatusCell instrumentId={itemId} />
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
          {processView.lanes.map((lane) => (
            <div key={lane.id} className="contents">
              <span className="text-muted-foreground" title={lane.title}>
                {lane.label}
              </span>
              <span className="text-right tabular-nums text-foreground/90" title={lane.title}>
                {formatEstudioProcessTimestamp(lane.lastAt)}
                <span className="ml-1 text-[9px] text-muted-foreground">
                  (
                  {lane.state === 'ok'
                    ? 'ok'
                    : lane.state === 'stale'
                      ? 'toca'
                      : lane.state === 'running'
                        ? '…'
                        : '—'}
                  )
                </span>
              </span>
            </div>
          ))}
          <span className="text-muted-foreground">Últ. Lab</span>
          <span className="text-right tabular-nums">
            {formatEstudioProcessTimestamp(processView.lastLabAt)}
          </span>
          <span className="text-muted-foreground">Últ. CORE-R</span>
          <span className="text-right tabular-nums">
            {formatEstudioProcessTimestamp(processView.lastCoreRAt)}
          </span>
        </div>
      </div>

      <div className="flex justify-end gap-0.5">
        <IconButton icon={Plus} title="Nueva operación" onClick={onOrder} />
      </div>
    </div>
  );
}

