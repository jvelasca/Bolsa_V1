/**
 * Helpers de navegación extraídos de `BacktestsPage` — URL, tab, run, instrumento.
 *
 * Extraído de `backtests-page.tsx` (Track B B6) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 *
 * Recibe TODO el estado/setter/ref que cierran las 6 funciones a través de
 * `BacktestPageNavigationCtx` (factory `createBacktestPageNavigation`).
 * Recrear las funciones cada llamada (cada render). NO memoizar: el original
 * no estaba memoizado; useCallback/useMemo stale-cerrarían instrumentId /
 * fullCycleActive / pathname.
 */

import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { SetURLSearchParams } from "react-router-dom";
import type {
  HubTab,
  ResultFocus,
  StrategiesListFilter,
  UniverseMode,
} from "@/features/backtests/backtests-page.constants";
import {
  emptyAssistantProgress,
  type AssistantSessionProgress,
} from "@/features/backtests/backtest-assistant-completion";
import type { AssistantStepId } from "@/features/backtests/backtest-assistant-steps";
import type { BatchRankRow } from "@/features/backtests/backtest-batch-run";
import type { ExplorePresetRow } from "@/features/backtests/backtest-explore-value";
import type { LabBoardZone } from "@/features/backtests/backtest-lab-board-types";
import type { ListAutoCampaign } from "@/features/backtests/backtest-list-auto";
import type { OptimizeBeforeAfterSnapshot } from "@/features/backtests/backtest-optimize-delta";
import type { OptimizeSeed } from "@/features/backtests/backtest-optimize-seed";
import type { MineStrategiesFilterState } from "@/features/backtests/mine-strategies-filters";

/**
 * Todo lo que las 6 funciones extraídas leen/escriben.
 * Los `MutableRefObject` y `Dispatch<SetStateAction<...>>` se pasan intactos
 * desde el componente (mismas referencias estables). Los valores (`pathname`,
 * `instrumentId`, `fullCycleActive`) se re-pasan en cada render.
 */
export interface BacktestPageNavigationCtx {
  pathname: string;
  setSearchParams: SetURLSearchParams;

  setStrategiesListFilter: Dispatch<SetStateAction<StrategiesListFilter>>;
  setLibraryFocusStrategyId: Dispatch<SetStateAction<string | null>>;
  setLibraryFocusPreset: Dispatch<SetStateAction<string | null>>;
  setMineFilters: Dispatch<SetStateAction<MineStrategiesFilterState>>;

  setSelectedId: Dispatch<SetStateAction<string | null>>;
  setPreferOpenAnalysis: Dispatch<SetStateAction<boolean>>;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;

  instrumentId: string;
  exploreAbortRef: MutableRefObject<AbortController | null>;
  setExploreRunning: Dispatch<SetStateAction<boolean>>;
  setExploreRows: Dispatch<SetStateAction<ExplorePresetRow[]>>;
  setExploreProgress: Dispatch<SetStateAction<{ done: number; total: number }>>;
  setExploreError: Dispatch<SetStateAction<string | null>>;
  setBatchRows: Dispatch<SetStateAction<BatchRankRow[]>>;
  setBatchError: Dispatch<SetStateAction<string | null>>;
  setFocusTimestamp: Dispatch<SetStateAction<string | null>>;
  setOptimizeSeed: Dispatch<SetStateAction<OptimizeSeed | null>>;
  setLabZones: Dispatch<SetStateAction<LabBoardZone[] | null>>;
  setCoachPass: Dispatch<SetStateAction<"initial" | "post_lab">>;
  setOptimizeCompare: Dispatch<
    SetStateAction<OptimizeBeforeAfterSnapshot | null>
  >;
  lastBatteryFingerprintRef: MutableRefObject<string | null>;
  setAssistantProgress: Dispatch<SetStateAction<AssistantSessionProgress>>;
  setAwaitingAck: Dispatch<SetStateAction<boolean>>;
  setAwaitingAckStage: Dispatch<SetStateAction<"coach1" | "revalidate" | null>>;
  setLabImprovedThisCycle: Dispatch<SetStateAction<number>>;
  setSemifinalShortcutArmed: Dispatch<SetStateAction<boolean>>;
  setLabOpenedThisRun: Dispatch<SetStateAction<boolean>>;
  assistantChainRef: MutableRefObject<string>;
  setAssistantFocus: Dispatch<SetStateAction<AssistantStepId | null>>;
  fullCycleActive: boolean;
  listAutoRef: MutableRefObject<ListAutoCampaign | null>;
  setFullCycleActive: Dispatch<SetStateAction<boolean>>;
  setAssistantStatus: Dispatch<SetStateAction<string | null>>;
  setInstrumentId: Dispatch<SetStateAction<string>>;

