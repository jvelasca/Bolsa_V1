/**
 * Derivados + detail anti-stale del Hub Backtesting (`/backtests`).
 *
 * Extraído de `backtests-page.tsx` (Track B B4) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 */

import { useMemo } from "react";
import type {
  BacktestRunDetailDto,
  BacktestRunDto,
  FundamentalChipDto,
  InstrumentListDetailDto,
  InstrumentListSummaryDto,
  InstrumentStrategyTopV1,
  InstrumentWithMetaDto,
  StrategyDefinitionDetailDto,
  StrategyDefinitionSummaryDto,
} from "@bolsa/shared";
import type { StrategiesListFilter } from "@/features/backtests/backtests-page.constants";
import {
  isAssistantStepComplete,
  resolveAssistantActiveStep,
  type AssistantSessionProgress,
} from "@/features/backtests/backtest-assistant-completion";
import type { AssistantStepId } from "@/features/backtests/backtest-assistant-steps";
import { instrumentTopIsDurable } from "@/features/backtests/backtest-assistant-full-cycle";
import type { ExplorePresetRow } from "@/features/backtests/backtest-explore-value";
import { resolveMatrixCoachTargetIds } from "@/features/backtests/backtest-explore-value";
import type { ListAutoBoardState } from "@/features/backtests/backtest-list-auto-board";
import { summarizeListMemberFa } from "@/features/backtests/backtest-list-member-fa";
import { summarizeListMemberBacktest } from "@/features/backtests/backtest-list-member-status";
import {
  annotateStrategyMatrixRowsWithTop,
  type StrategyMatrixFilter,
  type StrategyMatrixRow,
  type StrategyMatrixRunProgress,
} from "@/features/backtests/backtest-strategy-matrix";
import { finalistHudBadgeFromTop } from "@/features/backtests/instrument-top-match";
import { filterStrategiesByLibraryBucket } from "@/features/backtests/library-strategy-buckets";
import {
  filterMineStrategies,
  uniqueSortedValues,
  type MineStrategiesFilterState,
} from "@/features/backtests/mine-strategies-filters";

/** Forma mínima de `UseQueryResult` / mutation result usada por los derivados. */
type QueryData<T> = { data?: { data: T } | undefined };
type MissingFinalistQuery = {
  data?: { data?: StrategyDefinitionDetailDto } | undefined;
  isPending: boolean;
  isFetching: boolean;
};

export type UseBacktestDerivedDataParams = {
  instrumentsQuery: QueryData<InstrumentWithMetaDto[]>;
  listsQuery: QueryData<InstrumentListSummaryDto[]>;
  listDetailQuery: QueryData<InstrumentListDetailDto>;
  listQuotesQuery: QueryData<InstrumentWithMetaDto[]>;
  listTopsQuery: QueryData<InstrumentStrategyTopV1[]>;
  listFaQuery: QueryData<FundamentalChipDto[]>;
  listAutoBoard: ListAutoBoardState | null;
  strategiesQuery: QueryData<StrategyDefinitionSummaryDto[]>;
  missingFinalistQueries: readonly MissingFinalistQuery[];
  missingFinalistKey: string;
  missingFinalistIds: string[];
  runsQuery: QueryData<BacktestRunDto[]>;
  instrumentTopQuery: QueryData<InstrumentStrategyTopV1 | null>;
  topStrategyIds: Set<string>;
  strategiesListFilter: StrategiesListFilter;
  mineFilters: MineStrategiesFilterState;
  instrumentId: string;
  exploreRows: ExplorePresetRow[];
  exploreProgress: { done: number; total: number };
  assistantProgress: AssistantSessionProgress;
  assistantFocus: AssistantStepId | null;
  detailQuery: QueryData<BacktestRunDetailDto>;
  selectedId: string | null;
  runMutation: QueryData<BacktestRunDetailDto>;
  matrixRows: StrategyMatrixRow[];
  matrixFilter: StrategyMatrixFilter;
  matrixSelectedIds: Set<string>;
};

