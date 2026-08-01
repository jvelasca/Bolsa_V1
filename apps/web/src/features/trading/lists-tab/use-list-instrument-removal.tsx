import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { InstrumentRemovalPreviewDto } from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { closeOpenChartsForInstrument } from '@/lib/close-chart-on-list-removal';
import { InstrumentRemovalConfirmDialog } from '@/features/trading/lists-tab/instrument-removal-confirm-dialog';

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
    [invalidateLists],
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
        await invalidateLists();
        setPending(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'No se pudo quitar el valor');
      } finally {
        setActing(false);
      }
    },
    [invalidateLists, pending],
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
