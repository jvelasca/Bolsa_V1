import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import type { InstrumentRemovalPreviewDto, InstrumentWithMetaDto } from '@bolsa/shared';
import { Dialog, checkboxClassName } from '@/components/ui/dialog';
import { api, ApiError } from '@/lib/api';
import { closeOpenChartsForInstrument } from '@/lib/close-chart-on-list-removal';
import { useTradingUiStore } from '@/stores/trading-ui-store';
import { InstrumentRemovalConfirmDialog } from '@/features/trading/lists-tab/instrument-removal-confirm-dialog';

export function ListMembershipDialog() {
  const instrument = useTradingUiStore((s) => s.listMembershipInstrument);
  const close = useTradingUiStore((s) => s.closeListMembershipDialog);
  const queryClient = useQueryClient();

  const listsQuery = useQuery({
    queryKey: ['lists'],
    queryFn: api.getLists,
    enabled: Boolean(instrument),
  });

  const listIds = listsQuery.data?.data.map((list) => list.id) ?? [];
  const detailsQueries = useQueries({
    queries: listIds.map((id) => ({
      queryKey: ['list', id],
      queryFn: () => api.getList(id),
      enabled: Boolean(instrument) && listIds.length > 0,
    })),
  });

  const initialMembership = useMemo(() => {
    const map: Record<string, boolean> = {};
    for (const query of detailsQueries) {
      const detail = query.data?.data;
      if (!detail || !instrument) continue;
      map[detail.id] = detail.instrumentIds.includes(instrument.id);
    }
    return map;
  }, [detailsQueries, instrument]);

  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [orphanPreview, setOrphanPreview] = useState<InstrumentRemovalPreviewDto | null>(null);
  const [pendingRemovals, setPendingRemovals] = useState<string[]>([]);
  const [pendingAdds, setPendingAdds] = useState<string[]>([]);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  useEffect(() => {
    if (instrument) setSelected(initialMembership);
  }, [instrument, initialMembership]);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['lists'] });
    await queryClient.invalidateQueries({ queryKey: ['list'] });
    await queryClient.invalidateQueries({ queryKey: ['list-quotes'] });
    await queryClient.invalidateQueries({ queryKey: ['database-summary'] });
    await queryClient.invalidateQueries({ queryKey: ['database-orphans'] });
  };

  const applyChanges = async (removals: string[], adds: string[], purgeIfOrphan: boolean) => {
    if (!instrument) return;
    for (const listId of removals) {
      await api.removeInstrumentFromList(listId, instrument.id, { purgeIfOrphan: false });
    }
    for (const listId of adds) {
      const detail = detailsQueries.find((q) => q.data?.data.id === listId)?.data?.data;
      if (!detail) continue;
      const ids = new Set(detail.instrumentIds);
      ids.add(instrument.id);
      await api.updateList(listId, { instrumentIds: [...ids] });
    }
    if (purgeIfOrphan) {
      await api.deleteInstrument(instrument.id, false);
    }
    if (removals.length > 0) {
      closeOpenChartsForInstrument(instrument.id);
    }
    await invalidate();
    close();
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!instrument) return;
      const removals = listIds.filter(
        (listId) => initialMembership[listId] && !selected[listId],
      );
      const adds = listIds.filter((listId) => !initialMembership[listId] && selected[listId]);

      let orphan: InstrumentRemovalPreviewDto | null = null;
      for (const listId of removals) {
        const { data } = await api.getInstrumentRemovalPreview(instrument.id, listId);
        // Simula el efecto acumulado: tras quitar todas las listas de este guardado
        const remainingAfterAll = data.listMemberships.filter(
          (m) => !removals.includes(m.listId),
        );
        if (remainingAfterAll.length === 0) {
          orphan = {
            ...data,
            wouldBeOrphan: true,
            remainingListCount: 0,
            canPurge: data.positions === 0 && data.pendingOrders === 0,
            purgeBlockedReasons:
              data.positions > 0 || data.pendingOrders > 0
                ? [
                    ...(data.positions > 0
                      ? [`Tiene ${data.positions} posición(es) abierta(s).`]
                      : []),
                    ...(data.pendingOrders > 0
                      ? [`Tiene ${data.pendingOrders} orden(es) pendiente(s).`]
                      : []),
                  ]
                : [],
          };
          break;
        }
      }

      if (orphan) {
        setPendingRemovals(removals);
        setPendingAdds(adds);
        setOrphanPreview(orphan);
        return;
      }

      await applyChanges(removals, adds, false);
    },
    onError: (err) => {
      setConfirmError(err instanceof ApiError ? err.message : 'No se pudo guardar');
    },
  });

  const confirmMutation = useMutation({
    mutationFn: async (purgeIfOrphan: boolean) => {
      await applyChanges(pendingRemovals, pendingAdds, purgeIfOrphan);
      setOrphanPreview(null);
    },
    onError: (err) => {
      setConfirmError(err instanceof ApiError ? err.message : 'No se pudo guardar');
    },
  });

  if (!instrument) return null;

  const loading = listsQuery.isLoading || detailsQueries.some((q) => q.isLoading);

  return (
    <>
      <Dialog
        open
        onClose={close}
        title={`Listas — ${instrument.symbol}`}
        description="Marca en qué listas debe aparecer este valor."
        className="max-w-md"
      >
        {loading && <p className="text-xs text-muted-foreground">Cargando listas…</p>}
        {!loading && listIds.length === 0 && (
          <p className="text-xs text-muted-foreground">No hay listas disponibles.</p>
        )}

        <ul className="scroll-area max-h-56 space-y-1 overflow-auto rounded border border-border p-2">
          {listIds.map((listId) => {
            const summary = listsQuery.data?.data.find((list) => list.id === listId);
            if (!summary) return null;
            const locked = summary.source === 'catalog';
            return (
              <li key={listId}>
                <label
                  className={`flex items-center gap-2 rounded px-1 py-1 text-sm ${
                    locked ? 'opacity-70' : 'cursor-pointer hover:bg-accent/50'
                  }`}
                >
                  <input
                    type="checkbox"
                    className={checkboxClassName}
                    checked={Boolean(selected[listId])}
                    disabled={locked || saveMutation.isPending}
                    onChange={(e) =>
                      setSelected((prev) => ({ ...prev, [listId]: e.target.checked }))
                    }
                  />
                  <span className="font-medium">{summary.name}</span>
                  <span className="text-xs text-muted-foreground">
                    ({summary.itemCount}
                    {summary.source === 'catalog' ? ' · índice' : ''})
                  </span>
                </label>
              </li>
            );
          })}
        </ul>

        {(confirmError || saveMutation.error) && (
          <p className="mt-2 text-xs text-destructive">
            {confirmError ??
              (saveMutation.error instanceof Error
                ? saveMutation.error.message
                : 'Error al guardar')}
          </p>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            className="rounded border border-border px-3 py-1.5 text-sm hover:bg-accent"
            onClick={close}
          >
            Cancelar
          </button>
          <button
            type="button"
            disabled={saveMutation.isPending}
            className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </Dialog>

      <InstrumentRemovalConfirmDialog
        open={Boolean(orphanPreview)}
        preview={orphanPreview}
        pending={confirmMutation.isPending}
        error={confirmError}
        onClose={() => {
          if (confirmMutation.isPending) return;
          setOrphanPreview(null);
          setPendingRemovals([]);
          setPendingAdds([]);
        }}
        onKeepInDb={() => confirmMutation.mutate(false)}
        onPurge={() => confirmMutation.mutate(true)}
      />
    </>
  );
}

export function openListMembershipFor(instrument: InstrumentWithMetaDto) {
  useTradingUiStore.getState().openListMembershipDialog(instrument);
}
