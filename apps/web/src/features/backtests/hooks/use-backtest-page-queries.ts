/**
 * Queries React Query del Hub Backtesting (`/backtests`).
 *
 * Extraído de `backtests-page.tsx` (Track B B2) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 */

import { useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import type { ChartTimeframe } from "@bolsa/shared";
import { api } from "@/lib/api";
import type { UniverseMode } from "@/features/backtests/backtests-page.constants";
import type { PeriodPreset } from "@/features/backtests/backtest-period";
import { saveBacktestRunContext } from "@/features/backtests/backtest-run-context";
import {
  formatCoachProfileRailLabel,
  resolveCoachProfilePolicy,
} from "@/features/backtests/coach-profile-policy";
import { isFinalistsFreshnessContextReady } from "@/features/backtests/backtest-finalists-freshness";

export type UseBacktestPageQueriesParams = {
  listId: string;
  universeMode: UniverseMode;
  instrumentId: string;
  runTimeframe: ChartTimeframe;
  effectiveAccountId: string | null | undefined;
  selectedId: string | null;
  historyMaxKept: number;
  includeMineStrategies: boolean;
  includeOptimizedStrategies: boolean;
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  diaD: string;
  initialCash: string;
  commissionBps: string;
  slippageBps: string;
};

export function useBacktestPageQueries(params: UseBacktestPageQueriesParams) {
  const {
    listId,
    universeMode,
    instrumentId,
    runTimeframe,
    effectiveAccountId,
    selectedId,
    historyMaxKept,
    includeMineStrategies,
    includeOptimizedStrategies,
    periodPreset,
    customDateFrom,
    customDateTo,
    diaD,
    initialCash,
    commissionBps,
    slippageBps,
  } = params;

  const instrumentsQuery = useQuery({
    queryKey: ["instruments"],
    queryFn: api.getInstruments,
    staleTime: 60_000,
  });

  const listsQuery = useQuery({
    queryKey: ["lists"],
    queryFn: api.getLists,
  });

  const listDetailQuery = useQuery({
    queryKey: ["list", listId],
    queryFn: () => api.getList(listId),
    enabled: universeMode === "list" && Boolean(listId),
  });

  /** Símbolos/nombres de la lista activa (cubre índices recién suscritos aún no en catálogo cacheado). */
  const listQuotesQuery = useQuery({
    queryKey: ["list-quotes", listId],
    queryFn: () => api.getListQuotes(listId),
    enabled: universeMode === "list" && Boolean(listId),
    staleTime: 30_000,
  });

  const listMemberIdsKey = useMemo(() => {
    const ids = listQuotesQuery.data?.data?.map((q) => q.id) ?? [];
    return ids.slice().sort().join(",");
  }, [listQuotesQuery.data?.data]);

  /** TOPs en batch para resumen de estado en Lista valores. */
  const listTopsQuery = useQuery({
    queryKey: [
      "instrument-strategy-tops-batch",
      listId,
      runTimeframe,
      listMemberIdsKey,
    ],
    queryFn: () =>
      api.queryInstrumentStrategyTops({
        instrumentIds: (listQuotesQuery.data?.data ?? []).map((q) => q.id),
        timeframe: runTimeframe,
      }),
    enabled:
      universeMode === "list" &&
      Boolean(listId) &&
      Boolean(listMemberIdsKey) &&
      (listQuotesQuery.data?.data.length ?? 0) > 0,
    staleTime: 20_000,
  });

  /** Chips FA en batch (PR3) — Score_FUND compacto por miembro. */
  const listFaQuery = useQuery({
    queryKey: ["instrument-fundamentals-batch", listId, listMemberIdsKey],
    queryFn: () =>
      api.queryInstrumentFundamentals({
        instrumentIds: (listQuotesQuery.data?.data ?? []).map((q) => q.id),
      }),
    enabled:
      universeMode === "list" &&
      Boolean(listId) &&
      Boolean(listMemberIdsKey) &&
      (listQuotesQuery.data?.data.length ?? 0) > 0,
    staleTime: 60_000,
  });

  const strategiesQuery = useQuery({
    queryKey: ["strategies"],
    queryFn: api.getStrategies,
  });

  const instrumentTopQuery = useQuery({
    queryKey: ["instrument-strategy-top", instrumentId, runTimeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId, runTimeframe),
    enabled: Boolean(instrumentId),
    staleTime: 15_000,
    retry: false,
  });

  /** Perfil de la cuenta activa → CORE-P gate Coach¹→Lab. */
  const accountProfileQuery = useQuery({
    queryKey: ["account-active-profile", effectiveAccountId],
    queryFn: () => api.getAccountActiveProfile(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 60_000,
  });

  const coachProfilePolicy = useMemo(
    () =>
      resolveCoachProfilePolicy({
        profileId: accountProfileQuery.data?.data?.profileId,
        profileName: accountProfileQuery.data?.data?.name,
        horizon: accountProfileQuery.data?.data?.declared?.horizon ?? null,
        riskTolerance:
          accountProfileQuery.data?.data?.declared?.riskTolerance ?? null,
      }),
    [accountProfileQuery.data?.data],
  );

  const coachProfileRailLabel = useMemo(
    () => formatCoachProfileRailLabel(coachProfilePolicy),
    [coachProfilePolicy],
  );

  const playContextKey = `${effectiveAccountId ?? ""}|${coachProfilePolicy.profileId ?? "none"}`;

  /** Persist periodo/costes/TF/DÍA D — misma huella de frescura tras reinicio. */
  useEffect(() => {
    saveBacktestRunContext({
      periodPreset,
      customDateFrom,
      customDateTo,
      diaD,
      initialCash,
      commissionBps,
      slippageBps,
      timeframe: runTimeframe,
    });
  }, [
    periodPreset,
    customDateFrom,
    customDateTo,
    diaD,
    initialCash,
    commissionBps,
    slippageBps,
    runTimeframe,
  ]);

  const freshnessContextReady = isFinalistsFreshnessContextReady({
    instrumentsFetched: instrumentsQuery.isFetched,
    accountProfileReady: !effectiveAccountId || accountProfileQuery.isFetched,
    strategiesReady:
      !(includeMineStrategies || includeOptimizedStrategies) ||
      strategiesQuery.isFetched,
  });
  const playContextKeyRef = useRef<string | null>(null);

  const topStrategyIds = useMemo(() => {
    const ids = new Set<string>();
    for (const slot of instrumentTopQuery.data?.data?.slots ?? []) {
      if (slot.strategyDefinitionId) ids.add(slot.strategyDefinitionId);
    }
    return ids;
  }, [instrumentTopQuery.data?.data?.slots]);

  const missingFinalistIds = useMemo(() => {
    const have = new Set((strategiesQuery.data?.data ?? []).map((s) => s.id));
    return [...topStrategyIds].filter((id) => !have.has(id));
  }, [strategiesQuery.data?.data, topStrategyIds]);

  const missingFinalistQueries = useQueries({
    queries: missingFinalistIds.map((id) => ({
      queryKey: ["strategy", id] as const,
      queryFn: () => api.getStrategy(id),
      staleTime: 60_000,
      retry: false,
    })),
  });
  const missingFinalistKey = missingFinalistQueries
    .map((q) => q.data?.data?.id ?? "")
    .join(",");

  const runsQuery = useQuery({
    queryKey: ["backtests", historyMaxKept],
    queryFn: () => api.getBacktests(historyMaxKept),
  });

  const detailQuery = useQuery({
    queryKey: ["backtest", selectedId],
    queryFn: () => api.getBacktest(selectedId!),
    enabled: Boolean(selectedId),
  });

  return {
    instrumentsQuery,
    listsQuery,
    listDetailQuery,
    listQuotesQuery,
    listMemberIdsKey,
    listTopsQuery,
    listFaQuery,
    strategiesQuery,
    instrumentTopQuery,
    accountProfileQuery,
    coachProfilePolicy,
    coachProfileRailLabel,
    playContextKey,
    freshnessContextReady,
    playContextKeyRef,
    topStrategyIds,
    missingFinalistIds,
    missingFinalistQueries,
    missingFinalistKey,
    runsQuery,
    detailQuery,
  };
}
