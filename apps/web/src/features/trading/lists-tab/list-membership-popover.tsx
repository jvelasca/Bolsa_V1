import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { InstrumentWithMetaDto } from '@bolsa/shared';
import {
  isVirtualListId,
  VIRTUAL_LIST_LABELS,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_VISUALIZATION,
} from '@bolsa/shared';
import { Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';
import { checkboxClassName } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { usePendingOrders } from '@/features/trading/use-pending-orders';
import { useListInstrumentRemoval } from '@/features/trading/lists-tab/use-list-instrument-removal';
import { useWorkspaceStore } from '@/stores/workspace-store';

interface ListMembershipPopoverProps {
  instrument: InstrumentWithMetaDto;
  anchorRef: React.RefObject<HTMLButtonElement | null>;
  onClose: () => void;
}

interface MembershipRow {
  id: string;
  name: string;
  checked: boolean;
  locked: boolean;
  hint?: string;
}

export function ListMembershipPopover({
  instrument,
  anchorRef,
  onClose,
}: ListMembershipPopoverProps) {
  const popoverRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const { pendingOrders } = usePendingOrders();
  const charts = useWorkspaceStore((state) => state.workspace.charts);
  const inVisualizados = useMemo(
    () => charts.some((tab) => tab.instrumentId === instrument.id),
    [charts, instrument.id],
  );
  const { removeFromList, dialog, loadingPreview } = useListInstrumentRemoval();

  const accountScope = useActiveAccountQueryKey();

  const listsQuery = useQuery({
    queryKey: ['lists'],
    queryFn: api.getLists,
  });

  const portfolioQuery = useQuery({
    queryKey: ['portfolio', accountScope],
    queryFn: api.getPortfolio,
  });

  const apiLists = useMemo(() => listsQuery.data?.data ?? [], [listsQuery.data?.data]);

  const membershipsQuery = useQuery({
    queryKey: ['lists', 'memberships'],
    queryFn: api.getListMemberships,
    staleTime: 30_000,
  });

  const membershipByListId = useMemo(() => {
    const map: Record<string, boolean> = {};
    const memberships = membershipsQuery.data?.data ?? {};
    for (const list of apiLists) {
      map[list.id] = (memberships[list.id] ?? []).includes(instrument.id);
    }
    return map;
  }, [apiLists, membershipsQuery.data?.data, instrument.id]);

  const [position, setPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();
    setPosition({
      top: rect.bottom + 4,
      left: Math.max(8, rect.right - 240),
    });
  }, [anchorRef]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (popoverRef.current?.contains(target)) return;
      if (anchorRef.current?.contains(target)) return;
      if ((target as HTMLElement).closest?.('[role="dialog"]')) return;
      onClose();
    }
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [anchorRef, onClose]);

  const updateMutation = useMutation({
    mutationFn: async ({ listId, include }: { listId: string; include: boolean }) => {
      if (!include) {
        await removeFromList(listId, instrument.id);
        return;
      }
      const current = membershipsQuery.data?.data?.[listId] ?? [];
      const ids = new Set(current);
      ids.add(instrument.id);
      await api.updateList(listId, { instrumentIds: [...ids] });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['lists'] });
      await queryClient.invalidateQueries({ queryKey: ['lists', 'memberships'] });
      await queryClient.invalidateQueries({ queryKey: ['list'] });
      await queryClient.invalidateQueries({ queryKey: ['list-quotes'] });
    },
  });

  const rows: MembershipRow[] = useMemo(() => {
    const result: MembershipRow[] = [
      {
        id: VIRTUAL_LIST_VISUALIZATION,
        name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_VISUALIZATION],
        checked: inVisualizados,
        locked: false,
        hint: 'pestañas',
      },
      {
        id: VIRTUAL_LIST_PORTFOLIO,
        name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_PORTFOLIO],
        checked: (portfolioQuery.data?.data.positions ?? []).some(
          (position) => position.instrumentId === instrument.id,
        ),
        locked: true,
        hint: 'posición',
      },
      {
        id: VIRTUAL_LIST_PENDING_ORDERS,
        name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_PENDING_ORDERS],
        checked: pendingOrders.some((order) => order.instrumentId === instrument.id),
        locked: true,
        hint: 'orden',
      },
    ];

    for (const list of apiLists) {
      result.push({
        id: list.id,
        name: list.name,
        checked: Boolean(membershipByListId[list.id]),
        locked: list.source !== 'custom',
        hint:
          list.source === 'catalog' ? 'índice' : list.source === 'custom' ? 'personal' : undefined,
      });
    }

    return result;
  }, [
    apiLists,
    instrument.id,
    membershipByListId,
    pendingOrders,
    portfolioQuery.data,
    inVisualizados,
  ]);

  const loading =
    listsQuery.isLoading ||
    membershipsQuery.isLoading ||
    portfolioQuery.isLoading;

  async function handleToggle(row: MembershipRow) {
    if (row.locked) return;
    if (row.id === VIRTUAL_LIST_VISUALIZATION) {
      const { reconcileVisualizadosToOpenCharts } = await import(
        '@/features/trading/lists-tab/use-chart-visualization-sync'
      );
      if (row.checked) {
        const { closeOpenChartsForInstrument } = await import(
          '@/lib/close-chart-on-list-removal'
        );
        closeOpenChartsForInstrument(instrument.id);
        reconcileVisualizadosToOpenCharts();
      } else {
        // Abrir pestaña = entra en Visualizados (SoT = charts).
        const { useWorkspaceStore } = await import('@/stores/workspace-store');
        useWorkspaceStore.getState().openChartTab(instrument.id, instrument.symbol);
        reconcileVisualizadosToOpenCharts();
      }
      return;
    }
    if (isVirtualListId(row.id)) return;
    updateMutation.mutate({ listId: row.id, include: !row.checked });
  }

  return (
    <>
      <div
        ref={popoverRef}
        className="fixed z-[80] w-60 rounded-md border border-border bg-card p-2 shadow-xl"
        style={{ top: position.top, left: position.left }}
        role="dialog"
        aria-label={`Listas de ${instrument.symbol}`}
      >
        <p className="mb-2 border-b border-border pb-1.5 text-xs font-medium">
          {instrument.symbol}
          <span className="ml-1 font-normal text-muted-foreground">· listas</span>
        </p>

        {(loading || loadingPreview) && (
          <p className="flex items-center gap-1 px-1 py-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            Cargando…
          </p>
        )}

        {!loading && !loadingPreview && (
          <ul className="scroll-area max-h-52 space-y-0.5 overflow-auto">
            {rows.map((row) => (
              <li key={row.id}>
                <label
                  className={cn(
                    'flex items-center gap-2 rounded px-1 py-1 text-xs',
                    row.locked ? 'opacity-80' : 'cursor-pointer hover:bg-accent/50',
                  )}
                >
                  <input
                    type="checkbox"
                    className={checkboxClassName}
                    checked={row.checked}
                    disabled={row.locked || updateMutation.isPending}
                    onChange={() => handleToggle(row)}
                  />
                  <span className="min-w-0 flex-1 truncate">{row.name}</span>
                  {row.hint && (
                    <span className="shrink-0 text-[10px] text-muted-foreground">{row.hint}</span>
                  )}
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
      {dialog}
    </>
  );
}
