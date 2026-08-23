/**
 * Tab `jobs` (Lab · Optimizar) extraída de `BacktestsPage`.
 *
 * Extraído de `backtests-page.tsx` (Track B B11) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 *
 * Presentacional: props in, JSX out. Sin hooks. Recrear el ViewModel cada
 * render en el shell (no memoizar): el original no estaba memoizado.
 */

import type { Dispatch, SetStateAction } from "react";
import type { ChartTimeframe } from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import type { HubTab } from "@/features/backtests/backtest-hub-nav";
import type { LabBoardZone } from "@/features/backtests/backtest-lab-board-types";
import {
  buildOptimizeBeforeAfter,
  type OptimizeBeforeAfterSnapshot,
} from "@/features/backtests/backtest-optimize-delta";
import { BacktestOptimizeCompareCard } from "@/features/backtests/backtest-optimize-compare-card";
import { BacktestOptimizePanel } from "@/features/backtests/backtest-optimize-panel";
import type { OptimizeSeed } from "@/features/backtests/backtest-optimize-seed";
import type { PeriodPreset } from "@/features/backtests/backtest-period";
import type {
  ResultFocus,
  RunSource,
  UniverseMode,
} from "@/features/backtests/backtests-page.constants";
import type { CoachProfilePolicy } from "@/features/backtests/coach-profile-policy";
import { useBacktestPageMutations } from "@/features/backtests/hooks/use-backtest-page-mutations";
import { useBacktestPageQueries } from "@/features/backtests/hooks/use-backtest-page-queries";

type Queries = ReturnType<typeof useBacktestPageQueries>;
type Mutations = ReturnType<typeof useBacktestPageMutations>;

export type BacktestPageJobsViewModel = {
  optimizeSeed: OptimizeSeed | null;
  setOptimizeSeed: Dispatch<SetStateAction<OptimizeSeed | null>>;
  labZones: LabBoardZone[] | null;
  setTab: (next: HubTab) => void;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  optimizeCompare: OptimizeBeforeAfterSnapshot | null;
  setOptimizeCompare: Dispatch<
    SetStateAction<OptimizeBeforeAfterSnapshot | null>
  >;
  instrumentsQuery: Pick<Queries["instrumentsQuery"], "data">;
  instrumentId: string;
  coachProfilePolicy: CoachProfilePolicy;
  setSavedStrategyId: Dispatch<SetStateAction<string>>;
  setRunSource: Dispatch<SetStateAction<RunSource>>;
  setInstrumentId: Dispatch<SetStateAction<string>>;
  setInitialCash: Dispatch<SetStateAction<string>>;
  setRunTimeframe: Dispatch<SetStateAction<ChartTimeframe>>;
  setPeriodPreset: Dispatch<SetStateAction<PeriodPreset>>;
  setUniverseMode: Dispatch<SetStateAction<UniverseMode>>;
  runMutation: Pick<Mutations["runMutation"], "mutate">;
};

export function BacktestsPageJobsTab({
  vm,
}: {
  vm: BacktestPageJobsViewModel;
}) {
  const {
    coachProfilePolicy,
    instrumentId,
    instrumentsQuery,
    labZones,
    optimizeCompare,
    optimizeSeed,
    runMutation,
    setInitialCash,
    setInstrumentId,
    setOptimizeCompare,
    setOptimizeSeed,
    setPeriodPreset,
    setResultFocus,
    setRunSource,
    setRunTimeframe,
    setSavedStrategyId,
    setTab,
    setUniverseMode,
  } = vm;

  return (
    <div className="mx-auto min-h-0 w-full max-w-[1600px] flex-1 space-y-4 overflow-auto px-1">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">
            Lab · Optimizar
          </h3>
          <p className="text-sm text-muted-foreground">
            Mismo Lab del embudo Coach → Finalistas. Busca Mejor ≥ ancla (OOS);
            no escribe Finalistas.
          </p>
        </div>
        {!optimizeSeed && !(labZones ?? []).some((z) => z.seed) && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              setTab("run");
              setResultFocus("coach");
            }}
          >
            Ir al Coach
          </Button>
        )}
      </div>
      {!optimizeSeed && !(labZones ?? []).some((z) => z.seed) && (
        <div className="rounded-lg border border-dashed border-border bg-muted/10 px-4 py-3 text-sm">
          <p className="font-medium text-foreground">Sin semilla cargada</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Desde Probar → Coach: «Pasar al Lab» o «Abrir Lab · #1». También
            puedes elegir instrumento abajo y lanzar a mano.
          </p>
        </div>
      )}
      {optimizeCompare && (
        <BacktestOptimizeCompareCard
          snapshot={optimizeCompare}
          onDismiss={() => setOptimizeCompare(null)}
          onBackToCoach={() => {
            setTab("run");
            setResultFocus("coach");
          }}
        />
      )}
      <BacktestOptimizePanel
        instruments={instrumentsQuery.data?.data ?? []}
        defaultInstrumentId={instrumentId}
        seed={optimizeSeed}
        maxDrawdownSoftPct={coachProfilePolicy.maxDrawdownSoftPct}
        profileId={coachProfilePolicy.profileId}
        profileHorizon={coachProfilePolicy.horizon}
        profileRiskTolerance={coachProfilePolicy.riskTolerance}
        onClearSeed={() => setOptimizeSeed(null)}
        onOptimizeComplete={({ seed: doneSeed, result }) => {
          const snap = buildOptimizeBeforeAfter(doneSeed, result);
          if (snap) setOptimizeCompare(snap);
        }}
        onAdoptedStrategy={({
          strategyId,
          instrumentId: nextInstrumentId,
          initialCash: cash,
          timeframe,
          barLimit,
          labEvidence,
        }) => {
          setSavedStrategyId(strategyId);
          setRunSource("saved");
          setInstrumentId(nextInstrumentId);
          setInitialCash(String(cash));
          setRunTimeframe(timeframe);
          setPeriodPreset("all");
          setUniverseMode("single");
          setTab("run");
          setResultFocus("detail");
          // Full lab window so indicators warm up. Lab provenance → trial.blocks (P9).
          runMutation.mutate({
            strategyDefinitionId: strategyId,
            instrumentId: nextInstrumentId,
            initialCash: cash,
            timeframe,
            limit: barLimit && barLimit > 0 ? barLimit : 10_000,
            labEvidence: labEvidence ?? null,
          });
        }}
      />
    </div>
  );
}