  setUniverseMode: Dispatch<SetStateAction<UniverseMode>>;
}

export function createBacktestPageNavigation(ctx: BacktestPageNavigationCtx) {
  const {
    pathname,
    setSearchParams,
    setStrategiesListFilter,
    setLibraryFocusStrategyId,
    setLibraryFocusPreset,
    setMineFilters,
    setSelectedId,
    setPreferOpenAnalysis,
    setResultFocus,
    instrumentId,
    exploreAbortRef,
    setExploreRunning,
    setExploreRows,
    setExploreProgress,
    setExploreError,
    setBatchRows,
    setBatchError,
    setFocusTimestamp,
    setOptimizeSeed,
    setLabZones,
    setCoachPass,
    setOptimizeCompare,
    lastBatteryFingerprintRef,
    setAssistantProgress,
    setAwaitingAck,
    setAwaitingAckStage,
    setLabImprovedThisCycle,
    setSemifinalShortcutArmed,
    setLabOpenedThisRun,
    assistantChainRef,
    setAssistantFocus,
    fullCycleActive,
    listAutoRef,
    setFullCycleActive,
    setAssistantStatus,
    setInstrumentId,
    setUniverseMode,
  } = ctx;

  function patchSearchParams(
    mutate: (params: URLSearchParams) => void,
    opts?: { replace?: boolean },
  ) {
    // Keep-alive fuera de /backtests: no pisar la URL de Trading/otros hubs.
    if (!pathname.startsWith("/backtests")) return;
    // Updater funcional: evita carrera entre setTab + selectInstrument (mismo
    // searchParams stale → instrumentId se queda en el valor anterior, p.ej. AENA).
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        mutate(next);
        return next;
      },
      { replace: opts?.replace },
    );
  }

  /** Abre Biblioteca con filtro / foco (entra en historial ←→). */
  function openLibrary(opts?: {
    library?: StrategiesListFilter;
    strategyId?: string | null;
    preset?: string | null;
    q?: string | null;
  }) {
    const library = opts?.library ?? "mine";
    setStrategiesListFilter(library);
    setLibraryFocusStrategyId(opts?.strategyId ?? null);
    setLibraryFocusPreset(opts?.preset ?? null);
    if (opts?.q != null) {
      setMineFilters((prev) => ({ ...prev, query: opts.q ?? "" }));
    }
    patchSearchParams((params) => {
      params.set("tab", "strategies");
      params.set("library", library);
      if (opts?.strategyId) params.set("strategyId", opts.strategyId);
      else params.delete("strategyId");
      if (opts?.preset) params.set("preset", opts.preset);
      else params.delete("preset");
      if (opts?.q?.trim()) params.set("q", opts.q.trim());
      else if (opts?.q === "") params.delete("q");
    });
  }

  function setTab(next: HubTab) {
    patchSearchParams((params) => {
      params.set("tab", next);
    });
  }

  function selectRun(
    id: string,
    options?: { tab?: HubTab; openAnalysis?: boolean; focus?: ResultFocus },
  ) {
    setSelectedId(id);
    if (options?.openAnalysis) setPreferOpenAnalysis(true);
    else setPreferOpenAnalysis(false);
    if (options?.focus) setResultFocus(options.focus);
    patchSearchParams((params) => {
      params.set("runId", id);
      params.set("tab", options?.tab ?? "run");
      if (options?.focus) params.set("focus", options.focus);
      if (options?.openAnalysis) params.set("openAnalysis", "1");
      else params.delete("openAnalysis");
      // Ver / checklist = Análisis técnico normal (no Verificar D→hoy).
      params.delete("verify");
    });
  }

  // Al elegir un valor: Detalle con vista previa (gráfico + B&H).
  function selectInstrument(
    id: string,
    opts?: {
      forceClear?: boolean;
      preserveListAutoFocus?: boolean;
      skipUrl?: boolean;
    },
  ) {
    const changed = opts?.forceClear || id !== instrumentId;
    // Siempre limpiar el run seleccionado al cambiar (evita carrera con ?runId= en la URL).
    if (changed) {
      // En Lista AUTO no abortamos aquí si vamos a omitir: el arranque explícito
      // gestiona el ciclo. Abort sí al cambiar de valor a mano.
      if (!opts?.preserveListAutoFocus) {
        exploreAbortRef.current?.abort();
      }
      setExploreRunning(false);
      setExploreRows([]);
      setExploreProgress({ done: 0, total: 0 });
      setExploreError(null);
      setBatchRows([]);
      setBatchError(null);
      setFocusTimestamp(null);
      setOptimizeSeed(null);
      setLabZones(null);
      setCoachPass("initial");
      setOptimizeCompare(null);
      lastBatteryFingerprintRef.current = null;
      setAssistantProgress(emptyAssistantProgress());
      setAwaitingAck(false);
      setAwaitingAckStage(null);
      setLabImprovedThisCycle(0);
      setSemifinalShortcutArmed(false);
      setLabOpenedThisRun(false);
      assistantChainRef.current = "";
      setAssistantFocus(null);
      if (fullCycleActive && !listAutoRef.current) {
        setFullCycleActive(false);
        setAssistantStatus(
          "Instrumento cambiado · ciclo reiniciado. Pulsa Play.",
        );
      }
    }
    setSelectedId(null);
    setInstrumentId(id);
    if (!opts?.preserveListAutoFocus) {
      setResultFocus("detail");
    }
    // Un solo patch URL: setTab + patch en paralelo pisaban instrumentId (stale).
    if (!opts?.skipUrl) {
      patchSearchParams((params) => {
        if (id) params.set("instrumentId", id);
        else params.delete("instrumentId");
        params.delete("runId");
        params.set("tab", "run");
        if (!opts?.preserveListAutoFocus) {
          params.set("focus", "detail");
        }
      });
    } else {
      setTab("run");
    }
  }

  /** Desde lista / tablero AUTO / ranking → pestaña Universo Valor + Detalle. */
  function openInstrumentInValor(
    id: string,
    opts?: { runId?: string | null; soft?: boolean },
  ) {
    if (!id) return;
    const campaignLive = Boolean(
      listAutoRef.current && !listAutoRef.current.aborted,
    );
    const soft = Boolean(opts?.soft) || campaignLive;
    setUniverseMode("single");
    if (soft) {
      // No tumba ranking / campaña AUTO: solo cambia el valor activo.
      setInstrumentId(id);
      setSelectedId(opts?.runId ?? null);
      setResultFocus("detail");
      setTab("run");
    } else {
      selectInstrument(id, { skipUrl: true });
      if (opts?.runId) setSelectedId(opts.runId);
      setResultFocus("detail");
    }
    patchSearchParams((params) => {
      params.set("instrumentId", id);
      params.set("focus", "detail");
      params.set("tab", "run");
      if (opts?.runId) params.set("runId", opts.runId);
      else params.delete("runId");
    });
  }

  return {
    patchSearchParams,
    openLibrary,
    setTab,
    selectRun,
    selectInstrument,
    openInstrumentInValor,
  };
}
