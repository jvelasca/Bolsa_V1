/**
 * Handlers Lab extraídos de `BacktestsPage` — navegación y Coach→Lab.
 *
 * Extraído de `backtests-page.tsx` (Track B B9) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 *
 * Dos factories por dependencia circular con orchestration:
 * - `createBacktestLabNavigationHandlers` (antes de orchestration; provee openGuidedOptimize)
 * - `createBacktestLabCoachHandlers` (después; consume runCoachBattery / settleFullCycle)
 *
 * Recrear las funciones cada llamada (cada render). NO memoizar: el original
 * no estaba memoizado; useCallback/useMemo stale-cerrarían instrumentId /
 * fullCycleActive / campaign.
 */

import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { QueryClient } from "@tanstack/react-query";
import {
  BACKTEST_STRATEGIES,
  STRATEGY_PRESET_CATEGORY_LABELS,
  type BacktestStrategyType,
  type ChartTimeframe,
  type InstrumentStrategyTopV1,
  type InstrumentWithMetaDto,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { universeEmptyStatus } from "@/features/backtests/backtest-assistant-full-cycle";
import type { AssistantSessionProgress } from "@/features/backtests/backtest-assistant-completion";
import type { AssistantPrefs } from "@/features/backtests/backtest-assistant-prefs";
import {
  finalistMatrixRowIds,
  mergeUniverseTargetIds,
} from "@/features/backtests/backtest-coach-lote";
import type { ExplorePresetRow } from "@/features/backtests/backtest-explore-value";
import type {
  LabBoardZone,
  LabReanalyzeRequest,
} from "@/features/backtests/backtest-lab-board-types";
import { padLabZones } from "@/features/backtests/backtest-lab-board-types";
import type { ListAutoCampaign } from "@/features/backtests/backtest-list-auto";
import type { FullCycleSettleReason } from "@/features/backtests/backtest-list-auto";
import { buildOptimizeRequestsFromSeed } from "@/features/backtests/backtest-optimize-from-seed";
import {
  buildOptimizeSeedFromExploreRow,
  isOptimizableStrategy,
  type OptimizeSeed,
} from "@/features/backtests/backtest-optimize-seed";
import {
  STRATEGY_MATRIX_MAX_SELECTED,
  exploreBatteryRowIds,
  type StrategyMatrixRow,
} from "@/features/backtests/backtest-strategy-matrix";
import type {
  HubTab,
  ResultFocus,
} from "@/features/backtests/backtests-page.constants";

export interface BacktestLabNavigationCtx {
  setOptimizeSeed: Dispatch<SetStateAction<OptimizeSeed | null>>;
  setInstrumentId: Dispatch<SetStateAction<string>>;
  setLabZones: Dispatch<SetStateAction<LabBoardZone[] | null>>;
  setLabOpenedThisRun: Dispatch<SetStateAction<boolean>>;
  setTab: (next: HubTab) => void;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
}

export interface BacktestLabCoachCtx {
  queryClient: QueryClient;
  instrumentId: string;
  fullCycleActive: boolean;
  assistantPrefs: AssistantPrefs;
  matrixRowsForUi: StrategyMatrixRow[];
  instrumentTop: InstrumentStrategyTopV1 | null;
  instrumentLabels: Record<string, { symbol: string; name: string }>;
  instruments: InstrumentWithMetaDto[];
  initialCash: string;
  runTimeframe: ChartTimeframe;
  listAutoRef: MutableRefObject<ListAutoCampaign | null>;

  setAssistantStatus: Dispatch<SetStateAction<string | null>>;
  setLabImprovedThisCycle: Dispatch<SetStateAction<number>>;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  setAssistantProgress: Dispatch<SetStateAction<AssistantSessionProgress>>;
  setCoachPass: Dispatch<SetStateAction<"initial" | "post_lab">>;
  setMatrixSelectedIds: Dispatch<SetStateAction<Set<string>>>;
  setSemifinalEnqueuePending: Dispatch<SetStateAction<boolean>>;
  setSemifinalJobsQueued: Dispatch<SetStateAction<boolean>>;
  setLabOpenedThisRun: Dispatch<SetStateAction<boolean>>;
  setTab: (next: HubTab) => void;

  runCoachBattery: (
    targetRowIds: string[],
    opts?: {
      lockFilterToPreset?: boolean;
      lockFilter?: "preset" | "all";
      extraRows?: StrategyMatrixRow[];
      pass?: "initial" | "post_lab";
      carryRows?: ExplorePresetRow[];
      markLabImproved?: boolean;
      forceResim?: boolean;
    },
  ) => Promise<{ okCount: number; error?: string }>;
  settleFullCycle: (
    reason: FullCycleSettleReason,
    statusMessage?: string,
  ) => void;
  openLabBoard: (zones: LabBoardZone[]) => void;
}

export function createBacktestLabNavigationHandlers(
  ctx: BacktestLabNavigationCtx,
) {
  const {
    setOptimizeSeed,
    setInstrumentId,
    setLabZones,
    setLabOpenedThisRun,
    setTab,
    setResultFocus,
  } = ctx;

  function openGuidedOptimize(
    seed: OptimizeSeed,
    extras?: {
      rank?: 1 | 2 | 3;
      stars?: number;
      starsCapped?: boolean;
      jobId?: string | null;
    },
  ) {
    setOptimizeSeed(seed);
    setInstrumentId(seed.instrumentId);
    const rank = extras?.rank ?? 1;
    const zone: LabBoardZone = {
      id: `zone-${rank}-${seed.strategyType}`,
      rank,
      seed,
      jobId: extras?.jobId ?? null,
      stars: extras?.stars,
      starsCapped: extras?.starsCapped,
      coachLabel: seed.strategyLabel,
    };
    setLabZones(padLabZones([zone]));
    setLabOpenedThisRun(true);
    setTab("run");
    setResultFocus("lab");
  }

  function openLabBoard(zones: LabBoardZone[]) {
    const padded = padLabZones(zones);
    setLabZones(padded);
    const first = padded.find((z) => z.seed);
    if (first?.seed) {
      setOptimizeSeed(first.seed);
      setInstrumentId(first.seed.instrumentId);
    }
    setLabOpenedThisRun(true);
    setTab("run");
    setResultFocus("lab");
  }

  return { openGuidedOptimize, openLabBoard };
}

export function createBacktestLabCoachHandlers(ctx: BacktestLabCoachCtx) {
  const {
    queryClient,
    instrumentId,
    fullCycleActive,
    assistantPrefs,
    matrixRowsForUi,
    instrumentTop,
    instrumentLabels,
    instruments,
    initialCash,
    runTimeframe,
    listAutoRef,
    setAssistantStatus,
    setLabImprovedThisCycle,
    setResultFocus,
    setAssistantProgress,
    setCoachPass,
    setMatrixSelectedIds,
    setSemifinalEnqueuePending,
    setSemifinalJobsQueued,
    setLabOpenedThisRun,
    setTab,
    runCoachBattery,
    settleFullCycle,
    openLabBoard,
  } = ctx;

  /** Lab → Coach²: re-simula Mejores; carries van sin re-score. */
  async function reanalyzeLabWithCoach(payload: LabReanalyzeRequest) {
    if (!instrumentId) {
      setAssistantStatus("Elige un valor antes de reanalizar.");
      return;
    }
    await queryClient.invalidateQueries({ queryKey: ["strategies"] });

    const extraRows: StrategyMatrixRow[] = payload.improved.map((item) => ({
      rowId: `saved:${item.strategyId}`,
      kind: "saved" as const,
      label: item.label,
      subtitle: "Lab · Mejor",
      // Identidad explore/coach = tipo Coach original (evita colapsar 2 proxies SMA en 1).
      // El preset ejecutable va en la def; buildCoachTopSlots/sanitize lo usan al grabar TOP.
      presetKey: (item.strategyType ?? item.presetKey ?? undefined) as
        | BacktestStrategyType
        | undefined,
      strategyDefinitionId: item.strategyId,
      origin: "preset",
      savedBucket: "optimized" as const,
      status: "idle" as const,
    }));

    const carryRows: ExplorePresetRow[] = payload.carried.map((c) => {
      const strategyType = (c.strategyType ??
        "sma_crossover") as BacktestStrategyType;
      const meta = BACKTEST_STRATEGIES[strategyType];
      const category = meta?.category ?? "trend";
      return {
        strategyType,
        label: `${c.label} · no mejoró en Lab`,
        category,
        categoryLabel: STRATEGY_PRESET_CATEGORY_LABELS[category] ?? category,
        status: "ok" as const,
        labPass: "lab_carry" as const,
      };
    });

    setAssistantStatus(
      `Reanalizando ${payload.improved.length} Mejor(es) Lab con Coach` +
        (payload.carried.length
          ? ` · ${payload.carried.length} aviso(s) sin mejora`
          : "") +
        "…",
    );

    setLabImprovedThisCycle(payload.improved.length);
    setResultFocus("coach");
    await runCoachBattery(
      payload.improved.map((i) => `saved:${i.strategyId}`),
      {
        extraRows,
        pass: "post_lab",
        carryRows,
        markLabImproved: true,
      },
    );
    setAssistantProgress((p) => ({ ...p, labDone: true }));
    if (fullCycleActive) {
      setAssistantStatus(
        payload.improved.length
          ? "Ciclo: Coach² listo · evaluando Finalistas…"
          : "Ciclo: Lab sin Mejor guardable. No se pisan Finalistas active.",
      );
    } else {
      setAssistantStatus(
        payload.improved.length
          ? "Coach tras Lab listo. Revisa ★ y guarda Finalistas si te convencen."
          : "Coach: solo avisos sin mejora. Optimiza de nuevo en Lab o cambia de candidatas.",
      );
    }
  }

  /** Asistente / revalidar: genéricas ∪ Finalistas (± Optimizadas ± Mis). */
  async function runExploreValue(): Promise<{
    okCount: number;
    error?: string;
  }> {
    setCoachPass("initial");
    const includeOptimized = assistantPrefs.universe.includeOptimizedStrategies;
    const includeMine = assistantPrefs.universe.includeMineStrategies;
    const includeFinalists = assistantPrefs.universe.includeFinalistsInBattery;
    const optimizedIds = matrixRowsForUi
      .filter((r) => r.kind === "saved" && r.savedBucket === "optimized")
      .map((r) => r.rowId);
    const mineIds = matrixRowsForUi
      .filter((r) => r.kind === "saved" && r.savedBucket === "mine")
      .map((r) => r.rowId);
    const finalistIds = finalistMatrixRowIds(instrumentTop?.slots ?? []);
    const targets = mergeUniverseTargetIds({
      presetIds: exploreBatteryRowIds(),
      finalistRowIds: finalistIds,
      includeFinalists,
      optimizedRowIds: optimizedIds,
      includeOptimized,
      mineRowIds: mineIds,
      includeMine,
      max: STRATEGY_MATRIX_MAX_SELECTED,
    });
    if (
      (includeOptimized && optimizedIds.length > 0) ||
      (includeMine && mineIds.length > 0) ||
      (includeFinalists && finalistIds.length > 0)
    ) {
      setMatrixSelectedIds(new Set(targets));
    }
    return runCoachBattery(targets, {
      lockFilter:
        includeOptimized ||
        includeMine ||
        (includeFinalists && finalistIds.length > 0)
          ? "all"
          : "preset",
    });
  }

  async function optimizeSemifinalFromCoach(
    candidates: Array<{
      row: ExplorePresetRow;
      stars?: number;
      starsCapped?: boolean;
      rank?: number;
    }>,
  ): Promise<"opened" | "skipped"> {
    if (!instrumentId) {
      setAssistantStatus("Elige un valor antes de optimizar la semifinal.");
      return "skipped";
    }
    const symbol =
      instrumentLabels[instrumentId]?.symbol ??
      instruments.find((inst) => inst.id === instrumentId)?.symbol;
    const top3 = candidates.slice(0, 3);
    const withGrid = top3.filter((c) =>
      isOptimizableStrategy(c.row.strategyType),
    );
    const skipped = top3.filter(
      (c) => !isOptimizableStrategy(c.row.strategyType),
    );

    if (withGrid.length === 0) {
      const msg = skipped.length
        ? `Ninguna de las ${skipped.length} candidatas tiene grid nativo (p. ej. Bollinger). Guarda TOP semifinal o elige otras.`
        : "No hay candidatas para el laboratorio.";
      setAssistantStatus(msg);
      if (fullCycleActive || listAutoRef.current) {
        settleFullCycle("skip_lab", universeEmptyStatus(msg));
      }
      return "skipped";
    }

    setSemifinalEnqueuePending(true);
    setAssistantStatus(null);
    const zones: LabBoardZone[] = [];
    const errors: string[] = [];
    try {
      for (let i = 0; i < withGrid.length; i++) {
        const cand = withGrid[i]!;
        const row = cand.row;
        const rank = (i + 1) as 1 | 2 | 3;
        const seed = buildOptimizeSeedFromExploreRow(row, {
          instrumentId,
          symbol,
          initialCash: Number(initialCash) || 10_000,
          timeframe: runTimeframe,
          barLimit: row.barCount,
          source: "explore_best",
        });
        const bodies = buildOptimizeRequestsFromSeed(seed);
        const jobIds: string[] = [];
        if (bodies.length === 0) {
          errors.push(row.label);
        } else {
          for (const body of bodies) {
            try {
              const res = await api.enqueueOptimizeJob(body);
              jobIds.push(res.data.id);
            } catch {
              errors.push(`${row.label} (${body.engine ?? "job"})`);
            }
          }
        }
        zones.push({
          id: `zone-${rank}-${row.strategyType}`,
          rank,
          seed,
          jobId: jobIds[0] ?? null,
          jobIds: jobIds.length > 0 ? jobIds : null,
          stars: cand.stars,
          starsCapped: cand.starsCapped,
          coachLabel: row.label,
        });
      }
      const skipNote = skipped.length
        ? ` · omitidas sin grid: ${skipped.map((c) => c.row.label).join(", ")}`
        : "";
      const errNote = errors.length ? ` · fallos: ${errors.join(", ")}` : "";
      const queued = zones.reduce(
        (n, z) => n + (z.jobIds?.length ?? (z.jobId ? 1 : 0)),
        0,
      );
      const smaDual = zones.some((z) => (z.jobIds?.length ?? 0) > 1);
      setAssistantStatus(
        `Lab: ${zones.length} zona(s)${
          queued
            ? ` · ${queued} job(s) en curso${smaDual ? " (H0+Optuna)" : ""}`
            : ""
        }${skipNote}${errNote}. Adopta solo si Mejor ≥ ancla (OOS).`,
      );
      if (queued > 0) setSemifinalJobsQueued(true);
      if (zones.length > 0 && queued > 0) {
        openLabBoard(zones);
        return "opened";
      }
      // Zonas sin jobs encolados → el board las marcaría terminal al instante;
      // cerramos aquí para no dejar «Lab en curso» colgado.
      setLabOpenedThisRun(true);
      setTab("run");
      setResultFocus("lab");
      if (fullCycleActive || listAutoRef.current) {
        settleFullCycle(
          "skip_lab",
          universeEmptyStatus(
            errors.length ? errors.join(", ") : "sin jobs Lab",
          ),
        );
      }
      return "skipped";
    } catch {
      if (fullCycleActive || listAutoRef.current) {
        settleFullCycle("skip_lab", universeEmptyStatus("error Lab enqueue"));
      }
      return "skipped";
    } finally {
      setSemifinalEnqueuePending(false);
    }
  }

  return { reanalyzeLabWithCoach, runExploreValue, optimizeSemifinalFromCoach };
}
