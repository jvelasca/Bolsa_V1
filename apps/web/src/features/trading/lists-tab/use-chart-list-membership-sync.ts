import { useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import {
  membershipFingerprint,
  type ChartListMembershipSnapshot,
} from "@/lib/chart-list-membership";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { useVisualizationStore } from "@/stores/visualization-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

/**
 * Mantiene la membresía lista↔instrumento al día y reconcilia
 * sourceListId / chartListContext cuando cambian las listas.
 *
 * Usa GET /api/lists/memberships (1 request) en lugar de N× GET /lists/{id}.
 */
export function useChartListMembershipSync() {
  const accountScope = useActiveAccountQueryKey();
  const { pendingOrders } = usePendingOrders();
  const visualizationEntries = useVisualizationStore((state) => state.entries);
  const syncMembership = useWorkspaceStore(
    (state) => state.syncChartListMembership,
  );

  const listsQuery = useQuery({
    queryKey: ["lists"],
    queryFn: api.getLists,
    staleTime: 30_000,
  });

  const membershipsQuery = useQuery({
    queryKey: ["lists", "memberships"],
    queryFn: api.getListMemberships,
    staleTime: 30_000,
  });

  const apiLists = listsQuery.data?.data ?? [];
  const memberships = membershipsQuery.data?.data ?? null;

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
  });

  const membershipsSignature = useMemo(() => {
    if (!memberships) return "";
    return Object.keys(memberships)
      .sort()
      .map((id) => `${id}:${(memberships[id] ?? []).join(",")}`)
      .join("|");
  }, [memberships]);

  const pendingSignature = useMemo(
    () =>
      pendingOrders
        .map((order) => `${order.id}:${order.instrumentId}`)
        .join("|"),
    [pendingOrders],
  );

  const visualizationSignature = useMemo(
    () => visualizationEntries.map((entry) => entry.instrumentId).join(","),
    [visualizationEntries],
  );

  const portfolioSignature = useMemo(
    () =>
      (portfolioQuery.data?.data.positions ?? [])
        .map((position) => position.instrumentId)
        .join(","),
    // dataUpdatedAt es señal de refresco: recalcular memberships al refrescar portfolio
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [portfolioQuery.dataUpdatedAt, portfolioQuery.data?.data.positions],
  );

  const membership = useMemo((): ChartListMembershipSnapshot | null => {
    if (listsQuery.isLoading || membershipsQuery.isLoading) return null;
    if (!memberships) return null;

    const api: Record<string, ReadonlySet<string>> = {};
    for (const [listId, ids] of Object.entries(memberships)) {
      api[listId] = new Set(ids);
    }

    return {
      api,
      listMeta: apiLists.map((list) => ({ id: list.id, source: list.source })),
      virtual: {
        visualization: new Set(
          visualizationEntries.map((entry) => entry.instrumentId),
        ),
        portfolio: new Set(
          (portfolioQuery.data?.data.positions ?? []).map(
            (position) => position.instrumentId,
          ),
        ),
        pendingOrders: new Set(
          pendingOrders.map((order) => order.instrumentId),
        ),
      },
    };
    // Las *Signature ya son los fingerprints estables de pendingOrders/portfolio/
    // visualizationEntries; se evita recalcular el snapshot por identidad de array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    apiLists,
    listsQuery.isLoading,
    memberships,
    membershipsQuery.isLoading,
    membershipsSignature,
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