export function useBacktestDerivedData(params: UseBacktestDerivedDataParams) {
  const {
    instrumentsQuery,
    listsQuery,
    listDetailQuery,
    listQuotesQuery,
    listTopsQuery,
    listFaQuery,
    listAutoBoard,
    strategiesQuery,
    missingFinalistQueries,
    missingFinalistKey,
    missingFinalistIds,
    runsQuery,
    instrumentTopQuery,
    topStrategyIds,
    strategiesListFilter,
    mineFilters,
    instrumentId,
    exploreRows,
    exploreProgress,
    assistantProgress,
    assistantFocus,
    detailQuery,
    selectedId,
    runMutation,
    matrixRows,
    matrixFilter,
    matrixSelectedIds,
  } = params;

  const instruments = useMemo(
    () => instrumentsQuery.data?.data ?? [],
    [instrumentsQuery.data?.data],
  );
  const lists = listsQuery.data?.data ?? [];
  const listDetail = listDetailQuery.data?.data;
  const listQuotes = useMemo(
    () => listQuotesQuery.data?.data ?? [],
    [listQuotesQuery.data?.data],
  );
  const listTopsById = useMemo(() => {
    const map = new Map<
      string,
      import("@bolsa/shared").InstrumentStrategyTopV1
    >();
    for (const top of listTopsQuery.data?.data ?? []) {
      map.set(top.instrumentId, top);
    }
    return map;
  }, [listTopsQuery.data?.data]);
  const listFaById = useMemo(() => {
    const map = new Map<string, import("@bolsa/shared").FundamentalChipDto>();
    for (const row of listFaQuery.data?.data ?? []) {
      map.set(row.instrumentId, row);
    }
    return map;
  }, [listFaQuery.data?.data]);
  const listAutoPhaseById = useMemo(() => {
    const map = new Map<
      string,
      import("@/features/backtests/backtest-list-auto-board").ListAutoRowPhase
    >();
    for (const row of listAutoBoard?.rows ?? []) {
      map.set(row.instrumentId, row.phase);
    }
    return map;
  }, [listAutoBoard]);
  const listMembersWithStatus = useMemo(
    () =>
      listQuotes.map((q) => ({
        id: q.id,
        symbol: q.symbol,
        name: q.name,
        status: summarizeListMemberBacktest({
          top: listTopsById.get(q.id) ?? null,
          autoPhase: listAutoPhaseById.get(q.id) ?? null,
        }),
        fa: summarizeListMemberFa(listFaById.get(q.id) ?? null),
      })),
    [listQuotes, listTopsById, listAutoPhaseById, listFaById],
  );
  const strategies = useMemo(() => {
    const base = strategiesQuery.data?.data ?? [];
    const byId = new Map(base.map((s) => [s.id, s]));
    for (const q of missingFinalistQueries) {
      const d = q.data?.data;
      if (!d || byId.has(d.id)) continue;
      byId.set(d.id, {
        id: d.id,
        name: d.name,
        presetKey: d.presetKey,
        origin: d.origin,
        timeframe: d.timeframe,
        kind: d.kind,
        instrumentIds:
          d.instrumentIds ?? d.definition?.universe?.instrumentIds ?? [],
        updatedAt: d.updatedAt,
        createdAt: d.createdAt,
      });
    }
    return [...byId.values()];
    // missingFinalistKey es señal de refresco: recalcula `strategies` cuando se
    // resuelven los lookups huérfanos asíncronos de finalists (missingFinalistQueries).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategiesQuery.data?.data, missingFinalistKey, missingFinalistQueries]);
  const runs = runsQuery.data?.data ?? [];
  const instrumentTop = instrumentTopQuery.data?.data ?? null;
  const knownStrategyIds = useMemo(
    () => new Set(strategies.map((s) => s.id)),
    [strategies],
  );
  /**
   * Mientras hay lookups de slots huérfanos en vuelo, asumir TOP durable
   * (no pisar). Cuando fallan todos → huérfano ≡ sin TOP.
   */
  const finalistStrategyLookupPending =
    missingFinalistIds.length > 0 &&
    missingFinalistQueries.some((q) => q.isPending || q.isFetching);
  const hasDurableInstrumentTop = instrumentTopIsDurable(
    instrumentTop,
    knownStrategyIds,
  );
  const hasExistingTopForSave = !instrumentTop
    ? false
    : finalistStrategyLookupPending
      ? true
      : hasDurableInstrumentTop;
  const instrumentSymbolById = useMemo(() => {
    const map = new Map<string, string>();
    for (const inst of instruments) {
      map.set(inst.id, inst.symbol);
    }
    return map;
  }, [instruments]);

  const mineFilterTimeframes = useMemo(
    () => uniqueSortedValues(strategies.map((s) => s.timeframe)),
    [strategies],
  );
  const mineFilterOrigins = useMemo(
    () => uniqueSortedValues(strategies.map((s) => s.origin)),
    [strategies],
  );
  const mineFilterInstruments = useMemo(() => {
    const ids = new Set<string>();
    for (const s of strategies) {
      for (const id of s.instrumentIds ?? []) {
        if (id) ids.add(id);
      }
    }
    return [...ids]
      .map((id) => ({
        id,
        symbol: instrumentSymbolById.get(id) ?? id.slice(0, 8),
      }))
      .sort((a, b) => a.symbol.localeCompare(b.symbol, "es"));
  }, [strategies, instrumentSymbolById]);

  const filteredStrategies = useMemo(() => {
    if (strategiesListFilter === "generics") {
      return [];
    }
    const base =
      strategiesListFilter === "finalists"
        ? strategies.filter((s) => topStrategyIds.has(s.id))
        : filterStrategiesByLibraryBucket(strategies, strategiesListFilter);
    return filterMineStrategies(base, mineFilters, {
      currentInstrumentId: instrumentId,
      symbolById: instrumentSymbolById,
    });
  }, [
    strategies,
    strategiesListFilter,
    topStrategyIds,
    mineFilters,
    instrumentId,
    instrumentSymbolById,
  ]);

  const exploreOkCount = exploreRows.filter((r) => r.status === "ok").length;
  const coachRunProgress = useMemo((): StrategyMatrixRunProgress => {
    const ok = exploreRows.filter((r) => r.status === "ok").length;
    const error = exploreRows.filter((r) => r.status === "error").length;
    const skipped = exploreRows.filter((r) => r.status === "skipped").length;
    const runningLabels = exploreRows
      .filter((r) => r.status === "running")
      .map((r) => r.label)
      .slice(0, 3);
    const pending = Math.max(0, exploreProgress.total - exploreProgress.done);
    return {
      done: exploreProgress.done,
      total: exploreProgress.total,
      ok,
      error,
      skipped,
      pending,
      runningLabels,
    };
  }, [exploreRows, exploreProgress]);
  const assistantStep = resolveAssistantActiveStep(
    assistantProgress,
    assistantFocus,
  );
  const assistantStepComplete: Partial<Record<AssistantStepId, boolean>> = {
    universe: isAssistantStepComplete("universe", assistantProgress),
    semifinal: isAssistantStepComplete("semifinal", assistantProgress),
    lab: isAssistantStepComplete("lab", assistantProgress),
    finalists: isAssistantStepComplete("finalists", assistantProgress),
  };

  // Never fall back to a stale mutation run when viewing another selectedId (ranking → detalle).
  const rawDetail =
    (detailQuery.data?.data?.id === selectedId
      ? detailQuery.data.data
      : undefined) ??
    (runMutation.data?.data?.id === selectedId
      ? runMutation.data.data
      : undefined);
  // Tras cambiar de valor, no reutilizar el detalle del instrumento anterior.
  const detail =
    rawDetail && instrumentId && rawDetail.instrumentId === instrumentId
      ? rawDetail
      : rawDetail && !instrumentId
        ? rawDetail
        : undefined;

  const detailFinalistBadge = useMemo(
    () => (detail ? finalistHudBadgeFromTop(detail, instrumentTop) : null),
    [detail, instrumentTop],
  );

  const instrumentLabels = useMemo(() => {
    const map: Record<string, { symbol: string; name: string }> = {};
    for (const inst of instruments) {
      map[inst.id] = { symbol: inst.symbol, name: inst.name };
    }
    // Quotes de la lista pisan/completan: prioritario tras suscribir SP100/etc.
    for (const inst of listQuotes) {
      map[inst.id] = { symbol: inst.symbol, name: inst.name };
    }
    return map;
  }, [instruments, listQuotes]);

  const instrumentSymbol = instrumentLabels[instrumentId]?.symbol ?? null;

  const matrixRowsForUi = useMemo(
    () => annotateStrategyMatrixRowsWithTop(matrixRows, instrumentTop),
    [matrixRows, instrumentTop],
  );

  /** Lote del botón Probar + coach: selección del filtro, o todas las del filtro. */
  const matrixCoachTargetIds = useMemo(
    () =>
      resolveMatrixCoachTargetIds(
        matrixRowsForUi,
        matrixFilter,
        matrixSelectedIds,
      ),
    [matrixRowsForUi, matrixFilter, matrixSelectedIds],
  );

  return {
    instruments,
    lists,
    listDetail,
    listQuotes,
    listTopsById,
    listFaById,
    listAutoPhaseById,
    listMembersWithStatus,
    strategies,
    runs,
    instrumentTop,
    knownStrategyIds,
    finalistStrategyLookupPending,
    hasDurableInstrumentTop,
    hasExistingTopForSave,
    instrumentSymbolById,
    mineFilterTimeframes,
    mineFilterOrigins,
    mineFilterInstruments,
    filteredStrategies,
    exploreOkCount,
    coachRunProgress,
    assistantStep,
    assistantStepComplete,
    rawDetail,
    detail,
    detailFinalistBadge,
    instrumentLabels,
    instrumentSymbol,
    matrixRowsForUi,
    matrixCoachTargetIds,
  };
}
