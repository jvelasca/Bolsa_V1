/**
 * Comprueba frescura de datos y lanza sync automático si están vacíos o desactualizados (solo 1D).
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import type { ChartTimeframe } from '@bolsa/shared';
import { api } from '@/lib/api';
import { useInstrumentSync } from '@/features/instruments/use-instrument-sync';

export function useInstrumentDataFreshness(
  instrumentId: string | undefined,
  timeframe: ChartTimeframe = '1d',
) {
  const queryClient = useQueryClient();
  const syncMutation = useInstrumentSync(instrumentId);
  const autoSyncAttempted = useRef<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ['data-status', instrumentId, timeframe],
    queryFn: () => api.getDataStatus(instrumentId!, timeframe),
    enabled: Boolean(instrumentId),
    staleTime: 15_000,
  });

  const status = statusQuery.data?.data;
  const needsAutoSync =
    timeframe === '1d' &&
    Boolean(instrumentId && status) &&
    (status!.freshnessStatus === 'stale' || status!.freshnessStatus === 'empty');

  useEffect(() => {
    if (!instrumentId || !needsAutoSync) return;
    if (autoSyncAttempted.current === instrumentId) return;
    if (syncMutation.isPending) return;
    autoSyncAttempted.current = instrumentId;
    void syncMutation.mutateAsync().then(
      () => {
        void statusQuery.refetch();
        void queryClient.invalidateQueries({ queryKey: ['data-status', instrumentId] });
      },
      () => void statusQuery.refetch(),
    );
  }, [instrumentId, needsAutoSync, queryClient, syncMutation, statusQuery]);

  useEffect(() => {
    autoSyncAttempted.current = null;
  }, [instrumentId]);

  return {
    status,
    isLoading: statusQuery.isLoading,
    isSyncing: syncMutation.isPending,
    refetch: statusQuery.refetch,
  };
}

export function invalidateInstrumentDataStatus(
  queryClient: ReturnType<typeof useQueryClient>,
  instrumentId: string,
  timeframe?: ChartTimeframe,
) {
  void queryClient.invalidateQueries({ queryKey: ['data-status', instrumentId, timeframe] });
  void queryClient.invalidateQueries({ queryKey: ['data-status', instrumentId] });
}
