/**
 * Controlador Asistente extraído de `BacktestsPage` — Play, Universo→Lab, ciclo.
 *
 * Extraído de `backtests-page.tsx` (Track B B8) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 *
 * Mezcla factory (funciones, como B6) y hook de efectos (como B5/B7).
 * Recrear las funciones cada llamada (cada render). NO memoizar: el original
 * no estaba memoizado; useCallback/useMemo stale-cerrarían instrumentId /
 * campaign / pathname.
 */

import {
  useEffect,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";
import type {
  ChartTimeframe,
  InstrumentStrategyTopV1,
  InstrumentWithMetaDto,
  InvestorProfileV1,
} from "@bolsa/shared";
import {
  canAutoRunStep,
  emptyAssistantProgress,
  withUniverseDone,
  type AssistantSessionProgress,
} from "@/features/backtests/backtest-assistant-completion";
import {
  saveAssistantPrefs,
  type AssistantPrefs,
} from "@/features/backtests/backtest-assistant-prefs";
import {
  ASSISTANT_STEPS,
  type AssistantStepId,
} from "@/features/backtests/backtest-assistant-steps";
import { universeEmptyStatus } from "@/features/backtests/backtest-assistant-full-cycle";
import { rankTechnicalRecommendations } from "@/features/backtests/backtest-deep-coach";
import type { BatchRankRow } from "@/features/backtests/backtest-batch-run";
import type { ExplorePresetRow } from "@/features/backtests/backtest-explore-value";
import type { LabBoardZone } from "@/features/backtests/backtest-lab-board-types";
import type { ListAutoBoardState } from "@/features/backtests/backtest-list-auto-board";
import type { FullCycleSettleReason } from "@/features/backtests/backtest-list-auto";
import type { OptimizeBeforeAfterSnapshot } from "@/features/backtests/backtest-optimize-delta";
import type { OptimizeSeed } from "@/features/backtests/backtest-optimize-seed";
import {
  effectiveDiaD,
  isDiaDInPast,
} from "@/features/backtests/backtest-period";
import {
  exploreBatteryRowIds,
  type StrategyMatrixFilter,
} from "@/features/backtests/backtest-strategy-matrix";
import { patchStrategyMatrixTablePrefs } from "@/features/backtests/backtest-zone-prefs";
import type {
  HubTab,
  ResultFocus,
  StrategiesListFilter,
} from "@/features/backtests/backtests-page.constants";
import { buildAuditedDeepTechnicalCoachNote } from "@/features/backtests/coach-dual-audit";
import {
  resolveCoachProfilePolicy,
  shouldAdvanceToLab,
} from "@/features/backtests/coach-profile-policy";
import {
  isCoach1AckSatisfied,
  resolveCoach1AdvanceAction,
  shouldReenterUniverseToLabChain,
} from "@/features/backtests/assistant-cycle-orchestrator";
import { formatDiaDDisplay } from "@/features/backtests/dia-d-favorites";
import type { ListAutoUiState } from "@/features/backtests/lib/backtest-list-auto-controller";

export type BacktestAssistantControllerCtx = {
  assistantStepComplete: Partial<Record<AssistantStepId, boolean>>;
  assistantPrefs: AssistantPrefs;
  fullCycleActive: boolean;
  instrumentId: string;
  diaD: string;
  runTimeframe: ChartTimeframe;
  exploreRows: ExplorePresetRow[];
  instrumentLabels: Record<string, { symbol: string; name: string }>;
  instruments: InstrumentWithMetaDto[];
  detail: object | null | undefined;
  selectedId: string | null;
  coachPass: "initial" | "post_lab";

  assistantProgressRef: MutableRefObject<AssistantSessionProgress>;
  assistantChainRef: MutableRefObject<string>;
  listAutoFreshnessMemoryRef: MutableRefObject<Map<string, string>>;
  exploreAbortRef: MutableRefObject<AbortController | null>;
  batchAbortRef: MutableRefObject<AbortController | null>;

  setTab: (next: HubTab) => void;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  setLabOpenedThisRun: Dispatch<SetStateAction<boolean>>;
  setStrategiesListFilter: Dispatch<SetStateAction<StrategiesListFilter>>;
  setFullCycleActive: Dispatch<SetStateAction<boolean>>;
  setAssistantStatus: Dispatch<SetStateAction<string | null>>;
  setDiaD: Dispatch<SetStateAction<string>>;
  setExploreRunning: Dispatch<SetStateAction<boolean>>;
  setExploreRows: Dispatch<SetStateAction<ExplorePresetRow[]>>;
  setExploreProgress: Dispatch<SetStateAction<{ done: number; total: number }>>;
  setExploreError: Dispatch<SetStateAction<string | null>>;
  setBatchRows: Dispatch<SetStateAction<BatchRankRow[]>>;
  setSemifinalJobsQueued: Dispatch<SetStateAction<boolean>>;
  setSemifinalEnqueuePending: Dispatch<SetStateAction<boolean>>;
  setOptimizeSeed: Dispatch<SetStateAction<OptimizeSeed | null>>;
  setLabZones: Dispatch<SetStateAction<LabBoardZone[] | null>>;
  setCoachPass: Dispatch<SetStateAction<"initial" | "post_lab">>;
  setOptimizeCompare: Dispatch<
    SetStateAction<OptimizeBeforeAfterSnapshot | null>
  >;
  setAssistantProgress: Dispatch<SetStateAction<AssistantSessionProgress>>;
  setAwaitingAck: Dispatch<SetStateAction<boolean>>;
  setAwaitingAckStage: Dispatch<SetStateAction<"coach1" | "revalidate" | null>>;
  setLabImprovedThisCycle: Dispatch<SetStateAction<number>>;
  setSemifinalShortcutArmed: Dispatch<SetStateAction<boolean>>;
  setAssistantFocus: Dispatch<SetStateAction<AssistantStepId | null>>;
  setListAutoBoard: Dispatch<SetStateAction<ListAutoBoardState | null>>;
  setAssistantPrefs: Dispatch<SetStateAction<AssistantPrefs>>;
  setMatrixFilter: Dispatch<SetStateAction<StrategyMatrixFilter>>;
  setMatrixSelectedIds: Dispatch<SetStateAction<Set<string>>>;

  startListAutoCampaign: () => Promise<boolean>;
  abortListAutoCampaign: (opts?: { keepContinue?: boolean }) => void;
  settleFullCycle: (
    reason: FullCycleSettleReason,
    statusMessage?: string,
  ) => void;
  runExploreValue: () => Promise<{ okCount: number; error?: string }>;
  optimizeSemifinalFromCoach: (
    candidates: Array<{
      row: ExplorePresetRow;
      stars?: number;
      starsCapped?: boolean;
      rank?: number;
    }>,
  ) => Promise<"opened" | "skipped">;
};

export type BacktestAssistantController = {
  playAssistantSequence: () => Promise<void>;
  handleDiaDChange: (next: string) => void;
  updateAssistantPrefs: (next: AssistantPrefs) => void;
  executeAssistantStep: (
    step: AssistantStepId,
    opts?: { fullCycle?: boolean; progress?: AssistantSessionProgress },
  ) => void | Promise<void>;
  goAssistantStep: (step: AssistantStepId) => void;
};

export function createBacktestAssistantController(
  ctx: BacktestAssistantControllerCtx,
): BacktestAssistantController {
  const {
    assistantStepComplete,
    assistantPrefs,
    fullCycleActive,
    instrumentId,
    diaD,
    runTimeframe,
    exploreRows,
    instrumentLabels,
    instruments,
    detail,
    selectedId,
    coachPass,
    assistantProgressRef,
    assistantChainRef,
    listAutoFreshnessMemoryRef,
    exploreAbortRef,
    batchAbortRef,
    setTab,
    setResultFocus,
    setLabOpenedThisRun,
    setStrategiesListFilter,
    setFullCycleActive,
    setAssistantStatus,
    setDiaD,
    setExploreRunning,
    setExploreRows,
    setExploreProgress,
    setExploreError,
    setBatchRows,
    setSemifinalJobsQueued,
    setSemifinalEnqueuePending,
    setOptimizeSeed,
    setLabZones,
    setCoachPass,
    setOptimizeCompare,
    setAssistantProgress,
    setAwaitingAck,
    setAwaitingAckStage,
    setLabImprovedThisCycle,
    setSemifinalShortcutArmed,
    setAssistantFocus,
    setListAutoBoard,
    setAssistantPrefs,
    setMatrixFilter,
    setMatrixSelectedIds,
    startListAutoCampaign,
    abortListAutoCampaign,
    settleFullCycle,
    runExploreValue,
    optimizeSemifinalFromCoach,
  } = ctx;

  function goAssistantStep(step: AssistantStepId) {
    setTab("run");
    if (step === "universe") {
      setResultFocus(
        detail || selectedId
          ? "detail"
          : exploreRows.length > 0
            ? "coach"
            : "detail",
      );
      return;
    }
    if (step === "semifinal") {
      setResultFocus("coach");
      return;
    }
    if (step === "lab") {
      setLabOpenedThisRun(true);
      setResultFocus("lab");
      return;
    }
    setStrategiesListFilter("finalists");
    setResultFocus("finalists");
  }

  /** Play: paso a paso, ciclo 1 valor, o lista AUTO (lista + ciclo completo). */
  async function playAssistantSequence() {
    if (await startListAutoCampaign()) return;
    const next = ASSISTANT_STEPS.find((s) => !assistantStepComplete[s.id]);
    if (!next) {
      setFullCycleActive(false);
      setAssistantStatus(
        "Asistente completo. Revisa Análisis técnico / fundamental / Coach / Lab / Finalistas.",
      );
      return;
    }
    const cycle = assistantPrefs.fullCycleOnPlay;
    setFullCycleActive(cycle);
    if (cycle) {
      setAssistantStatus(`Ciclo completo: empezando en ${next.label}…`);
    }
    void executeAssistantStep(next.id, { fullCycle: cycle });
  }

  /** Al pasar a DÍA D (fecha pasada): reinicia el asistente / ciclo en curso. */
  function handleDiaDChange(next: string) {
    const enteringDiaD =
      isDiaDInPast(next) &&
      (!isDiaDInPast(diaD) || effectiveDiaD(next) !== effectiveDiaD(diaD));
    setDiaD(next);
    if (!enteringDiaD) return;
    abortListAutoCampaign();
    exploreAbortRef.current?.abort();
    batchAbortRef.current?.abort();
    setExploreRunning(false);
    setExploreRows([]);
    setExploreProgress({ done: 0, total: 0 });
    setExploreError(null);
    setBatchRows([]);
    setSemifinalJobsQueued(false);
    setSemifinalEnqueuePending(false);
    setOptimizeSeed(null);
    setLabZones(null);
    setCoachPass("initial");
    setOptimizeCompare(null);
    setAssistantProgress(emptyAssistantProgress());
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    setAssistantFocus(null);
    setLabOpenedThisRun(false);
    setFullCycleActive(false);
    assistantChainRef.current = "";
    listAutoFreshnessMemoryRef.current = new Map();
    setListAutoBoard(null);
    setResultFocus("detail");
    setAssistantStatus(
      `DÍA D ${formatDiaDDisplay(effectiveDiaD(next))} · asistente reiniciado. Pulsa Play.`,
    );
  }

  function updateAssistantPrefs(next: AssistantPrefs) {
    setAssistantPrefs(next);
    saveAssistantPrefs(next);
  }

  async function runSemifinalOptimizeFromRows(): Promise<"opened" | "skipped"> {
    const symbol =
      instrumentLabels[instrumentId]?.symbol ??
      instruments.find((i) => i.id === instrumentId)?.symbol ??
      "Valor";
    const ranked = rankTechnicalRecommendations(exploreRows, {
      symbol,
      timeframe: runTimeframe,
    });
    return optimizeSemifinalFromCoach(
      ranked.slice(0, 3).map((r) => ({
        row: r.row,
        stars: r.stars,
        starsCapped: r.starsCapped,
        rank: r.rank,
      })),
    );
  }

  async function executeAssistantStep(
    step: AssistantStepId,
    opts?: { fullCycle?: boolean; progress?: AssistantSessionProgress },
  ) {
    const cycle = opts?.fullCycle ?? fullCycleActive;
    const progress = opts?.progress ?? assistantProgressRef.current;
    if (!canAutoRunStep(step, progress, Boolean(instrumentId))) {
      setAssistantStatus(
        step === "universe"
          ? "Elige un valor para Universo."
          : "Completa el paso anterior (✓) o pulsa Play.",
      );
      goAssistantStep(step);
      return;
    }

    setAssistantFocus(step);
    goAssistantStep(step);

    if (step === "universe") {
      if (assistantPrefs.universe.selectAllGenerics) {
        setMatrixFilter("preset");
        patchStrategyMatrixTablePrefs({ filter: "preset" });
        setMatrixSelectedIds(new Set(exploreBatteryRowIds()));
      }
      if (!assistantPrefs.universe.runCoachOnEnter) {
        setAssistantStatus(
          "Universo: marca Probar + coach en prefs o lanza a mano.",
        );
        if (cycle) {
          settleFullCycle(
            "skip_lab",
            universeEmptyStatus("prefs sin Probar + coach"),
          );
        }
        return;
      }
      setAssistantStatus(
        cycle
          ? "Ciclo: Universo · Probar + coach…"
          : "Universo: Probar + coach…",
      );
      const battery = await runExploreValue();
      // El efecto Universo→Lab encadena si hay OK; si 0 OK, cerrar ciclo (evita hang en RED etc.).
      if (cycle && battery.okCount === 0) {
        settleFullCycle(
          "skip_lab",
          universeEmptyStatus(battery.error ?? "0 OK"),
        );
      }
      return;
    }

    if (step === "semifinal") {
      const doOptimize = assistantPrefs.semifinal.optimizeTop3OnEnter || cycle;
      let labOutcome: "opened" | "skipped" | "idle" = "idle";
      if (doOptimize) {
        setAssistantStatus(
          cycle ? "Ciclo: Coach → Lab TOP-3…" : "Coach: Optimizar TOP-3…",
        );
        labOutcome = await runSemifinalOptimizeFromRows();
      } else {
        setAssistantStatus("Coach listo.");
      }
      if (labOutcome === "skipped") {
        // settleFullCycle ya avanzó Lista AUTO; no dejar «Lab en curso».
        setAssistantFocus(null);
        return;
      }
      setAssistantProgress((p) => {
        const next = {
          ...p,
          universeDone: true,
          semifinalDone: true,
        };
        assistantProgressRef.current = next;
        return next;
      });
      setAssistantFocus(null);
      if (cycle) {
        setLabOpenedThisRun(true);
        setResultFocus("lab");
        setAssistantStatus(
          "Ciclo: Lab en curso. Al terminar con mejora → Coach² → Finalistas.",
        );
      } else {
        setAssistantStatus("Coach ✓. Pulsa Play para Lab.");
      }
      return;
    }

    if (step === "lab") {
      setLabOpenedThisRun(true);
      setAssistantFocus(null);
      setAssistantStatus(
        cycle
          ? "Ciclo: Lab abierto. Espera resultados; handoff a Coach² automático si hay mejora."
          : "Lab: adopta Mejor ≥ ancla (OOS). Luego Play → Finalistas.",
      );
      return;
    }

    if (step === "finalists") {
      setStrategiesListFilter("finalists");
      setAssistantFocus(null);
      if (cycle && coachPass === "post_lab") {
        setAssistantStatus(
          "Ciclo: revisando Finalistas (auto-guardado si procede)…",
        );
        setResultFocus("coach");
        return;
      }
      setAssistantProgress((p) => ({ ...p, finalistsDone: true }));
      setFullCycleActive(false);
      if (assistantPrefs.finalists.revalidateCoachOnEnter) {
        setAssistantStatus("Finalistas: Revalidar + coach…");
        await runExploreValue();
      } else {
        setAssistantStatus("Finalistas ✓ · TOP del valor.");
      }
    }
  }

  return {
    playAssistantSequence,
    handleDiaDChange,
    updateAssistantPrefs,
    executeAssistantStep,
    goAssistantStep,
  };
}

export type UseBacktestAssistantEffectsParams = {
  exploreRunning: boolean;
  exploreOkCount: number;
  assistantProgress: AssistantSessionProgress;
  exploreRows: ExplorePresetRow[];
  fullCycleActive: boolean;
  accountProfileQuery: { data?: { data?: InvestorProfileV1 } };
  coachGate: { ack: boolean };
  assistantPrefs: AssistantPrefs;
  instrumentLabels: Record<string, { symbol: string; name: string }>;
  instrumentId: string;
  instruments: InstrumentWithMetaDto[];
  runTimeframe: ChartTimeframe;
  playContextKey: string;
  listAutoUi: ListAutoUiState | null;
  listAutoBoard: ListAutoBoardState | null;
  labOpenedThisRun: boolean;
  instrumentTop: InstrumentStrategyTopV1 | null | undefined;

  assistantChainRef: MutableRefObject<string>;
  assistantProgressRef: MutableRefObject<AssistantSessionProgress>;
  coach1AdvancePendingRef: MutableRefObject<boolean>;
  playContextKeyRef: MutableRefObject<string | null>;
  exploreAbortRef: MutableRefObject<AbortController | null>;
  listAutoFreshnessMemoryRef: MutableRefObject<Map<string, string>>;

  setAssistantProgress: Dispatch<SetStateAction<AssistantSessionProgress>>;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  setAssistantFocus: Dispatch<SetStateAction<AssistantStepId | null>>;
  setAssistantStatus: Dispatch<SetStateAction<string | null>>;
  setAwaitingAck: Dispatch<SetStateAction<boolean>>;
  setAwaitingAckStage: Dispatch<SetStateAction<"coach1" | "revalidate" | null>>;
  setSemifinalShortcutArmed: Dispatch<SetStateAction<boolean>>;
  setLabImprovedThisCycle: Dispatch<SetStateAction<number>>;
  setExploreRunning: Dispatch<SetStateAction<boolean>>;
  setExploreRows: Dispatch<SetStateAction<ExplorePresetRow[]>>;
  setExploreProgress: Dispatch<SetStateAction<{ done: number; total: number }>>;
  setExploreError: Dispatch<SetStateAction<string | null>>;
  setBatchRows: Dispatch<SetStateAction<BatchRankRow[]>>;
  setSemifinalJobsQueued: Dispatch<SetStateAction<boolean>>;
  setSemifinalEnqueuePending: Dispatch<SetStateAction<boolean>>;
  setOptimizeSeed: Dispatch<SetStateAction<OptimizeSeed | null>>;
  setLabZones: Dispatch<SetStateAction<LabBoardZone[] | null>>;
  setCoachPass: Dispatch<SetStateAction<"initial" | "post_lab">>;
  setOptimizeCompare: Dispatch<
    SetStateAction<OptimizeBeforeAfterSnapshot | null>
  >;
  setLabOpenedThisRun: Dispatch<SetStateAction<boolean>>;
  setFullCycleActive: Dispatch<SetStateAction<boolean>>;
  setListAutoBoard: Dispatch<SetStateAction<ListAutoBoardState | null>>;

  abortListAutoCampaign: (opts?: { keepContinue?: boolean }) => void;
  settleFullCycle: (
    reason: FullCycleSettleReason,
    statusMessage?: string,
  ) => void;
  executeAssistantStep: (
    step: AssistantStepId,
    opts?: { fullCycle?: boolean; progress?: AssistantSessionProgress },
  ) => void | Promise<void>;
};

export function useBacktestAssistantEffects(
  params: UseBacktestAssistantEffectsParams,
): void {
  const {
    exploreRunning,
    exploreOkCount,
    assistantProgress,
    exploreRows,
    fullCycleActive,
    accountProfileQuery,
    coachGate,
    assistantPrefs,
    instrumentLabels,
    instrumentId,
    instruments,
    runTimeframe,
    playContextKey,
    listAutoUi,
    listAutoBoard,
    labOpenedThisRun,
    instrumentTop,
    assistantChainRef,
    assistantProgressRef,
    coach1AdvancePendingRef,
    playContextKeyRef,
    exploreAbortRef,
    listAutoFreshnessMemoryRef,
    setAssistantProgress,
    setResultFocus,
    setAssistantFocus,
    setAssistantStatus,
    setAwaitingAck,
    setAwaitingAckStage,
    setSemifinalShortcutArmed,
    setLabImprovedThisCycle,
    setExploreRunning,
    setExploreRows,
    setExploreProgress,
    setExploreError,
    setBatchRows,
    setSemifinalJobsQueued,
    setSemifinalEnqueuePending,
    setOptimizeSeed,
    setLabZones,
    setCoachPass,
    setOptimizeCompare,
    setLabOpenedThisRun,
    setFullCycleActive,
    setListAutoBoard,
    abortListAutoCampaign,
    settleFullCycle,
    executeAssistantStep,
  } = params;

  // Universo terminado → Coach¹; en ciclo: gate perfil → Lab o skip_lab
  useEffect(() => {
    if (exploreRunning) return;
    if (exploreOkCount === 0) return;
    if (assistantProgress.semifinalDone) return;

    const fp = `u2s:${exploreRows
      .filter((r) => r.status === "ok")
      .map((r) => r.runId ?? r.strategyType)
      .join(",")}`;
    const fingerprintMatches = assistantChainRef.current === fp;
    const canReenter = shouldReenterUniverseToLabChain({
      fingerprintMatches,
      pendingAck1: coach1AdvancePendingRef.current,
      ackSatisfied: isCoach1AckSatisfied({
        needsAck: true,
        ackReady: coachGate.ack,
        autoAckOnCycle: assistantPrefs.coach.autoAckOnCycle,
        pauseIfAckNeeded: assistantPrefs.coach.pauseIfAckNeeded,
      }),
    });
    if (fingerprintMatches && !canReenter) return;
    if (!fingerprintMatches) {
      assistantChainRef.current = fp;
    }

    // Snapshot síncrono: el setState de React no está committed aún cuando
    // encadenamos semifinal; sin esto canAutoRunStep ve universeDone=false.
    const nextProgress = withUniverseDone(assistantProgressRef.current);
    assistantProgressRef.current = nextProgress;
    setAssistantProgress(nextProgress);
    setResultFocus("coach");
    setAssistantFocus(null);

    if (!fullCycleActive) {
      setAssistantStatus("Universo ✓. Pulsa Play para Coach.");
      return;
    }

    const profile = accountProfileQuery.data?.data ?? null;
    const policy = resolveCoachProfilePolicy({
      profileId: profile?.profileId,
      profileName: profile?.name,
      horizon: profile?.declared?.horizon ?? null,
      riskTolerance: profile?.declared?.riskTolerance ?? null,
    });
    const symbol =
      instrumentLabels[instrumentId]?.symbol ??
      instruments.find((i) => i.id === instrumentId)?.symbol ??
      "Valor";
    const audited = buildAuditedDeepTechnicalCoachNote(
      exploreRows,
      {
        symbol,
        timeframe: runTimeframe,
        horizon: policy.horizon,
        riskTolerance: policy.riskTolerance,
        profileName: policy.profileName,
        profileId: policy.profileId,
        maxDrawdownSoftPct: policy.maxDrawdownSoftPct,
        futureWeight: assistantPrefs.coach.futureWeight,
        evidenceLevel: "in_sample_only",
      },
      undefined,
      { coachPass: "initial" },
    );
    const gate = shouldAdvanceToLab({
      confidence: audited.audit?.confidence,
      policy,
      labEvenIfWeak: assistantPrefs.coach.labEvenIfWeak,
      recommendationCount: audited.recommendations.length,
    });

    const action = resolveCoach1AdvanceAction({
      gate,
      confidence: audited.audit?.confidence,
      requireAckBeforeLab: assistantPrefs.coach.requireAckBeforeLab,
      ackReady: coachGate.ack,
      autoAckOnCycle: assistantPrefs.coach.autoAckOnCycle,
      pauseIfAckNeeded: assistantPrefs.coach.pauseIfAckNeeded,
      saveSemifinalSkipLab: assistantPrefs.coach.saveSemifinalSkipLab,
    });

    if (action.type === "skip_lab") {
      coach1AdvancePendingRef.current = false;
      const skipped = { ...nextProgress, semifinalDone: true, labDone: true };
      assistantProgressRef.current = skipped;
      setAssistantProgress(skipped);
      settleFullCycle("skip_lab", `Ciclo: ${action.reason}`);
      return;
    }

    if (action.type === "wait_ack1") {
      coach1AdvancePendingRef.current = true;
      setAwaitingAck(true);
      setAwaitingAckStage("coach1");
      setAssistantStatus(
        `Ciclo: Universo ✓ · falta ACK¹ para Lab (${action.reason})`,
      );
      return;
    }

    if (action.type === "save_semifinal") {
      coach1AdvancePendingRef.current = false;
      setAwaitingAck(false);
      setAwaitingAckStage(null);
      setSemifinalShortcutArmed(true);
      setAssistantStatus(`Ciclo: ${action.reason}…`);
      setResultFocus("coach");
      return;
    }

    coach1AdvancePendingRef.current = false;
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    setAssistantStatus(`Ciclo: Universo ✓ → Lab (${action.reason})…`);
    void executeAssistantStep("semifinal", {
      fullCycle: true,
      progress: nextProgress,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    exploreRunning,
    exploreOkCount,
    fullCycleActive,
    accountProfileQuery.data?.data,
    coachGate.ack,
    assistantPrefs.coach.requireAckBeforeLab,
    assistantPrefs.coach.saveSemifinalSkipLab,
    assistantPrefs.coach.labEvenIfWeak,
    assistantPrefs.coach.autoAckOnCycle,
    assistantPrefs.coach.pauseIfAckNeeded,
  ]);

  // CORE-P: cambio de cuenta / perfil invalida Play o Lista AUTO en curso
  useEffect(() => {
    if (playContextKeyRef.current == null) {
      playContextKeyRef.current = playContextKey;
      return;
    }
    if (playContextKeyRef.current === playContextKey) return;
    playContextKeyRef.current = playContextKey;

    const midCycle =
      fullCycleActive ||
      Boolean(listAutoUi) ||
      Boolean(listAutoBoard && !listAutoBoard.done && !listAutoBoard.aborted);
    if (!midCycle) return;

    abortListAutoCampaign();
    exploreAbortRef.current?.abort();
    setExploreRunning(false);
    setExploreRows([]);
    setExploreProgress({ done: 0, total: 0 });
    setExploreError(null);
    setBatchRows([]);
    setSemifinalJobsQueued(false);
    setSemifinalEnqueuePending(false);
    setOptimizeSeed(null);
    setLabZones(null);
    setCoachPass("initial");
    setOptimizeCompare(null);
    setAssistantProgress(emptyAssistantProgress());
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    setAssistantFocus(null);
    setLabOpenedThisRun(false);
    setFullCycleActive(false);
    assistantChainRef.current = "";
    listAutoFreshnessMemoryRef.current = new Map();
    setListAutoBoard(null);
    setResultFocus("detail");
    setAssistantStatus(
      "Cuenta o perfil cambiado · ciclo reiniciado. Pulsa Play.",
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playContextKey, fullCycleActive, listAutoUi, listAutoBoard]);

  // Lab terminado (paso a paso): TOP active + Lab abierto en esta pasada
  useEffect(() => {
    if (fullCycleActive) return;
    if (!assistantProgress.semifinalDone) return;
    if (!labOpenedThisRun) return;
    if (assistantProgress.labDone) return;
    if (instrumentTop?.status !== "active") return;

    const fp = `l2f:${instrumentTop.id}:v${instrumentTop.version}`;
    if (assistantChainRef.current === fp) return;
    assistantChainRef.current = fp;

    setAssistantProgress((p) => ({ ...p, labDone: true }));
    setAssistantStatus("Lab ✓ (TOP active). Pulsa Play para Finalistas.");
  }, [
    fullCycleActive,
    assistantProgress.semifinalDone,
    assistantProgress.labDone,
    labOpenedThisRun,
    instrumentTop?.status,
    instrumentTop?.id,
    instrumentTop?.version,
  ]);
}
