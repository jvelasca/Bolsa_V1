/**
 * Batch FA + Composite/TA para hub Instrumentos (I2).
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  HUB_COMPOSITE_QUERY_CHUNK,
  HUB_FA_QUERY_CHUNK,
  chunkIds,
  indexFaScores,
  indexTaScores,
  type HubFaScore,
  type HubTaScore,
} from '@/features/instruments/instruments-hub-scores';

async function fetchFaChips(instrumentIds: string[]) {
  const chunks = chunkIds(instrumentIds, HUB_FA_QUERY_CHUNK);
  const parts = await Promise.all(
    chunks.map((ids) => api.queryInstrumentFundamentals({ instrumentIds: ids })),
  );
  return parts.flatMap((p) => p.data);
}

async function fetchCompositeChips(instrumentIds: string[]) {
  const chunks = chunkIds(instrumentIds, HUB_COMPOSITE_QUERY_CHUNK);
  const parts = await Promise.all(
    chunks.map((ids) =>
      api.queryInstrumentComposite({
        instrumentIds: ids,
        horizon: 'swing',
        regime: 'neutral',
      }),
    ),
  );
  return parts.flatMap((p) => p.data);
}

export function useInstrumentsHubScores(instrumentIds: string[]) {
  const idsKey = useMemo(() => [...instrumentIds].sort().join(','), [instrumentIds]);

  const faQuery = useQuery({
    queryKey: ['instrument-fundamentals-batch', 'hub', idsKey],
    queryFn: () => fetchFaChips(instrumentIds),
    enabled: instrumentIds.length > 0,
    staleTime: 60_000,
  });

  const taQuery = useQuery({
    queryKey: ['instrument-composite-batch', 'hub', idsKey],
    queryFn: () => fetchCompositeChips(instrumentIds),
    enabled: instrumentIds.length > 0,
    staleTime: 60_000,
  });

  const faByInstrument = useMemo(
    () => indexFaScores(faQuery.data ?? []),
    [faQuery.data],
  ) as Map<string, HubFaScore>;

  const taByInstrument = useMemo(
    () => indexTaScores(taQuery.data ?? []),
    [taQuery.data],
  ) as Map<string, HubTaScore>;

  return {
    faByInstrument,
    taByInstrument,
    scoresLoading: (faQuery.isLoading || taQuery.isLoading) && instrumentIds.length > 0,
    faReady: faQuery.isSuccess || faQuery.isError || instrumentIds.length === 0,
    taReady: taQuery.isSuccess || taQuery.isError || instrumentIds.length === 0,
  };
}
