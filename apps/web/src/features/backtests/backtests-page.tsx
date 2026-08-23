/**
 * Hub Backtesting (`/backtests`) — orquestación UI del embudo.
 *
 * Ciclo completo / Lista AUTO / Finalistas Checklist+Proponer / Lab handoff.
 * Política motor: `backtest-assistant-full-cycle.ts`, `backtest-list-auto.ts`.
 * Documentación: `docs/engineering/session-handoff-2026-07-30.md` ·
 * `docs/engineering/list-auto-ops-2026-07-29.md`.
 */

import { parseTab } from "@/features/backtests/backtest-hub-nav";
import {
  STRATEGY_OPTIONS,
  type ResultFocus,
  type RunSource,
  type StrategiesListFilter,
  type UniverseMode,
} from "@/features/backtests/backtests-page.constants";
import { useBacktestPageQueries } from "@/features/backtests/hooks/use-backtest-page-queries";
import { useBacktestPageMutations } from "@/features/backtests/hooks/use-backtest-page-mutations";
import { useBacktestDerivedData } from "@/features/backtests/hooks/use-backtest-derived-data";
import { useBacktestUrlSync } from "@/features/backtests/hooks/use-backtest-url-sync";
import {
  createBacktestListAutoController,
  useBacktestListAutoEffects,
  type ListAutoStartOverrides,
  type ListAutoUiState,
} from "@/features/backtests/lib/backtest-list-auto-controller";
import {
  createBacktestAssistantController,
  useBacktestAssistantEffects,
} from "@/features/backtests/lib/backtest-assistant-controller";
import { BacktestHubTabsBar } from "@/features/backtests/backtest-hub-tabs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Navigate,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import {
  BACKTEST_STRATEGIES,
  type BacktestStrategyType,
  type ChartDrawing,
  type ChartStrategySetupDraft,
  type ChartTimeframe,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { useListAutoActivityStore } from "@/stores/list-auto-activity-store";
import {
  type BatchRankRow,
  type BatchSortKey,
} from "@/features/backtests/backtest-batch-run";
import {
  type ExplorePresetRow,
  type ExploreSortKey,
} from "@/features/backtests/backtest-explore-value";
import { type OptimizeBeforeAfterSnapshot } from "@/features/backtests/backtest-optimize-delta";
import type { LabBoardZone } from "@/features/backtests/backtest-lab-board-types";
import {
  buildOptimizeSeedFromRun,
  type OptimizeSeed,
} from "@/features/backtests/backtest-optimize-seed";
import { BacktestAssistantRail } from "@/features/backtests/backtest-assistant-rail";
import {
  emptyAssistantProgress,
  type AssistantSessionProgress,
} from "@/features/backtests/backtest-assistant-completion";
import {
  loadAssistantPrefs,
  type AssistantPrefs,
} from "@/features/backtests/backtest-assistant-prefs";
import {
  listAutoPlayTitle,
  type ListAutoCampaign,
} from "@/features/backtests/backtest-list-auto";
import { loadBacktestRunContext } from "@/features/backtests/backtest-run-context";
import type { ListAutoBoardState } from "@/features/backtests/backtest-list-auto-board";
import { type AssistantStepId } from "@/features/backtests/backtest-assistant-steps";
import { equityCurveFromDetail } from "@/features/backtests/backtest-export";
import { BacktestLibraryTab } from "@/features/backtests/backtest-library-tab";
import { parseLibraryFilterParam } from "@/features/backtests/library-nav";
import { BacktestHistoryTab } from "@/features/backtests/backtest-history-tab";
import {
  STRATEGY_MATRIX_MAX_SELECTED,
  buildStrategyMatrixRows,
  type StrategyMatrixFilter,
  type StrategyMatrixRow,
} from "@/features/backtests/backtest-strategy-matrix";
import {
  BacktestZoneSettingsButton,
  BacktestZoneSettingsDialog,
} from "@/features/backtests/backtest-zone-settings-dialog";
import {
  loadBacktestZonePrefs,
  patchStrategyMatrixTablePrefs,
  type BacktestZonePrefs,
} from "@/features/backtests/backtest-zone-prefs";
import {
  defaultMineStrategiesFilters,
  type MineStrategiesFilterState,
} from "@/features/backtests/mine-strategies-filters";
import {
  PAPER_PATH_LAB,
  PAPER_PATH_SUPERVISED,
} from "@/features/settings/paper-paths-copy";
import { proposeFinalistSupervised } from "@/features/backtests/finalist-propose-supervised";
import { isOpenAnalysisQuery } from "@/features/backtests/strategy-monitor";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useAlertsStore } from "@/stores/alerts-store";
import {
  openHelpAiPlatform,
  useSupervisedF3QueueStore,
} from "@/stores/supervised-f3-queue-store";
import { useMediaQuery } from "@/lib/use-media-query";
import {
  DEFAULT_PERIOD_PRESET,
  type PeriodPreset,
} from "@/features/backtests/backtest-period";
import { BacktestDiaDOriginControl } from "@/features/backtests/backtest-dia-d-origin-control";
import { DiaDVerifyHost } from "@/features/backtests/dia-d-verify-host";
import { UniverseChip } from "@/features/platform/universe-chip";
import { setAdoption } from "@/features/platform/strategy-adoption";
import { useDiaDTradingSessionStore } from "@/stores/dia-d-trading-session-store";
import { createBacktestOrchestration } from "@/features/backtests/lib/backtest-orchestration";
import {
  createBacktestLabCoachHandlers,
  createBacktestLabNavigationHandlers,
} from "@/features/backtests/lib/backtest-lab-handlers";
import { createBacktestPageNavigation } from "@/features/backtests/lib/backtest-page-navigation";
import {
  BacktestsPageJobsTab,
  type BacktestPageJobsViewModel,
} from "@/features/backtests/backtests-page-jobs-tab";
import {
  BacktestsPageRunTab,
  type BacktestPageViewModel,
} from "@/features/backtests/backtests-page-run-tab";

