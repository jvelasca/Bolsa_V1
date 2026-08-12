/**
 * Orquestación "god" extraída de `BacktestsPage` — 4 acciones de ciclo/embudo.
 *
 * CERO cambios de lógica: este módulo es una extracción pura (mover + tipar).
 * Recibe TODO el estado/setter/ref/helper que leen las 4 acciones a través de
 * `BacktestOrchestrationCtx` (factory `createBacktestOrchestration`).
 */

import type { QueryClient } from "@tanstack/react-query";
import type {
  BacktestStrategyType,
  ChartTimeframe,
  InstrumentListDetailDto,
  InstrumentStrategyTopV1,
  InstrumentWithMetaDto,
} from "@bolsa/shared";
import type {
  ResultFocus,
  RunSource,
} from "@/features/backtests/backtest-hub-nav";
import {
  runBacktestBatch,
  type BatchRankRow,
} from "@/features/backtests/backtest-batch-run";
import {
  matrixRowsToExploreRows,
  periodReturnsFromEquity,
  type ExplorePresetRow,
} from "@/features/backtests/backtest-explore-value";
import {
  buildCoachBatteryFingerprint,
  canReuseCoachLote,
} from "@/features/backtests/backtest-coach-lote";
import {
  runStrategyMatrixBattery,
  type StrategyMatrixFilter,
  type StrategyMatrixRow,
} from "@/features/backtests/backtest-strategy-matrix";
import {
  advanceListAutoAfterSettle,
  listAutoDoneStatus,
  listAutoPausedStatus,
  listAutoProgressLabel,
  type FullCycleSettleReason,
  type ListAutoCampaign,
} from "@/features/backtests/backtest-list-auto";
import {
  markListAutoBoardDone,
  markListAutoBoardPaused,
  markListAutoBoardSettled,
  listAutoTopFingerprint,
  resolveListAutoChange,
  type ListAutoBoardState,
} from "@/features/backtests/backtest-list-auto-board";
import {
  resolveBacktestWindow,
  type PeriodPreset,
} from "@/features/backtests/backtest-period";
import {
  readFinalistsFreshness,
  writeLocalFreshnessFingerprint,
} from "@/features/backtests/backtest-finalists-freshness";
import { readLabEvidenceFromCoachFacts } from "@/features/backtests/finalists-stability-summary";
import { readStashedOosEvidence } from "@/features/backtests/backtest-oos-evidence";
import {
  buildCoreRReportFromBoard,
  judgeCoreR,
  saveCoreRReport,
  type CoreRDualAuditSnap,
} from "@/features/backtests/core-r-judgment";
import { clearListAutoContinueSnapshot } from "@/features/backtests/backtest-list-auto-persist";
import type { CoachProfilePolicy } from "@/features/backtests/coach-profile-policy";
import type { AssistantSessionProgress } from "@/features/backtests/backtest-assistant-completion";
import type { AssistantPrefs } from "@/features/backtests/backtest-assistant-prefs";
import {
  buildOptimizeSeedFromExploreRow,
  type OptimizeSeed,
} from "@/features/backtests/backtest-optimize-seed";

import type { Dispatch, MutableRefObject, SetStateAction } from "react";

export type BacktestOrchestrationRef<T> = MutableRefObject<T>;

/**
 * Todo lo que los 4 bloques extraídos leen/escriben/llaman.
 * Los `MutableRefObject` y `Dispatch<SetStateAction<...>>` se pasan intactos
 * desde el componente (mismas referencias estables).
 */
export interface BacktestOrchestrationCtx {
  queryClient: QueryClient;

