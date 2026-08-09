/**
 * Carga listas + portfolio para el hub Instrumentos (I1).
 * Reutiliza query keys: ['lists'], ['lists','memberships'], ['portfolio', accountScope].
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
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

  const membershipsQuery = useQuery({
    queryKey: ['lists', 'memberships'],
    queryFn: api.getListMemberships,
    staleTime: 30_000,
  });

  const apiLists = useMemo(() => listsQuery.data?.data ?? [], [listsQuery.data?.data]);

  const portfolioQuery = useQuery({
    queryKey: ['portfolio', accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
  });

  const membershipsByInstrument = useMemo(() => {
    const memberships = membershipsQuery.data?.data ?? {};
    const details = apiLists.map((list) => ({
      id: list.id,
      name: list.name,
      source: list.source,
      instrumentIds: memberships[list.id] ?? [],
    }));
    return invertListMemberships(details);
  }, [apiLists, membershipsQuery.data?.data]);

  const positionsByInstrument = useMemo(
    () => indexPositionsByInstrument(portfolioQuery.data?.data.positions ?? []),
    [portfolioQuery.data?.data.positions],
  );

  const listsReady =
    apiLists.length === 0 ||
    membershipsQuery.isSuccess ||
    membershipsQuery.isError;
  const portfolioReady = portfolioQuery.isSuccess || portfolioQuery.isError;

  return {
    membershipsByInstrument: membershipsByInstrument as Map<string, HubListMembership[]>,
    positionsByInstrument: positionsByInstrument as Map<string, PositionDto>,
    apiLists,
    listsLoading: listsQuery.isLoading || membershipsQuery.isLoading || !listsReady,
    portfolioLoading: portfolioQuery.isLoading && !portfolioReady,
    accountScope,
  };
}
