/**
 * V1.41.2 — misma fuente de entriesBlocked en Mercado / Hoy / Journal / Operaciones.
 * Kill switch + incidentes + vetoed del board. Fail-closed si fallan los incidentes.
 * No recalcula DS-05 de cartera (atención, no bloqueo global).
 */

import { useQuery } from "@tanstack/react-query";
import { mesaEntriesBlocked } from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

const STALE_MS = 15_000;
const REFETCH_MS = 60_000;

export type MesaEntriesBlockedStateV1 = {
  entriesBlocked: boolean;
  killOn: boolean;
  vetoed: number;
  incidentCount: number;
  incidentsFailed: boolean;
};

export function useMesaEntriesBlocked(): MesaEntriesBlockedStateV1 {
  const accountScope = useActiveAccountQueryKey();
  const { effectiveAccountId } = useActiveAccount();

  const killQuery = useQuery({
    queryKey: ["risk-kill-switch"],
    queryFn: () => api.getRiskKillSwitch(),
    staleTime: STALE_MS,
    refetchInterval: REFETCH_MS,
  });

  const boardQuery = useQuery({
    queryKey: ["decision-board", accountScope],
    queryFn: () => api.getDecisionBoard(accountScope!),
    enabled: Boolean(accountScope),
    staleTime: STALE_MS,
    refetchInterval: REFETCH_MS,
  });

  const incidentsQuery = useQuery({
    queryKey: ["operational-incidents-active", effectiveAccountId],
    queryFn: () => api.getActiveOperationalIncidents(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: STALE_MS,
    refetchInterval: REFETCH_MS,
  });

  const killOn = killQuery.data?.effective === true;
  const vetoed = boardQuery.data?.data?.buckets?.vetoed ?? 0;
  const incidentsFailed = incidentsQuery.isError;
  const incidents = incidentsFailed
    ? []
    : (incidentsQuery.data?.data?.incidents ?? []);
  const incidentCount = incidentsFailed
    ? -1
    : (incidentsQuery.data?.data?.incidents?.length ?? 0);

  const entriesBlocked =
    incidentsFailed ||
    mesaEntriesBlocked({
      killSwitchEffective: killOn,
      incidents,
      vetoed,
    });

  return {
    entriesBlocked,
    killOn,
    vetoed,
    incidentCount,
    incidentsFailed,
  };
}