  instrumentId: string;
  runSource: RunSource;
  savedStrategyId: string;
  strategyType: BacktestStrategyType;
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  diaD: string;
  initialCash: string;
  commissionBps: string;
  slippageBps: string;
  runTimeframe: ChartTimeframe;
  matrixFilter: StrategyMatrixFilter;
  listDetail: InstrumentListDetailDto | undefined;
  instrumentLabels: Record<string, { symbol: string; name: string }>;
  instruments: InstrumentWithMetaDto[];
  matrixRowsForUi: StrategyMatrixRow[];
  matrixRunFingerprint: string;
  assistantPrefs: AssistantPrefs;
  instrumentTop: InstrumentStrategyTopV1 | null;
  listAutoBoard: ListAutoBoardState | null;
  coachProfilePolicy: CoachProfilePolicy;

  batchAbortRef: BacktestOrchestrationRef<AbortController | null>;
  exploreAbortRef: BacktestOrchestrationRef<AbortController | null>;
  lastBatteryFingerprintRef: BacktestOrchestrationRef<string | null>;
  listAutoRef: BacktestOrchestrationRef<ListAutoCampaign | null>;
  listAutoSettleLockRef: BacktestOrchestrationRef<number | null>;
  listAutoPendingStartRef: BacktestOrchestrationRef<number | null>;
  listAutoFreshnessMemoryRef: BacktestOrchestrationRef<Map<string, string>>;
  coach1AdvancePendingRef: BacktestOrchestrationRef<boolean>;
  assistantProgressRef: BacktestOrchestrationRef<AssistantSessionProgress>;

  setBatchError: Dispatch<SetStateAction<string | null>>;
  setExploreRows: Dispatch<SetStateAction<ExplorePresetRow[]>>;
  setBatchRunning: Dispatch<SetStateAction<boolean>>;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  setBatchProgress: Dispatch<SetStateAction<{ done: number; total: number }>>;
  setBatchRows: Dispatch<SetStateAction<BatchRankRow[]>>;
  setSelectedId: Dispatch<SetStateAction<string | null>>;
  setExploreError: Dispatch<SetStateAction<string | null>>;
  setCoachPass: Dispatch<SetStateAction<"initial" | "post_lab">>;
  setMatrixFilter: Dispatch<SetStateAction<StrategyMatrixFilter>>;
  setExploreRunning: Dispatch<SetStateAction<boolean>>;
  setExploreProgress: Dispatch<SetStateAction<{ done: number; total: number }>>;
  setMatrixRows: Dispatch<SetStateAction<StrategyMatrixRow[]>>;
  setAssistantStatus: Dispatch<SetStateAction<string | null>>;
  setListAutoUi: Dispatch<
    SetStateAction<{ index: number; total: number; symbol: string } | null>
  >;
  setListAutoBoard: Dispatch<SetStateAction<ListAutoBoardState | null>>;
  setFullCycleActive: Dispatch<SetStateAction<boolean>>;
  setAwaitingAck: Dispatch<SetStateAction<boolean>>;
  setAwaitingAckStage: Dispatch<SetStateAction<"coach1" | "revalidate" | null>>;
  setLabImprovedThisCycle: Dispatch<SetStateAction<number>>;
  setSemifinalShortcutArmed: Dispatch<SetStateAction<boolean>>;
  setAssistantProgress: Dispatch<SetStateAction<AssistantSessionProgress>>;

  seedBacktestDetail: (
    detail: import("@bolsa/shared").BacktestRunDetailDto,
  ) => void;
  patchSearchParams: (
    mutate: (params: URLSearchParams) => void,
    opts?: { replace?: boolean },
  ) => void;
  pruneAfterBatch: (okCount: number) => void;
  openGuidedOptimize: (
    seed: OptimizeSeed,
    extras?: {
      rank?: 1 | 2 | 3;
      stars?: number;
      starsCapped?: boolean;
      jobId?: string | null;
    },
  ) => void;
  queueListAutoTicker: (index: number) => void;
  symbolForInstrument: (id: string) => string;
  persistListAutoPauseNow: (
    campaign: ListAutoCampaign,
    board: ListAutoBoardState,
  ) => void;
  clearPersistedListAutoPause: () => void;
  currentFinalistsInputFingerprint: (forInstrumentId: string) => string;
  rememberListAutoFreshness: (
    forInstrumentId: string,
    fingerprint: string,
    opts?: { lab?: boolean },
  ) => Promise<void>;
  patchStrategyMatrixTablePrefs: (patch: {
    filter?: StrategyMatrixFilter;
  }) => void;
}

