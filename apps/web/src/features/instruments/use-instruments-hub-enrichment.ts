/**
 * Carga listas + portfolio para el hub Instrumentos (I1).
 * Reutiliza query keys de Trading: ['lists'], ['list', id], ['portfolio', accountScope].
 */

import { useMemo } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import type { PositionDto } from '@bolsa/shared';
import { api } from '@/lib/api';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';
import {
  indexPositionsByInstrument,
  invertListMemberships,
  type HubListMembership,
} from '@/features/instruments/instruments-hub-enrichment';

export function useInstrumentsHubEnrichment() {
  const accountScope = useActiveAccountQueryKey();

  const listsQuery = useQuery({
    queryKey: ['lists'],
    queryFn: api.getLists,
    staleTime: 30_000,
  });

  const apiLists = listsQuery.data?.data ?? [];
  const listIds = apiLists.map((l) => l.id);

  const detailQueries = useQueries({
    queries: listIds.map((id) => ({
      queryKey: ['list', id],
      queryFn: () => api.getList(id),
      enabled: listIds.length > 0,
      staleTime: 30_000,
    })),
  });

  const portfolioQuery = useQuery({
    queryKey: ['portfolio', accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
  });

  const membershipsByInstrument = useMemo(() => {
    const details = detailQueries
      .map((q) => q.data?.data)
      .filter((d): d is NonNullable<typeof d> => Boolean(d));
    return invertListMemberships(
      details.map((d) => ({
        id: d.id,
        name: d.name,
        source: d.source,
        instrumentIds: d.instrumentIds,
      })),
    );
  }, [detailQueries]);

  const positionsByInstrument = useMemo(
    () => indexPositionsByInstrument(portfolioQuery.data?.data.positions ?? []),
    [portfolioQuery.data?.data.positions],
  );

  const listsReady =
    listIds.length === 0 || detailQueries.every((q) => q.isSuccess || q.isError);
  const portfolioReady = portfolioQuery.isSuccess || portfolioQuery.isError;

  return {
    membershipsByInstrument: membershipsByInstrument as Map<string, HubListMembership[]>,
    positionsByInstrument: positionsByInstrument as Map<string, PositionDto>,
    apiLists,
    listsLoading: listsQuery.isLoading || (listIds.length > 0 && !listsReady),
    portfolioLoading: portfolioQuery.isLoading && !portfolioReady,
    accountScope,
  };
}
