/**
 * Mutations React Query del Hub Backtesting (`/backtests`).
 *
 * Extraído de `backtests-page.tsx` (Track B B3) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 */

import { useMutation, type QueryClient } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";
import type { NavigateFunction } from "react-router-dom";
import {
  strategyDefinitionFromChartDraft,
  type BacktestStrategyType,
  type ChartStrategySetupDraft,
  type ChartTimeframe,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import type {
  HubTab,
  ResultFocus,
  RunSource,
  StrategiesListFilter,
} from "@/features/backtests/backtests-page.constants";
import type { PeriodPreset } from "@/features/backtests/backtest-period";
import { resolveBacktestWindow } from "@/features/backtests/backtest-period";
import type { BatchRankRow } from "@/features/backtests/backtest-batch-run";
import type { ExplorePresetRow } from "@/features/backtests/backtest-explore-value";

export type UseBacktestPageMutationsParams = {
  queryClient: QueryClient;
  navigate: NavigateFunction;
  instrumentId: string;
  initialCash: string;
  runTimeframe: ChartTimeframe;
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  diaD: string;
  runSource: RunSource;
  savedStrategyId: string;
  strategyType: BacktestStrategyType;
  commissionBps: string;
  slippageBps: string;
  newStrategyName: string;
  newStrategyPreset: BacktestStrategyType;
  historyMaxKept: number;
  pruneHistory: (keep: number) => Promise<void>;
  selectRun: (
    id: string,
    options?: { tab?: HubTab; openAnalysis?: boolean; focus?: ResultFocus },
  ) => void;
  openLibrary: (opts?: {
    library?: StrategiesListFilter;
    strategyId?: string | null;
    preset?: string | null;
    q?: string | null;
  }) => void;
  setTab: (next: HubTab) => void;
  setBatchRows: Dispatch<SetStateAction<BatchRankRow[]>>;
  setExploreRows: Dispatch<SetStateAction<ExplorePresetRow[]>>;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  setNewStrategyName: Dispatch<SetStateAction<string>>;
  setCloneOpen: Dispatch<SetStateAction<boolean>>;
  setSavedStrategyId: Dispatch<SetStateAction<string>>;
  setRunSource: Dispatch<SetStateAction<RunSource>>;
};

export function useBacktestPageMutations(
  params: UseBacktestPageMutationsParams,
) {
  const {
    queryClient,
    navigate,
    instrumentId,
    initialCash,
    runTimeframe,
    periodPreset,
    customDateFrom,
    customDateTo,
    diaD,
    runSource,
    savedStrategyId,
    strategyType,
    commissionBps,
    slippageBps,
    newStrategyName,
    newStrategyPreset,
    historyMaxKept,
    pruneHistory,
    selectRun,
    openLibrary,
    setTab,
    setBatchRows,
    setExploreRows,
    setResultFocus,
    setNewStrategyName,
    setCloneOpen,
    setSavedStrategyId,
    setRunSource,
  } = params;

  const runMutation = useMutation({
    mutationFn: (overrides?: {
      instrumentId?: string;
      strategyDefinitionId?: string;
      initialCash?: number;
      timeframe?: ChartTimeframe;
      limit?: number;
      dateFrom?: string;
      dateTo?: string;
      labEvidence?: import("@bolsa/shared").PaperLabEvidenceSnapshot | null;
    }) => {
      const window =
        overrides?.dateFrom != null
          ? {
              dateFrom: overrides.dateFrom,
              ...(overrides.dateTo ? { dateTo: overrides.dateTo } : {}),
              limit: 10_000,
            }
          : overrides?.limit != null && overrides.limit > 0
            ? { limit: overrides.limit }
            : resolveBacktestWindow(
                periodPreset,
                customDateFrom,
                customDateTo,
                diaD,
              );
      const nextInstrumentId = overrides?.instrumentId ?? instrumentId;
      const nextCash = overrides?.initialCash ?? Number(initialCash);
      const nextTf = overrides?.timeframe ?? runTimeframe;
      return api.runBacktest({
        instrumentId: nextInstrumentId,
        ...(overrides?.strategyDefinitionId
          ? { strategyDefinitionId: overrides.strategyDefinitionId }
          : runSource === "saved"
            ? { strategyDefinitionId: savedStrategyId }
            : { strategyType }),
        initialCash: nextCash,
        commissionBps: Number(commissionBps) || 0,
        slippageBps: Number(slippageBps) || 0,
        timeframe: nextTf,
        ...window,
        ...(overrides?.labEvidence
          ? { labEvidence: overrides.labEvidence }
          : {}),
      });
    },
    onSuccess: (result) => {
      setBatchRows([]);
      setExploreRows([]);
      setResultFocus("detail");
      // Seed detail cache immediately so the chart does not wait on a second GET.
      queryClient.setQueryData(["backtest", result.data.id], {
        data: result.data,
      });
      selectRun(result.data.id, { tab: "run" });
      void pruneHistory(historyMaxKept);
      void queryClient.invalidateQueries({ queryKey: ["research"] });
    },
  });

  const createStrategyMutation = useMutation({
    mutationFn: () =>
      api.createStrategyFromPreset({
        name: newStrategyName.trim(),
        presetKey: newStrategyPreset,
        commissionBps: Number(commissionBps) || 0,
        slippageBps: Number(slippageBps) || 0,
      }),
    onSuccess: () => {
      setNewStrategyName("");
      setCloneOpen(false);
      openLibrary({ library: "optimized" });
      void queryClient.invalidateQueries({ queryKey: ["strategies"] });
    },
  });

  const deployPaperMutation = useMutation({
    mutationFn: (payload: {
      strategyId: string;
      runId?: string;
      initialDeposit?: number;
      labEvidence?: import("@bolsa/shared").PaperLabEvidenceSnapshot | null;
    }) =>
      payload.runId
        ? api.deployBacktestPaperAccount(payload.runId, {
            initialDeposit: payload.initialDeposit,
            labEvidence: payload.labEvidence ?? undefined,
          })
        : api.deployStrategyPaperAccount(payload.strategyId, {
            initialDeposit: payload.initialDeposit,
            labEvidence: payload.labEvidence ?? undefined,
          }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      navigate(`/accounts?type=paper&selected=${result.data.id}`, {
        state: {
          paperLabEvidence: result.data.labEvidence ?? null,
          paperDeployNote:
            "Cuenta paper creada. Evidencia lab = provenance, no producción.",
        },
      });
    },
  });

  const saveChartStrategyMutation = useMutation({
    mutationFn: ({
      draft,
      name,
    }: {
      draft: ChartStrategySetupDraft;
      name: string;
    }) => {
      if (draft.inferredPresetKey) {
        return api.createStrategyFromPreset({
          name,
          presetKey: draft.inferredPresetKey,
          timeframe: draft.timeframe,
          commissionBps: Number(commissionBps) || 0,
          slippageBps: Number(slippageBps) || 0,
        });
      }
      return api.createStrategy({
        name,
        definition: strategyDefinitionFromChartDraft(draft, name),
      });
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["strategies"] });
      setSavedStrategyId(result.data.id);
      setRunSource("saved");
      setTab("run");
    },
  });

  return {
    runMutation,
    createStrategyMutation,
    deployPaperMutation,
    saveChartStrategyMutation,
  };
}
