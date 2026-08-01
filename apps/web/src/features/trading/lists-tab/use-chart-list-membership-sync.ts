import { useEffect, useMemo, useRef } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';
import {
  membershipFingerprint,
  type ChartListMembershipSnapshot,
} from '@/lib/chart-list-membership';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';
import { usePendingOrders } from '@/features/trading/use-pending-orders';
import { useVisualizationStore } from '@/stores/visualization-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

/**
 * Mantiene la membresía lista↔instrumento al día y reconcilia
 * sourceListId / chartListContext cuando cambian las listas.
 */
export function useChartListMembershipSync() {
  const accountScope = useActiveAccountQueryKey();
  const { pendingOrders } = usePendingOrders();
  const visualizationEntries = useVisualizationStore((state) => state.entries);
  const syncMembership = useWorkspaceStore((state) => state.syncChartListMembership);

  const listsQuery = useQuery({
    queryKey: ['lists'],
    queryFn: api.getLists,
    staleTime: 30_000,
  });

  const apiLists = listsQuery.data?.data ?? [];
  const listIds = useMemo(() => apiLists.map((list) => list.id), [apiLists]);

  const detailsQueries = useQueries({
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

  const listDetailsSignature = useMemo(
    () =>
      detailsQueries
        .map((query) => {
          const detail = query.data?.data;
          if (!detail) return '';
          return `${detail.id}:${detail.instrumentIds.join(',')}`;
        })
        .join('|'),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- firma estable desde datos de query
    [detailsQueries.map((query) => query.dataUpdatedAt).join('|'), listIds.join('|')],
  );

  const pendingSignature = useMemo(
    () => pendingOrders.map((order) => `${order.id}:${order.instrumentId}`).join('|'),
    [pendingOrders],
  );

  const visualizationSignature = useMemo(
    () => visualizationEntries.map((entry) => entry.instrumentId).join(','),
    [visualizationEntries],
  );

  const portfolioSignature = useMemo(
    () =>
      (portfolioQuery.data?.data.positions ?? [])
        .map((position) => position.instrumentId)
        .join(','),
    [portfolioQuery.dataUpdatedAt, portfolioQuery.data?.data.positions],
  );

  const membership = useMemo((): ChartListMembershipSnapshot | null => {
    if (listsQuery.isLoading) return null;
    if (listIds.length > 0 && detailsQueries.some((query) => query.isLoading)) return null;

    const api: Record<string, ReadonlySet<string>> = {};
    for (const query of detailsQueries) {
      const detail = query.data?.data;
      if (!detail) continue;
      api[detail.id] = new Set(detail.instrumentIds);
    }

    return {
      api,
      listMeta: apiLists.map((list) => ({ id: list.id, source: list.source })),
      virtual: {
        visualization: new Set(visualizationEntries.map((entry) => entry.instrumentId)),
        portfolio: new Set(
          (portfolioQuery.data?.data.positions ?? []).map((position) => position.instrumentId),
        ),
        pendingOrders: new Set(pendingOrders.map((order) => order.instrumentId)),
      },
    };
  }, [
    apiLists,
    listDetailsSignature,
    listIds.length,
    listsQuery.isLoading,
    pendingSignature,
    portfolioSignature,
    visualizationSignature,
  ]);

  const membershipKey = membership ? membershipFingerprint(membership) : null;
  const membershipRef = useRef(membership);
  membershipRef.current = membership;
  const lastSyncedKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (!membershipKey || !membershipRef.current) return;
    if (lastSyncedKeyRef.current === membershipKey) return;
    lastSyncedKeyRef.current = membershipKey;
    syncMembership(membershipRef.current);
  }, [membershipKey, syncMembership]);
}