export function BacktestsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const onBacktestsRoute = pathname.startsWith("/backtests");
  const tabParam = searchParams.get("tab");
  // Nota: la redirección legacy `/backtests?tab=screeners` → `/screeners` se
  // resuelve justo antes del return principal (después de todos los hooks) para
  // respetar la Regla de Hooks (orden estable) — ver las ~150 llamadas a hooks
  // que siguen y el bloque `if` previo al `return` principal.
  const tab = parseTab(tabParam);
  const runIdFromUrl = searchParams.get("runId");

  const queryClient = useQueryClient();
  const { effectiveAccountId } = useActiveAccount();
  const diaDVerifySession = useDiaDTradingSessionStore((s) => s.session);
  /** Solo hijack Análisis técnico con ?verify=1 (no por sesión residual en localStorage). */
  const diaDVerifyActive =
    searchParams.get("verify") === "1" && Boolean(diaDVerifySession);
  const diaDVerifyFullBleed = Boolean(
    diaDVerifyActive && diaDVerifySession?.fullBleedMovie,
  );
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enqueueSupervised = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActiveSupervised = useSupervisedF3QueueStore((s) => s.setActive);
  const [instrumentId, setInstrumentId] = useState(
    searchParams.get("instrumentId") ?? "",
  );
  const [universeMode, setUniverseMode] = useState<UniverseMode>("single");
  const [listId, setListId] = useState("");
  const [runSource, setRunSource] = useState<RunSource>("preset");
  const [strategyType, setStrategyType] =
    useState<BacktestStrategyType>("sma_crossover");
  const [savedStrategyId, setSavedStrategyId] = useState("");
  const [initialCash, setInitialCash] = useState(
    () => loadBacktestRunContext().initialCash || "10000",
  );
  const [commissionBps, setCommissionBps] = useState(
    () => loadBacktestRunContext().commissionBps || "0",
  );
  const [slippageBps, setSlippageBps] = useState(
    () => loadBacktestRunContext().slippageBps || "0",
  );
  const [runTimeframe, setRunTimeframe] = useState<ChartTimeframe>(
    () => (loadBacktestRunContext().timeframe as ChartTimeframe) || "1d",
  );
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>(
    () =>
      (loadBacktestRunContext().periodPreset as PeriodPreset) ||
      DEFAULT_PERIOD_PRESET,
  );
  const [customDateFrom, setCustomDateFrom] = useState(
    () => loadBacktestRunContext().customDateFrom,
  );
  const [customDateTo, setCustomDateTo] = useState(
    () => loadBacktestRunContext().customDateTo,
  );
  const [diaD, setDiaD] = useState(() => loadBacktestRunContext().diaD);
  const [selectedId, setSelectedId] = useState<string | null>(
    () => runIdFromUrl,
  );
  const [newStrategyName, setNewStrategyName] = useState("");
  const [newStrategyPreset, setNewStrategyPreset] =
    useState<BacktestStrategyType>("sma_crossover");
  const [replayDrawings, setReplayDrawings] = useState<ChartDrawing[] | null>(
    null,
  );
  const [, setDrawingLoadHint] = useState<string | null>(null);
  const [focusTimestamp, setFocusTimestamp] = useState<string | null>(null);
  const [batchRows, setBatchRows] = useState<BatchRankRow[]>([]);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ done: 0, total: 0 });
  const [batchSort, setBatchSort] = useState<BatchSortKey>("excess");
  const [batchError, setBatchError] = useState<string | null>(null);
  const [exploreRows, setExploreRows] = useState<ExplorePresetRow[]>([]);
  const [exploreRunning, setExploreRunning] = useState(false);
  const [exploreProgress, setExploreProgress] = useState({ done: 0, total: 0 });
  const [exploreSort, setExploreSort] = useState<ExploreSortKey>("excess");
  const [exploreError, setExploreError] = useState<string | null>(null);
  const [resultFocus, setResultFocus] = useState<ResultFocus>(() => {
    const focus = searchParams.get("focus");
    if (
      focus === "coach" ||
      focus === "lab" ||
      focus === "finalists" ||
      focus === "detail" ||
      focus === "fundamental" ||
      focus === "ranking" ||
      focus === "list_auto"
    ) {
      return focus;
    }
    return "detail";
  });
  const [optimizeSeed, setOptimizeSeed] = useState<OptimizeSeed | null>(null);
  const [labZones, setLabZones] = useState<LabBoardZone[] | null>(null);
  /** Coach tras Lab: techo ★5 + Guardar Finalistas. */
  const [coachPass, setCoachPass] = useState<"initial" | "post_lab">("initial");
  const [optimizeCompare, setOptimizeCompare] =
    useState<OptimizeBeforeAfterSnapshot | null>(null);
  const [assistantStatus, setAssistantStatus] = useState<string | null>(null);
  const [strategiesListFilter, setStrategiesListFilter] =
    useState<StrategiesListFilter>(
      () => parseLibraryFilterParam(searchParams.get("library")) ?? "all",
    );
  const [mineFilters, setMineFilters] = useState<MineStrategiesFilterState>(
    () => {
      const base = defaultMineStrategiesFilters();
      const q = searchParams.get("q");
      return q ? { ...base, query: q } : base;
    },
  );
  const [libraryFocusStrategyId, setLibraryFocusStrategyId] = useState<
    string | null
  >(() => searchParams.get("strategyId"));
  const [libraryFocusPreset, setLibraryFocusPreset] = useState<string | null>(
    () => searchParams.get("preset"),
  );
  const [cloneOpen, setCloneOpen] = useState(false);
  const [semifinalEnqueuePending, setSemifinalEnqueuePending] = useState(false);
  const [, setSemifinalJobsQueued] = useState(false);
  const [assistantPrefs, setAssistantPrefs] = useState<AssistantPrefs>(() =>
    loadAssistantPrefs(),
  );
  const [assistantProgress, setAssistantProgress] =
    useState<AssistantSessionProgress>(() => emptyAssistantProgress());
  /** Mirror sync del progreso: encadenar pasos en el mismo tick sin race de setState. */
  const assistantProgressRef = useRef(assistantProgress);
  assistantProgressRef.current = assistantProgress;
  /** Paso destacado en el rail mientras se ejecuta. */
  const [assistantFocus, setAssistantFocus] = useState<AssistantStepId | null>(
    null,
  );
  /** El usuario abrió Lab en esta pasada (evita ✓ lab por un TOP viejo en BD). */
  const [labOpenedThisRun, setLabOpenedThisRun] = useState(false);
  /** Play con ciclo completo activo (Coach → Lab → Coach² → Finalistas). */
  const [fullCycleActive, setFullCycleActive] = useState(false);
  /** Ciclo parado en Coach¹ / Revalidar esperando ACK humano. */
  const [awaitingAck, setAwaitingAck] = useState(false);
  const [awaitingAckStage, setAwaitingAckStage] = useState<
    "coach1" | "revalidate" | null
  >(null);
  const [coachGate, setCoachGate] = useState({
    needsAck: false,
    ack: false,
    postLab: false,
    canSaveTop: false,
  });
  /** Tras gate Lab OK, reintentar avance cuando llegue ACK¹. */
  const coach1AdvancePendingRef = useRef(false);
  /** Mejoras Lab de este ciclo (para auto-save aunque el lote re-etiquete mal). */
  const [labImprovedThisCycle, setLabImprovedThisCycle] = useState(0);
  /** Atajo semifinal armado (solo tras gate Coach¹ OK). */
  const [semifinalShortcutArmed, setSemifinalShortcutArmed] = useState(false);
  /** Abrir checklist paper al llegar a Detalle (?openAnalysis=1 o CTA Finalistas). */
  const [preferOpenAnalysis, setPreferOpenAnalysis] = useState(() =>
    isOpenAnalysisQuery(searchParams.get("openAnalysis")),
  );
  /** Campaña lista AUTO (ref = fuente de verdad; UI = progreso). */
  const listAutoRef = useRef<ListAutoCampaign | null>(null);
  /** ADR-024: Supervisión ON pide arrancar Lista AUTO sobre Estudio. */
  const supervisionStartPendingRef = useRef<string | null>(null);
  /**
   * ADR-024 capas: overrides del próximo Play (frescura / rediscubrimiento).
   * Se consumen una vez en `startListAutoCampaign`.
   */
  const listAutoStartOverridesRef = useRef<ListAutoStartOverrides | null>(null);
  /** ADR-024: ids quitados de Estudio — saltar en campaña en curso. */
  const listAutoExcludedIdsRef = useRef<Set<string>>(new Set());
  const listAutoPendingStartRef = useRef<number | null>(null);
  const [listAutoUi, setListAutoUi] = useState<ListAutoUiState | null>(null);
  /** Tablero visual de la campaña (persiste al terminar para revisar Δ). */
  const [listAutoBoard, setListAutoBoard] = useState<ListAutoBoardState | null>(
    null,
  );
  /** Filtro opcional: no encolar tickers que ya tienen Finalistas TOP. */
  const [listAutoSkipWithFinalists, setListAutoSkipWithFinalists] =
    useState(false);
  /** Fingerprints ya analizados en esta pestaña (skip sin stamp BD). */
  const listAutoFreshnessMemoryRef = useRef<Map<string, string>>(new Map());
  /** Token: fuerza el efecto de arranque aunque instrumentId no cambie. */
  const [listAutoStartToken, setListAutoStartToken] = useState(0);
  const listAutoPauseRestoredRef = useRef(false);
  /** Evita doble settle del mismo índice (saltaría tickers). */
  const listAutoSettleLockRef = useRef<number | null>(null);
  const assistantChainRef = useRef<string>("");
  const [zonePrefs, setZonePrefs] = useState<BacktestZonePrefs>(() =>
    loadBacktestZonePrefs(),
  );
  const [zoneSettingsOpen, setZoneSettingsOpen] = useState(false);
  const [matrixFilter, setMatrixFilter] = useState<StrategyMatrixFilter>(
    () => loadBacktestZonePrefs().strategyMatrix.filter,
  );
  const [matrixRows, setMatrixRows] = useState<StrategyMatrixRow[]>(() =>
    buildStrategyMatrixRows([]),
  );
  const [matrixSelectedIds, setMatrixSelectedIds] = useState<Set<string>>(
    () => new Set(),
  );
  const batchAbortRef = useRef<AbortController | null>(null);
  const exploreAbortRef = useRef<AbortController | null>(null);
  const lastBatteryFingerprintRef = useRef<string | null>(null);

  const isWide = useMediaQuery("(min-width: 1024px)");

  const pruneHistory = useCallback(
    async (keep: number) => {
      try {
        await api.pruneBacktests(keep);
      } catch {
        // Non-blocking: list still refreshes; user can retry via settings.
      }
      void queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
    [queryClient],
  );

  /** Keep detail available after multi-run even before list refresh; avoid 404 after prune. */
  const seedBacktestDetail = useCallback(
    (detail: import("@bolsa/shared").BacktestRunDetailDto) => {
      queryClient.setQueryData(["backtest", detail.id], { data: detail });
    },
    [queryClient],
  );

  /** Never prune below the OK count of the lote just created. */
  function pruneAfterBatch(okCount: number) {
    void pruneHistory(Math.max(zonePrefs.historyMaxKept, okCount));
  }

  const {
    instrumentsQuery,
    listsQuery,
    listDetailQuery,
    listQuotesQuery,
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
  } = useBacktestPageQueries({
    listId,
    universeMode,
    instrumentId,
    runTimeframe,
    effectiveAccountId,
    selectedId,
    historyMaxKept: zonePrefs.historyMaxKept,
    includeMineStrategies: assistantPrefs.universe.includeMineStrategies,
    includeOptimizedStrategies:
      assistantPrefs.universe.includeOptimizedStrategies,
    periodPreset,
    customDateFrom,
    customDateTo,
    diaD,
    initialCash,
    commissionBps,
    slippageBps,
  });

  // B3: helpers de nav antes del hook de mutations (antes vivían después;
  // function declarations se hoist-eaban; el hook necesita params explícitos).
  // B6: factory cada render (no hoist); el orden queries → nav → mutations se mantiene.
  const {
    patchSearchParams,
    openLibrary,
    setTab,
    selectRun,
    selectInstrument,
    openInstrumentInValor,
  } = createBacktestPageNavigation({
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
  });

  const {
    runMutation,
    createStrategyMutation,
    deployPaperMutation,
    saveChartStrategyMutation,
  } = useBacktestPageMutations({
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
    historyMaxKept: zonePrefs.historyMaxKept,
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
  });

  function applyChartDraft(draft: ChartStrategySetupDraft) {
    selectInstrument(draft.instrumentId);
    setUniverseMode("single");
    setRunTimeframe(draft.timeframe);
    if (draft.inferredPresetKey) {
      setRunSource("preset");
      setStrategyType(draft.inferredPresetKey);
      setMatrixSelectedIds(new Set([`preset:${draft.inferredPresetKey}`]));
      setMatrixFilter("preset");
      patchStrategyMatrixTablePrefs({ filter: "preset" });
    }
  }

  const {
    instruments,
    lists,
    listDetail,
    listMembersWithStatus,
    strategies,
    runs,
    instrumentTop,
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
    detail,
    detailFinalistBadge,
    instrumentLabels,
    instrumentSymbol,
    matrixRowsForUi,
    matrixCoachTargetIds,
  } = useBacktestDerivedData({
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
  });

  useEffect(() => {
    const saved = strategiesQuery.data?.data ?? [];
    setMatrixRows((prev) => {
      const next = buildStrategyMatrixRows(saved);
      const prevById = new Map(prev.map((r) => [r.rowId, r]));
      return next.map((row) => {
        const old = prevById.get(row.rowId);
        if (!old) return row;
        return {
          ...row,
          status: old.status,
          error: old.error,
          runId: old.runId,
          totalReturnPct: old.totalReturnPct,
          buyHoldReturnPct: old.buyHoldReturnPct,
          excessReturnPct: old.excessReturnPct,
          tradeCount: old.tradeCount,
          maxDrawdownPct: old.maxDrawdownPct,
        };
      });
    });
  }, [strategiesQuery.data?.data]);

  /** Si cambian valor/periodo/costes, los OK previos ya no valen → reset resultados de la tabla. */
  const matrixRunFingerprint = [
    instrumentId,
    periodPreset,
    customDateFrom,
    customDateTo,
    initialCash,
    commissionBps,
    slippageBps,
    runTimeframe,
  ].join("|");
  const matrixFingerprintRef = useRef(matrixRunFingerprint);
  useEffect(() => {
    if (matrixFingerprintRef.current === matrixRunFingerprint) return;
    matrixFingerprintRef.current = matrixRunFingerprint;
    lastBatteryFingerprintRef.current = null;
    setMatrixRows((prev) =>
      prev.map((row) => ({
        ...row,
        status: "idle",
        error: undefined,
        runId: undefined,
        totalReturnPct: undefined,
        buyHoldReturnPct: undefined,
        excessReturnPct: undefined,
        tradeCount: undefined,
        maxDrawdownPct: undefined,
      })),
    );
  }, [matrixRunFingerprint]);

  useEffect(() => {
    return () => {
      // Snapshotear batchAbortRef.current a una variable local (sugerencia de autofix) REGRESIONARÍA: el ref
      // nace como null en el primer render y solo se asigna al iniciar un batch; en unmount queremos abortar
      // el AbortController vigente, no el del montaje. Leer el ref en cleanup es deliberado, por eso se
      // desactiva react-hooks/exhaustive-deps en estas dos líneas concretas (refs no-DOM).
      batchAbortRef.current?.abort(); // eslint-disable-line react-hooks/exhaustive-deps
      // Si Lista AUTO sigue activa (keep-alive en PlatformShell), no abortar explore.
      if (useListAutoActivityStore.getState().active) return;
      exploreAbortRef.current?.abort(); // eslint-disable-line react-hooks/exhaustive-deps
    };
  }, []);

  function toggleMatrixRow(rowId: string) {
    setMatrixSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(rowId)) {
        next.delete(rowId);
      } else if (next.size < STRATEGY_MATRIX_MAX_SELECTED) {
        next.add(rowId);
      }
      return next;
    });
  }

  /** replace | add | remove — selección tipo lista Windows + cabecera. */
  function applyMatrixSelection(
    mode: "replace" | "add" | "remove",
    rowIds: string[],
  ) {
    setMatrixSelectedIds((prev) => {
      if (mode === "replace") {
        return new Set(rowIds.slice(0, STRATEGY_MATRIX_MAX_SELECTED));
      }
      const next = new Set(prev);
      if (mode === "remove") {
        for (const id of rowIds) next.delete(id);
        return next;
      }
      for (const id of rowIds) {
        if (next.size >= STRATEGY_MATRIX_MAX_SELECTED) break;
        next.add(id);
      }
      return next;
    });
  }

  /** Botón matriz: respeta filtro actual y selección. */
  async function runCoachFromMatrixUi(opts?: { forceResim?: boolean }) {
    if (opts?.forceResim) {
      lastBatteryFingerprintRef.current = null;
      setAssistantStatus("Coach: forzando re-sim del lote…");
    }
    await runCoachBattery(matrixCoachTargetIds, {
      forceResim: opts?.forceResim,
    });
  }

  const linkedTrialQuery = useQuery({
    queryKey: ["research", "by-run", detail?.id],
    queryFn: () =>
      api.getResearchTrials({
        backtestRunId: detail!.id,
        limit: 1,
        sort: "created_at",
        sortDir: "desc",
      }),
    enabled: Boolean(detail?.id),
  });
  const linkedTrial = linkedTrialQuery.data?.data?.[0];
  const freshRun =
    runMutation.data?.data?.id === detail?.id ? runMutation.data : undefined;
  const displayTrialId = freshRun?.trialId ?? linkedTrial?.id;
  const displayMetrics = freshRun?.metrics ?? linkedTrial?.isMetrics;

  const replayBarsQuery = useQuery({
    queryKey: [
      "backtest-replay-ohlcv",
      detail?.id,
      detail?.instrumentId,
      detail?.barCount,
      detail?.timeframe,
      detail?.firstDate,
      detail?.lastDate,
    ],
    queryFn: () =>
      api.getOhlcv(
        detail!.instrumentId,
        Math.min(10_000, Math.max(detail!.barCount + 200, 400)),
        detail!.timeframe ?? "1d",
      ),
    enabled: Boolean(detail?.instrumentId && detail?.id === selectedId),
  });

  useEffect(() => {
    setReplayDrawings(null);
    setDrawingLoadHint(null);
    setFocusTimestamp(null);
  }, [detail?.id]);

  function focusTrade(timestamp: string) {
    setFocusTimestamp(timestamp);
    requestAnimationFrame(() => {
      document.getElementById("backtest-replay")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  const focusedTrade = useMemo(
    () =>
      detail?.trades.find((trade) => trade.timestamp === focusTimestamp) ??
      null,
    [detail?.trades, focusTimestamp],
  );
  const replayRunBars = useMemo(() => {
    const bars = replayBarsQuery.data?.data;
    if (!bars || !detail) return [];
    return bars.filter(
      (bar) =>
        bar.timestamp >= detail.firstDate && bar.timestamp <= detail.lastDate,
    );
  }, [detail, replayBarsQuery.data?.data]);

  const drawingReplayQuery = useQuery({
    queryKey: [
      "drawing-replay",
      detail?.id,
      replayDrawings?.map((drawing) => drawing.id).join(","),
    ],
    queryFn: () =>
      api.replayDrawings({
        bars: replayRunBars,
        drawings: replayDrawings!,
      }),
    enabled: Boolean(
      detail &&
      replayDrawings &&
      replayDrawings.length > 0 &&
      replayRunBars.length >= 2,
    ),
  });

  const drawingMarkers = drawingReplayQuery.data?.data ?? [];

  const manifestSummary = useMemo(() => {
    if (!detail?.manifest) return null;
    const snap = detail.manifest.dataSnapshot;
    return {
      engine: `${detail.manifest.engine.name} v${detail.manifest.engine.version}`,
      dataVersion: detail.dataVersion ?? snap?.dataVersion,
      barCount: snap?.barCount,
      metricsHash: detail.manifest.outputs.metricsHash,
    };
  }, [detail]);

  const equityCurve = useMemo(
    () => (detail ? equityCurveFromDetail(detail) : []),
    [detail],
  );

  function setLibraryFilter(next: StrategiesListFilter) {
    setStrategiesListFilter(next);
    setLibraryFocusStrategyId(null);
    setLibraryFocusPreset(null);
    patchSearchParams((params) => {
      params.set("tab", "strategies");
      params.set("library", next);
      params.delete("strategyId");
      params.delete("preset");
    });
  }

  function startOptimizeFromDetail() {
    if (!detail) return;
    const excess =
      typeof displayMetrics?.excessReturnPct === "number"
        ? displayMetrics.excessReturnPct
        : typeof linkedTrial?.isMetrics?.excessReturnPct === "number"
          ? linkedTrial.isMetrics.excessReturnPct
          : null;
    const seed = buildOptimizeSeedFromRun({
      instrumentId: detail.instrumentId,
      symbol: detail.symbol,
      strategyType: detail.strategyType,
      strategyLabel:
        BACKTEST_STRATEGIES[detail.strategyType]?.label ??
        detail.name ??
        detail.strategyType,
      initialCash: detail.initialCash,
      timeframe: (detail.timeframe as ChartTimeframe) || runTimeframe,
      barCount: detail.barCount,
      runId: detail.id,
      excessReturnPct: excess,
      totalReturnPct: detail.totalReturnPct,
      maxDrawdownPct: detail.maxDrawdownPct,
      tradeCount: detail.tradeCount,
      trialParams: linkedTrial?.params ?? null,
    });
    openGuidedOptimize(seed);
  }

  /** Finalistas → Detalle + checklist (Camino A). Sin re-Lab ni deploy directo. */
  function openFinalistChecklist(slot: {
    strategyDefinitionId: string;
    runId?: string | null;
    label?: string;
  }) {
    setSavedStrategyId(slot.strategyDefinitionId);
    setRunSource("saved");
    if (instrumentId && effectiveAccountId) {
      setAdoption({
        instrumentId,
        accountId: effectiveAccountId,
        state: "adoptada",
        strategyDefinitionId: slot.strategyDefinitionId,
        strategyLabel: slot.label ?? null,
        timeframe: runTimeframe,
      });
    }
    if (slot.runId) {
      selectRun(slot.runId, {
        tab: "run",
        openAnalysis: true,
        focus: "detail",
      });
      setAssistantStatus(PAPER_PATH_LAB.finalistsHint);
      return;
    }
    setPreferOpenAnalysis(false);
    setResultFocus("detail");
    setAssistantStatus(
      "Este Finalista no tiene run guardado. Usa Usar → Probar (genera resultado) y luego Checklist.",
    );
  }

  const proposeFinalistMutation = useMutation({
    mutationFn: async (slot: {
      strategyDefinitionId: string;
      label: string;
    }) => {
      if (!instrumentId) throw new Error("Elige un valor");
      if (!effectiveAccountId)
        throw new Error("Selecciona una cuenta activa (perfil FA)");
      const symbol =
        instrumentLabels[instrumentId]?.symbol ??
        instruments.find((i) => i.id === instrumentId)?.symbol ??
        "Valor";
      return proposeFinalistSupervised({
        instrumentId,
        symbol,
        accountId: effectiveAccountId,
        strategyDefinitionId: slot.strategyDefinitionId,
        strategyLabel: slot.label,
      });
    },
    onSuccess: (payload, slot) => {
      if (instrumentId && effectiveAccountId) {
        setAdoption({
          instrumentId,
          accountId: effectiveAccountId,
          state: "propuesta",
          strategyDefinitionId: slot.strategyDefinitionId,
          strategyLabel: slot.label,
          timeframe: runTimeframe,
        });
      }
      const id = enqueueSupervised(payload, {
        symbol: payload.symbol ?? undefined,
        origin: "finalists",
      });
      setActiveSupervised(id);
      const msg = `${PAPER_PATH_SUPERVISED.shortTitle}: ${slot.label} → ${payload.action} · revisa Supervisado F3`;
      setAssistantStatus(msg);
      pushToast(msg);
      openHelpAiPlatform({ panel: "supervised-f3" });
    },
    onError: (err: Error) => {
      setAssistantStatus(
        err.message || "No se pudo proponer al Supervisado F3",
      );
      pushToast(err.message || "Error al proponer Finalista");
    },
  });

  function proposeFinalistSupervisedSlot(slot: {
    strategyDefinitionId: string;
    label: string;
  }) {
    proposeFinalistMutation.mutate(slot);
  }

  useBacktestUrlSync({
    onBacktestsRoute,
    searchParams,
    setResultFocus,
    setTab,
    patchSearchParams,
    diaDVerifySession,
    setStrategiesListFilter,
    setLibraryFocusStrategyId,
    setLibraryFocusPreset,
    setMineFilters,
    setPreferOpenAnalysis,
    runIdFromUrl,
    listAutoRef,
    instrumentId,
    setInstrumentId,
    listsQuery,
    setUniverseMode,
    setListId,
    setSearchParams,
    setSelectedId,
    detail,
  });

  /**
   * Lista AUTO (campaña / supervisión / frescura) — Track B B7.
   * Se reconstruye en cada render (igual que las function locales originales).
   * Antes de orchestration (mismo patrón B6: factory → consumidores).
   */
  const {
    startListAutoCampaign,
    symbolForInstrument,
    queueListAutoTicker,
    persistListAutoPauseNow,
    clearPersistedListAutoPause,
    pauseListAuto,
    resumeListAuto,
    stopListAuto,
    forceListAutoRescanRemaining,
    abortListAutoCampaign,
    currentFinalistsInputFingerprint,
    rememberListAutoFreshness,
  } = createBacktestListAutoController({
    queryClient,
    universeMode,
    listId,
    listDetail,
    instrumentLabels,
    instruments,
    listAutoSkipWithFinalists,
    assistantPrefs,
    runTimeframe,
    listAutoBoard,
    matrixRowsForUi,
    periodPreset,
    customDateFrom,
    customDateTo,
    diaD,
    initialCash,
    commissionBps,
    slippageBps,
    coachProfilePolicy,
    listAutoRef,
    listAutoStartOverridesRef,
    listAutoExcludedIdsRef,
    listAutoPendingStartRef,
    listAutoFreshnessMemoryRef,
    listAutoSettleLockRef,
    assistantChainRef,
    exploreAbortRef,
    setAssistantStatus,
    setListAutoBoard,
    setResultFocus,
    setListAutoUi,
    setFullCycleActive,
    setAssistantProgress,
    setAwaitingAck,
    setAwaitingAckStage,
    setLabImprovedThisCycle,
    setSemifinalShortcutArmed,
    setLabOpenedThisRun,
    setListAutoStartToken,
    setExploreRunning,
    selectInstrument,
  });

  /**
   * Lab navegación (openGuidedOptimize / openLabBoard) — Track B B9.
   * Antes de orchestration: openGuidedOptimize se pasa a createBacktestOrchestration.
   */
  const { openGuidedOptimize, openLabBoard } =
    createBacktestLabNavigationHandlers({
      setOptimizeSeed,
      setInstrumentId,
      setLabZones,
      setLabOpenedThisRun,
      setTab,
      setResultFocus,
    });

  /**
   * Acciones de ciclo/embudo extraídas a `lib/backtest-orchestration.ts`.
   * Se reconstruyen en cada render (igual que las function locales originales):
   * los closures capturan SIEMPRE el estado/ref/helper más recientes.
   */
  const {
    runListBatch,
    runCoachBattery,
    startOptimizeFromExplore,
    settleFullCycle,
  } = createBacktestOrchestration({
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
  });

  /**
   * Lab Coach handlers (reanalyze / explore / semifinal) — Track B B9.
   * Después de orchestration: consume runCoachBattery y settleFullCycle.
   */
  const { reanalyzeLabWithCoach, runExploreValue, optimizeSemifinalFromCoach } =
    createBacktestLabCoachHandlers({
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
    });

  /**
   * Asistente (Play / Universo→Lab / ciclo) — Track B B8.
   * Se reconstruye en cada render (igual que las function locales originales).
   * Después de orchestration (necesita settleFullCycle, startListAutoCampaign, abortListAutoCampaign).
   */
  const {
    playAssistantSequence,
    handleDiaDChange,
    updateAssistantPrefs,
    executeAssistantStep,
    goAssistantStep,
  } = createBacktestAssistantController({
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
  });

  useBacktestAssistantEffects({
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
  });

  useBacktestListAutoEffects({
    listAutoBoard,
    listAutoUi,
    assistantStatus,
    listId,
    listDetail,
    instrumentLabels,
    universeMode,
    instrumentId,
    freshnessContextReady,
    instruments,
    runTimeframe,
    coachProfilePolicy,
    assistantPrefs,
    listAutoStartToken,
    listAutoRef,
    supervisionStartPendingRef,
    listAutoStartOverridesRef,
    listAutoExcludedIdsRef,
    listAutoPauseRestoredRef,
    listAutoPendingStartRef,
    listAutoFreshnessMemoryRef,
    setUniverseMode,
    setListId,
    setAssistantPrefs,
    setAssistantStatus,
    setResultFocus,
    setListAutoStartToken,
    setListAutoBoard,
    setListAutoUi,
    setTab,
    pauseListAuto,
    resumeListAuto,
    persistListAutoPauseNow,
    startListAutoCampaign,
    symbolForInstrument,
    currentFinalistsInputFingerprint,
    rememberListAutoFreshness,
    queryClient,
    executeAssistantStep,
    settleFullCycle,
  });

  // Redirección legacy ejecutada tras todos los hooks para respetar la Regla de
  // Hooks (el componente no debe variar el número de hooks entre renders por un
  // early return). Solo en la ruta real, no en keep-alive Lista AUTO fuera de /backtests.
  if (onBacktestsRoute && tabParam === "screeners") {
    return <Navigate to="/screeners" replace />;
  }

  const runTabVm: BacktestPageViewModel = {
    applyChartDraft,
    applyMatrixSelection,
    assistantPrefs,
    assistantProgress,
    assistantStepComplete,
    awaitingAck,
    batchAbortRef,
    batchError,
    batchProgress,
    batchRows,
    batchRunning,
    batchSort,
    coachPass,
    coachProfilePolicy,
    coachRunProgress,
    commissionBps,
    currentFinalistsInputFingerprint,
    customDateFrom,
    customDateTo,
    deployPaperMutation,
    detail,
    detailFinalistBadge,
    detailQuery,
    diaD,
    diaDVerifyActive,
    displayMetrics,
    displayTrialId,
    drawingMarkers,
    equityCurve,
    exploreAbortRef,
    exploreError,
    exploreOkCount,
    exploreProgress,
    exploreRows,
    exploreRunning,
    exploreSort,
    focusTimestamp,
    focusTrade,
    focusedTrade,
    forceListAutoRescanRemaining,
    fullCycleActive,
    hasExistingTopForSave,
    initialCash,
    instrumentId,
    instrumentLabels,
    instrumentSymbol,
    instrumentTop,
    instruments,
    instrumentsQuery,
    isWide,
    labImprovedThisCycle,
    labOpenedThisRun,
    labZones,
    linkedTrial,
    listAutoBoard,
    listAutoRef,
    listAutoSkipWithFinalists,
    listAutoUi,
    listDetail,
    listId,
    listMembersWithStatus,
    listQuotesQuery,
    listTopsQuery,
    lists,
    listsQuery,
    manifestSummary,
    matrixCoachTargetIds,
    matrixFilter,
    matrixRowsForUi,
    matrixSelectedIds,
    openFinalistChecklist,
    openInstrumentInValor,
    openLibrary,
    optimizeSeed,
    optimizeSemifinalFromCoach,
    patchSearchParams,
    pauseListAuto,
    periodPreset,
    preferOpenAnalysis,
    proposeFinalistMutation,
    proposeFinalistSupervisedSlot,
    pushToast,
    queryClient,
    reanalyzeLabWithCoach,
    replayBarsQuery,
    resultFocus,
    resumeListAuto,
    runCoachFromMatrixUi,
    runListBatch,
    runMutation,
    runSource,
    runTimeframe,
    saveChartStrategyMutation,
    savedStrategyId,
    selectInstrument,
    selectRun,
    selectedId,
    semifinalShortcutArmed,
    setAssistantStatus,
    setAwaitingAck,
    setAwaitingAckStage,
    setBatchSort,
    setCoachGate,
    setCoachPass,
    setCommissionBps,
    setCustomDateFrom,
    setCustomDateTo,
    setExploreSort,
    setFocusTimestamp,
    setInitialCash,
    setLabImprovedThisCycle,
    setLabOpenedThisRun,
    setLabZones,
    setListAutoSkipWithFinalists,
    setListId,
    setMatrixFilter,
    setMatrixSelectedIds,
    setOptimizeSeed,
    setPeriodPreset,
    setPreferOpenAnalysis,
    setResultFocus,
    setRunSource,
    setRunTimeframe,
    setSavedStrategyId,
    setSlippageBps,
    setStrategiesListFilter,
    setStrategyType,
    setUniverseMode,
    setZonePrefs,
    settleFullCycle,
    slippageBps,
    startOptimizeFromDetail,
    startOptimizeFromExplore,
    stopListAuto,
    strategies,
    strategyType,
    toggleMatrixRow,
    topStrategyIds,
    universeMode,
    updateAssistantPrefs,
    zonePrefs,
  };

  const jobsTabVm: BacktestPageJobsViewModel = {
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
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {diaDVerifyFullBleed ? <DiaDVerifyHost fullBleed /> : null}
      {!diaDVerifyFullBleed ? (
        <>
          <div className="flex shrink-0 flex-wrap items-end justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-end gap-2.5 sm:gap-3">
              <UniverseChip force="lab" className="mb-1" />
              <h2
                className="text-2xl font-semibold tracking-tight"
                title="Prueba una estrategia sobre un valor y un periodo. El resto de pestañas es secundario. En Probar, arrastra los separadores entre paneles para adaptar el espacio; se guarda en este dispositivo."
              >
                Backtesting
              </h2>
              <BacktestDiaDOriginControl
                diaD={diaD}
                onDiaDChange={handleDiaDChange}
                className="mb-0.5"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <BacktestHubTabsBar
                tab={tab}
                onTab={(next) => setTab(next)}
                onOpenLibrary={() =>
                  openLibrary({ library: strategiesListFilter })
                }
              />
              <BacktestZoneSettingsButton
                onClick={() => setZoneSettingsOpen(true)}
              />
            </div>
          </div>

          <BacktestAssistantRail
            activeStep={assistantStep}
            prefs={assistantPrefs}
            onPrefsChange={updateAssistantPrefs}
            progress={assistantProgress}
            coachPass={coachPass}
            fullCycleActive={fullCycleActive || Boolean(listAutoUi)}
            awaitingAck={awaitingAck}
            awaitingAckStage={awaitingAckStage}
            flashMessage={assistantStatus}
            onStepClick={goAssistantStep}
            onPlay={playAssistantSequence}
            profileLabel={coachProfileRailLabel}
            profileMissing={!coachProfilePolicy.profileId}
            playBusy={
              (fullCycleActive ||
                Boolean(listAutoUi) ||
                exploreRunning ||
                semifinalEnqueuePending) &&
              !listAutoBoard?.paused
            }
            playDisabled={
              Boolean(listAutoUi) ||
              Boolean(
                listAutoBoard && !listAutoBoard.done && !listAutoBoard.aborted,
              ) ||
              exploreRunning ||
              semifinalEnqueuePending ||
              !(
                Boolean(instrumentId) ||
                (universeMode === "list" &&
                  assistantPrefs.fullCycleOnPlay &&
                  Boolean(listId) &&
                  (listDetail?.instrumentIds.length ?? 0) > 0)
              )
            }
            playTitle={listAutoPlayTitle({
              fullCycleOnPlay: assistantPrefs.fullCycleOnPlay,
              listMode: universeMode === "list",
            })}
            listAutoControls={
              listAutoBoard && !listAutoBoard.done && !listAutoBoard.aborted
                ? {
                    visible: true,
                    paused: listAutoBoard.paused,
                    canPause: !listAutoBoard.paused,
                    canResume:
                      listAutoBoard.paused &&
                      !listAutoBoard.rows.some((r) => r.phase === "running"),
                    canStop: true,
                    onPause: pauseListAuto,
                    onResume: resumeListAuto,
                    onStop: stopListAuto,
                  }
                : null
            }
            onReset={() => {
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
              setListAutoBoard(null);
              setResultFocus("detail");
              setStrategiesListFilter("all");
              setTab("run");
              setAssistantStatus(
                instrumentId
                  ? "Listo. Pulsa Play para Universo."
                  : "Elige un valor y pulsa Play.",
              );
            }}
          />

          <BacktestZoneSettingsDialog
            open={zoneSettingsOpen}
            onOpenChange={setZoneSettingsOpen}
            onSaved={(prefs) => {
              setZonePrefs(prefs);
              void pruneHistory(prefs.historyMaxKept);
            }}
          />

          {tab === "run" && <BacktestsPageRunTab vm={runTabVm} />}

          {tab === "jobs" && <BacktestsPageJobsTab vm={jobsTabVm} />}

          {tab === "strategies" && (
            <BacktestLibraryTab
              strategyOptions={STRATEGY_OPTIONS}
              strategies={strategies}
              filteredStrategies={filteredStrategies}
              strategiesListFilter={strategiesListFilter}
              onStrategiesListFilterChange={setLibraryFilter}
              mineFilters={mineFilters}
              onMineFiltersChange={(next) => {
                setMineFilters(next);
                patchSearchParams(
                  (params) => {
                    params.set("tab", "strategies");
                    params.set("library", strategiesListFilter);
                    if (next.query.trim()) params.set("q", next.query.trim());
                    else params.delete("q");
                  },
                  { replace: true },
                );
              }}
              mineFilterTimeframes={mineFilterTimeframes}
              mineFilterOrigins={mineFilterOrigins}
              mineFilterInstruments={mineFilterInstruments}
              instrumentId={instrumentId}
              instrumentSymbol={instrumentSymbol}
              runTimeframe={runTimeframe}
              instrumentTop={instrumentTop}
              topStrategyIds={topStrategyIds}
              instrumentSymbolById={instrumentSymbolById}
              focusStrategyId={libraryFocusStrategyId}
              focusPresetKey={libraryFocusPreset}
              cloneOpen={cloneOpen}
              onCloneOpenChange={setCloneOpen}
              newStrategyName={newStrategyName}
              onNewStrategyNameChange={setNewStrategyName}
              newStrategyPreset={newStrategyPreset}
              onNewStrategyPresetChange={setNewStrategyPreset}
              createPending={createStrategyMutation.isPending}
              createError={createStrategyMutation.error}
              onCreate={() => createStrategyMutation.mutate()}
              onUsePreset={(key) => {
                setStrategyType(key);
                setRunSource("preset");
                setTab("run");
              }}
              onUseSaved={(strategyId) => {
                setSavedStrategyId(strategyId);
                setRunSource("saved");
                setTab("run");
                setResultFocus("detail");
                setAssistantStatus(PAPER_PATH_LAB.libraryHint);
              }}
              onOpenFinalistChecklist={(slot) => {
                setTab("run");
                openFinalistChecklist(slot);
              }}
              onProposeFinalistSupervised={(slot) => {
                setTab("run");
                proposeFinalistSupervisedSlot(slot);
              }}
              proposeFinalistPendingStrategyId={
                proposeFinalistMutation.isPending
                  ? (proposeFinalistMutation.variables?.strategyDefinitionId ??
                    null)
                  : null
              }
              onDeleted={(id) => {
                if (savedStrategyId === id) setSavedStrategyId("");
                if (libraryFocusStrategyId === id) {
                  setLibraryFocusStrategyId(null);
                  patchSearchParams((params) => {
                    params.delete("strategyId");
                  });
                }
              }}
              onGoToCoach={() => {
                setTab("run");
                setResultFocus("coach");
              }}
            />
          )}

          {tab === "history" && (
            <BacktestHistoryTab
              runs={runs}
              historyMaxKept={zonePrefs.historyMaxKept}
              selectedId={selectedId}
              onOpenSettings={() => setZoneSettingsOpen(true)}
              onSelectRun={(runId) => selectRun(runId, { tab: "run" })}
              onGoToRun={() => setTab("run")}
            />
          )}
        </>
      ) : null}
    </div>
  );
}
