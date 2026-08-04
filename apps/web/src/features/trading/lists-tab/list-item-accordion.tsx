import { useRef, useState } from 'react';
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
import { ListMembershipPopover } from '@/features/trading/lists-tab/list-membership-popover';
import { ListSyncStatusCell } from '@/features/trading/lists-tab/list-sync-status-cell';

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
  selected = false,
  onToggleSelect,
}: ListItemAccordionProps) {
  const membershipRef = useRef<HTMLButtonElement>(null);
  const [membershipOpen, setMembershipOpen] = useState(false);
  const selectModsRef = useRef({ ctrlKey: false, metaKey: false, shiftKey: false });
  const { visibleColumns, dataGridTemplateColumns, rowActionsWidth } = useListColumnLayoutContext();

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
                  title={subtitle ? `${cell.text} · ${subtitle}` : cell.text}
                  onClick={onOpenChart}
                >
                  <span className="block truncate font-medium text-foreground">{cell.text}</span>
                  {subtitle ? (
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

        <div className="space-y-1 border-t border-border/40 bg-muted/10 px-2 py-2 text-[10px]">

          <div className="grid grid-cols-2 gap-x-2 gap-y-0.5">

            <span className="text-muted-foreground">Apertura</span>

            <span className="text-right tabular-nums">

              {dayOpen != null ? formatPrice(dayOpen) : '—'}

            </span>

            <span className="text-muted-foreground">Cierre</span>

            <span className="text-right tabular-nums">

              {dayClose != null ? formatPrice(dayClose) : '—'}

            </span>

            <span className="text-muted-foreground">Spread</span>

            <span className="text-right tabular-nums">

              {live?.spreadPct != null ? formatPct(live.spreadPct) : '—'}

            </span>

            <span className="text-muted-foreground">Máx / Mín</span>

            <span className="text-right tabular-nums">

              {dayHigh != null && dayLow != null

                ? `${formatPrice(dayHigh)} / ${formatPrice(dayLow)}`

                : '— / —'}

            </span>

            <span className="text-muted-foreground">% día</span>

            <span

              className={cn(

                'text-right tabular-nums',

                isUp ? 'text-emerald-400' : 'text-red-400',

              )}

            >

              {changePct != null ? formatPct(changePct) : '—'}

            </span>

          </div>

          <div className="flex justify-end gap-0.5 pt-1">
            <IconButton icon={Plus} title="Nueva operación" onClick={() => openOrderDialog(item)} />
          </div>

        </div>

      )}

    </div>

  );

}

