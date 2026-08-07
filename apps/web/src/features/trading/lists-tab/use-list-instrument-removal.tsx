import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ESTUDIO_LIST_ID, type InstrumentRemovalPreviewDto } from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { closeOpenChartsForInstrument } from '@/lib/close-chart-on-list-removal';
import { InstrumentRemovalConfirmDialog } from '@/features/trading/lists-tab/instrument-removal-confirm-dialog';
import { unsubscribeInstrumentFromSupervision } from '@/features/trading/estudio-supervision';
import { useVisualizationStore } from '@/stores/visualization-store';

interface PendingRemoval {
  listId: string;
  instrumentId: string;
  preview: InstrumentRemovalPreviewDto;
}

/**
 * Al desmarcar un valor de una lista: si quedaría huérfano, pide confirmación
 * (solo lista vs purga BD). Si sigue en otras listas, quita sin diálogo.
 */
export function useListInstrumentRemoval() {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<PendingRemoval | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const invalidateLists = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['lists'] });
    await queryClient.invalidateQueries({ queryKey: ['list'] });
    await queryClient.invalidateQueries({ queryKey: ['list-quotes'] });
    await queryClient.invalidateQueries({ queryKey: ['database-summary'] });
    await queryClient.invalidateQueries({ queryKey: ['database-orphans'] });
  }, [queryClient]);

  const afterEstudioRemove = useCallback((listId: string, instrumentId: string) => {
    if (listId !== ESTUDIO_LIST_ID) return;
    useVisualizationStore.getState().removeInstrument(instrumentId);
    unsubscribeInstrumentFromSupervision([instrumentId]);
  }, []);

  const close = useCallback(() => {
    if (acting) return;
    setPending(null);
    setError(null);
  }, [acting]);

  const removeFromList = useCallback(
    async (listId: string, instrumentId: string) => {
      setError(null);
      setLoadingPreview(true);
      try {
        const { data: preview } = await api.getInstrumentRemovalPreview(instrumentId, listId);
        if (!preview.wouldBeOrphan) {
          await api.removeInstrumentFromList(listId, instrumentId, { purgeIfOrphan: false });
          closeOpenChartsForInstrument(instrumentId);
          afterEstudioRemove(listId, instrumentId);
          await invalidateLists();
          return;
        }
        setPending({ listId, instrumentId, preview });
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'No se pudo preparar la eliminación');
        throw err;
      } finally {
        setLoadingPreview(false);
      }
    },
    [afterEstudioRemove, invalidateLists],
  );

  const execute = useCallback(
    async (purgeIfOrphan: boolean) => {
      if (!pending) return;
      setActing(true);
      setError(null);
      try {
        await api.removeInstrumentFromList(pending.listId, pending.instrumentId, {
          purgeIfOrphan,
        });
        closeOpenChartsForInstrument(pending.instrumentId);
        afterEstudioRemove(pending.listId, pending.instrumentId);
        await invalidateLists();
        setPending(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'No se pudo quitar el valor');
      } finally {
        setActing(false);
      }
    },
    [afterEstudioRemove, invalidateLists, pending],
  );

  const dialog = (
    <InstrumentRemovalConfirmDialog
      open={Boolean(pending)}
      preview={pending?.preview ?? null}
      loading={loadingPreview}
      pending={acting}
      error={error}
      onClose={close}
      onKeepInDb={() => void execute(false)}
      onPurge={() => void execute(true)}
    />
  );

  return { removeFromList, dialog, loadingPreview, error };
}