/** Period Returns rellenos desde detail cache (misma lógica que el componente original). */
function enrichExplorePeriodReturns(
  rows: ExplorePresetRow[],
  queryClient: QueryClient,
): ExplorePresetRow[] {
  return rows.map((row) => {
    if (!row.runId || row.periodReturns) return row;
    const cached = queryClient.getQueryData<{
      data?: {
        equityCurve?: import("@bolsa/shared").BacktestEquityPointDto[];
      };
    }>(["backtest", row.runId]);
    return {
      ...row,
      periodReturns: periodReturnsFromEquity(cached?.data?.equityCurve),
    };
  });
}

function exploreRowsFromMatrix(
  next: StrategyMatrixRow[],
  targetIds: ReadonlySet<string>,
  queryClient: QueryClient,
): ExplorePresetRow[] {
  return enrichExplorePeriodReturns(
    matrixRowsToExploreRows(next.filter((row) => targetIds.has(row.rowId))),
    queryClient,
  );
}

export function createBacktestOrchestration(ctx: BacktestOrchestrationCtx) {
  const {
    queryClient,
    instrumentId,
    runSource,
    savedStrategyId,
    strategyType,
    periodPreset,
    customDateFrom,
    customDateTo,
    diaD,
    initialCash,
    commissionBps,
    slippageBps,
    runTimeframe,
    matrixFilter,
    listDetail,
    instrumentLabels,
    instruments,
    matrixRowsForUi,
    matrixRunFingerprint,
    assistantPrefs,
    instrumentTop,
    listAutoBoard,
    coachProfilePolicy,
    batchAbortRef,
    exploreAbortRef,
    lastBatteryFingerprintRef,
    listAutoRef,
    listAutoSettleLockRef,
    listAutoPendingStartRef,
    listAutoFreshnessMemoryRef,
    coach1AdvancePendingRef,
    assistantProgressRef,
    setBatchError,
    setExploreRows,
    setBatchRunning,
    setResultFocus,
    setBatchProgress,
    setBatchRows,
    setSelectedId,
    setExploreError,
    setCoachPass,
    setMatrixFilter,
    setExploreRunning,
    setExploreProgress,
    setMatrixRows,
    setAssistantStatus,
    setListAutoUi,
    setListAutoBoard,
    setFullCycleActive,
    setAwaitingAck,
    setAwaitingAckStage,
    setLabImprovedThisCycle,
    setSemifinalShortcutArmed,
    setAssistantProgress,
    seedBacktestDetail,
    patchSearchParams,
    pruneAfterBatch,
    openGuidedOptimize,
    queueListAutoTicker,
    symbolForInstrument,
    persistListAutoPauseNow,
    clearPersistedListAutoPause,
    currentFinalistsInputFingerprint,
    rememberListAutoFreshness,
    patchStrategyMatrixTablePrefs,
  } = ctx;

  async function runListBatch() {
    if (!listDetail?.instrumentIds.length) {
      setBatchError("La lista no tiene valores.");
      return;
    }
    if (runSource === "saved" && !savedStrategyId) {
      setBatchError("Elige una estrategia guardada.");
      return;
    }
    if (periodPreset === "custom" && (!customDateFrom || !customDateTo)) {
      setBatchError("Indica fechas desde/hasta.");
      return;
    }

    batchAbortRef.current?.abort();
    const controller = new AbortController();
    batchAbortRef.current = controller;
    setBatchError(null);
    setExploreRows([]);
    setBatchRunning(true);
    setResultFocus("ranking");
    setBatchProgress({ done: 0, total: listDetail.instrumentIds.length });

    try {
      const rows = await runBacktestBatch({
        instrumentIds: listDetail.instrumentIds,
        labels: instrumentLabels,
        ...(runSource === "saved"
          ? { strategyDefinitionId: savedStrategyId }
          : { strategyType }),
        initialCash: Number(initialCash),
        commissionBps: Number(commissionBps) || 0,
        slippageBps: Number(slippageBps) || 0,
        timeframe: runTimeframe,
        window: resolveBacktestWindow(
          periodPreset,
          customDateFrom,
          customDateTo,
          diaD,
        ),
        signal: controller.signal,
        onProgress: (next, done, total) => {
          setBatchRows(next);
          setBatchProgress({ done, total });
        },
        onRunComplete: seedBacktestDetail,
      });
      setBatchRows(rows);
      setSelectedId(null);
      setResultFocus("ranking");
      patchSearchParams((params) => {
        params.delete("runId");
        params.set("tab", "run");
      });
      pruneAfterBatch(rows.filter((r) => r.status === "ok").length);
      void queryClient.invalidateQueries({ queryKey: ["research"] });
    } catch (error) {
      setBatchError(
        error instanceof Error ? error.message : "Error en la batería",
      );
    } finally {
      setBatchRunning(false);
      batchAbortRef.current = null;
    }
  }

  async function runCoachBattery(
    targetRowIds: string[],
    opts?: {
      lockFilterToPreset?: boolean;
      lockFilter?: "preset" | "all";
      /** Filas extra (p. ej. Mejores Lab recién creados) no aún en matrixRowsForUi. */
      extraRows?: StrategyMatrixRow[];
      pass?: "initial" | "post_lab";
      /** Se fusionan tras la batería (avisos sin re-score). */
      carryRows?: ExplorePresetRow[];
      markLabImproved?: boolean;
      forceResim?: boolean;
    },
  ): Promise<{ okCount: number; error?: string }> {
    if (!instrumentId) {
      setExploreError("Elige un valor.");
      return { okCount: 0, error: "Elige un valor." };
    }
    if (periodPreset === "custom" && (!customDateFrom || !customDateTo)) {
      setExploreError("Indica fechas desde/hasta.");
      return { okCount: 0, error: "Indica fechas desde/hasta." };
    }
    if (targetRowIds.length === 0 && !opts?.carryRows?.length) {
      const err =
        matrixFilter === "finalists"
          ? "No hay finalistas en este valor. Guarda un TOP desde Coach o cambia de filtro."
          : matrixFilter === "mine"
            ? "No hay estrategias en Mis estrategias (o ninguna seleccionada)."
            : matrixFilter === "optimized"
              ? "No hay Optimizadas seleccionadas en este filtro."
              : matrixFilter === "preset"
                ? "No hay genéricas seleccionadas en este filtro."
                : "No hay estrategias para probar en este filtro.";
      setExploreError(err);
      return { okCount: 0, error: err };
    }

    exploreAbortRef.current?.abort();
    batchAbortRef.current?.abort();
    const controller = new AbortController();
    exploreAbortRef.current = controller;
    setExploreError(null);
    setBatchRows([]);
    setResultFocus("coach");
    setCoachPass(opts?.pass ?? "initial");
    const lock =
      opts?.lockFilter ?? (opts?.lockFilterToPreset ? "preset" : undefined);
    if (lock === "preset") {
      setMatrixFilter("preset");
      patchStrategyMatrixTablePrefs({ filter: "preset" });
    } else if (lock === "all") {
      setMatrixFilter("all");
      patchStrategyMatrixTablePrefs({ filter: "all" });
    }

    const targetSet = new Set(targetRowIds);
    const batteryRows = [...(opts?.extraRows ?? []), ...matrixRowsForUi];
    const fingerprint = buildCoachBatteryFingerprint({
      contextFingerprint: matrixRunFingerprint,
      targetRowIds,
    });
    const forceResim =
      Boolean(opts?.forceResim) ||
      Boolean(opts?.extraRows?.length) ||
      opts?.pass === "post_lab";
    const reuseDecision = canReuseCoachLote({
      preferReuse: assistantPrefs.universe.reuseLoteIfUnchanged,
      fingerprint,
      lastFingerprint: lastBatteryFingerprintRef.current,
      rows: batteryRows,
      targetRowIds,
      forceResim,
    });

    if (reuseDecision.reuse) {
      setExploreRunning(true);
      setExploreProgress({
        done: targetRowIds.length,
        total: Math.max(1, targetRowIds.length),
      });
      const explore = [
        ...exploreRowsFromMatrix(batteryRows, targetSet, queryClient).map(
          (r) =>
            opts?.markLabImproved
              ? { ...r, labPass: "lab_improved" as const }
              : r,
        ),
        ...(opts?.carryRows ?? []),
      ];
      setExploreRows(explore);
      setSelectedId(null);
      setAssistantStatus(
        `Coach: lote reutilizado (${targetRowIds.length} estrat.) · mismo valor/periodo/set.`,
      );
      setExploreRunning(false);
      exploreAbortRef.current = null;
      patchSearchParams((params) => {
        params.delete("runId");
        params.set("tab", "run");
      });
      return { okCount: explore.filter((r) => r.status === "ok").length };
    }

    setExploreRunning(true);
    setExploreProgress({ done: 0, total: Math.max(1, targetRowIds.length) });
    setAssistantStatus(null);

    try {
      let explore: ExplorePresetRow[] = [...(opts?.carryRows ?? [])];
      if (targetRowIds.length > 0) {
        const rows = await runStrategyMatrixBattery({
          instrumentId,
          selectedRowIds: targetRowIds,
          rows: batteryRows,
          initialCash: Number(initialCash),
          commissionBps: Number(commissionBps) || 0,
          slippageBps: Number(slippageBps) || 0,
          timeframe: runTimeframe,
          window: resolveBacktestWindow(
            periodPreset,
            customDateFrom,
            customDateTo,
            diaD,
          ),
          concurrency: 4,
          signal: controller.signal,
          onProgress: (next, progress) => {
            setMatrixRows(next);
            setExploreProgress({ done: progress.done, total: progress.total });
            const partial = exploreRowsFromMatrix(
              next,
              targetSet,
              queryClient,
            ).map((r) =>
              opts?.markLabImproved
                ? { ...r, labPass: "lab_improved" as const }
                : r,
            );
            setExploreRows([...partial, ...(opts?.carryRows ?? [])]);
          },
          onRunComplete: seedBacktestDetail,
        });
        setMatrixRows(rows);
        explore = [
          ...exploreRowsFromMatrix(rows, targetSet, queryClient).map((r) =>
            opts?.markLabImproved
              ? { ...r, labPass: "lab_improved" as const }
              : r,
          ),
          ...(opts?.carryRows ?? []),
        ];
        pruneAfterBatch(
          rows.filter((r) => targetSet.has(r.rowId) && r.status === "ok")
            .length,
        );
        lastBatteryFingerprintRef.current = fingerprint;
      }
      setExploreRows(explore);
      setSelectedId(null);
      setResultFocus("coach");
      patchSearchParams((params) => {
        params.delete("runId");
        params.set("tab", "run");
      });
      void queryClient.invalidateQueries({ queryKey: ["research"] });
      void queryClient.invalidateQueries({ queryKey: ["strategies"] });
      return { okCount: explore.filter((r) => r.status === "ok").length };
    } catch (error) {
      const msg =
        error instanceof Error ? error.message : "Error en la exploración";
      setExploreError(msg);
      lastBatteryFingerprintRef.current = null;
      return { okCount: 0, error: msg };
    } finally {
      setExploreRunning(false);
      exploreAbortRef.current = null;
    }
  }

  function startOptimizeFromExplore(
    row: ExplorePresetRow,
    source: OptimizeSeed["source"],
  ) {
    if (!instrumentId) return;
    const symbol =
      instrumentLabels[instrumentId]?.symbol ??
      instruments.find((inst) => inst.id === instrumentId)?.symbol;
    openGuidedOptimize(
      buildOptimizeSeedFromExploreRow(row, {
        instrumentId,
        symbol,
        initialCash: Number(initialCash) || 10_000,
        timeframe: runTimeframe,
        barLimit: row.barCount,
        source,
      }),
    );
  }

  function settleFullCycle(
    reason: FullCycleSettleReason,
    statusMessage?: string,
  ) {
    const settledCampaign = listAutoRef.current;
    const settledId =
      settledCampaign && !settledCampaign.aborted
        ? settledCampaign.instrumentIds[settledCampaign.index]
        : null;
    if (settledId) {
      void import("@/features/trading/estudio-lane-stamps").then((m) => {
        m.touchEstudioLaneStamp(
          settledId,
          settledCampaign?.forceRescan ? "rediscover" : "freshness",
        );
      });
    }
    void import("@/features/trading/estudio-process-status").then((m) => {
      m.emitEstudioProcessRunning({ instrumentId: null, lane: null });
    });
    if (statusMessage) setAssistantStatus(statusMessage);
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    coach1AdvancePendingRef.current = false;
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    const saved = reason === "saved";
    const skippedFinalists =
      reason === "skip_finalists" ||
      reason === "skip_lab" ||
      reason === "skip_fresh";
    setAssistantProgress((p) => {
      const next = {
        ...p,
        labDone: true,
        finalistsDone: true,
        finalistsSaved: saved,
        finalistsSkipped: !saved && skippedFinalists,
      };
      assistantProgressRef.current = next;
      return next;
    });
    if (saved) {
      setResultFocus("finalists");
      patchSearchParams((params) => {
        params.set("focus", "finalists");
      });
    }

    const campaign = listAutoRef.current;
    if (campaign && !campaign.aborted) {
      // Un solo settle por índice (Universo vacío + Lab vacío no deben avanzar 2×).
      if (listAutoSettleLockRef.current === campaign.index) return;
      listAutoSettleLockRef.current = campaign.index;
      const settledIndex = campaign.index;
      const settledId = campaign.instrumentIds[settledIndex]!;
      const afterKey = listAutoTopFingerprint(instrumentTop);
      const freshness = readFinalistsFreshness(
        instrumentTop?.coachFacts as Record<string, unknown> | null | undefined,
      );
      const settledFp = currentFinalistsInputFingerprint(settledId);
      const beforeKey = listAutoBoard?.rows[settledIndex]?.beforeTopKey ?? null;
      const changeKind = resolveListAutoChange({
        reason,
        beforeTopKey: beforeKey,
        afterTopKey: afterKey,
      });
      const facts = instrumentTop?.coachFacts as
        | Record<string, unknown>
        | null
        | undefined;
      const slot1StrategyId =
        instrumentTop?.slots?.[0]?.strategyDefinitionId ?? null;
      const oosFromFacts = readLabEvidenceFromCoachFacts(facts);
      const oosStash = readStashedOosEvidence(slot1StrategyId);
      const oosForJudge =
        oosFromFacts && oosFromFacts.kind !== "none" ? oosFromFacts : oosStash;
      const reeval = judgeCoreR({
        settleReason: reason,
        change: changeKind,
        evidenceLevel: instrumentTop?.evidenceLevel ?? null,
        dualAudit: (facts?.dualAudit as CoreRDualAuditSnap | undefined) ?? null,
        oos: oosForJudge
          ? {
              kind: oosForJudge.kind,
              pbo: oosForJudge.pbo,
              credibility: oosForJudge.credibility,
              oosReturnPct: oosForJudge.oosReturnPct,
              edgeBand: oosForJudge.edgeBand,
            }
          : null,
        topProfileId:
          typeof facts?.profileId === "string" ? facts.profileId : null,
        activeProfileId: coachProfilePolicy.profileId ?? null,
        slot1RunId: instrumentTop?.slots?.[0]?.runId ?? null,
        instrumentId: settledId,
        timeframe: runTimeframe,
        symbol: symbolForInstrument(settledId),
      });
      // Huella local síncrona YA (antes del PUT): si Stop/reinicio cortan el await,
      // el próximo Play aún puede omitir.
      // Siempre memoria + local: tras reinicio omitimos sin exigir TOP active.
      listAutoFreshnessMemoryRef.current.set(settledId, settledFp);
      writeLocalFreshnessFingerprint({
        instrumentId: settledId,
        timeframe: runTimeframe,
        fingerprint: settledFp,
        at:
          reason === "skip_fresh"
            ? freshness?.lastSearchAt
            : new Date().toISOString(),
      });
      const stampPromise =
        reason === "skip_fresh"
          ? Promise.resolve()
          : rememberListAutoFreshness(settledId, settledFp, {
              lab: reason === "saved",
            });
      setListAutoBoard((b) =>
        b
          ? markListAutoBoardSettled(b, settledIndex, reason, {
              detail: statusMessage ?? reeval.reason,
              afterTopKey: afterKey,
              lastSearchAt:
                reason === "skip_fresh"
                  ? (freshness?.lastSearchAt ?? new Date().toISOString())
                  : reason === "saved"
                    ? new Date().toISOString()
                    : (freshness?.lastSearchAt ?? new Date().toISOString()),
              reeval,
            })
          : b,
      );

      void stampPromise.finally(() => {
        const live = listAutoRef.current;
        if (!live || live.aborted) return;
        const adv = advanceListAutoAfterSettle(live);
        if (adv === "done" || adv === "aborted") {
          const total = live.instrumentIds.length;
          listAutoRef.current = null;
          listAutoPendingStartRef.current = null;
          setListAutoUi(null);
          setListAutoBoard((b) => {
            if (!b) return null;
            const done = markListAutoBoardDone(b);
            try {
              saveCoreRReport(
                buildCoreRReportFromBoard({
                  listId: done.listId,
                  timeframe: runTimeframe,
                  rows: done.rows,
                }),
              );
            } catch {
              // ignore
            }
            return done;
          });
          setFullCycleActive(false);
          clearPersistedListAutoPause();
          clearListAutoContinueSnapshot();
          setAssistantStatus(listAutoDoneStatus(total));
          setResultFocus("list_auto");
          return;
        }
        if (adv === "paused") {
          const symbol = symbolForInstrument(live.instrumentIds[live.index]!);
          setListAutoUi({
            index: live.index,
            total: live.instrumentIds.length,
            symbol,
          });
          setListAutoBoard((b) => {
            const next = b ? markListAutoBoardPaused(b, true) : b;
            if (next) persistListAutoPauseNow(live, next);
            return next;
          });
          setFullCycleActive(false);
          setAssistantStatus(
            listAutoPausedStatus({
              index: live.index,
              total: live.instrumentIds.length,
              symbol,
            }),
          );
          setResultFocus("list_auto");
          return;
        }
        setAssistantStatus(
          `${listAutoProgressLabel({
            index: live.index,
            total: live.instrumentIds.length,
            symbol: symbolForInstrument(live.instrumentIds[live.index]!),
          })} · ${reason} → siguiente…`,
        );
        queueListAutoTicker(live.index);
      });
      return;
    }

    setFullCycleActive(false);
  }

  return {
    runListBatch,
    runCoachBattery,
    startOptimizeFromExplore,
    settleFullCycle,
  };
}
