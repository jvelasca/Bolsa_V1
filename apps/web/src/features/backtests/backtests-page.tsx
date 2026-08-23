/**
 * Hub Backtesting (`/backtests`) — orquestación UI del embudo.
 *
 * Ciclo completo / Lista AUTO / Finalistas Checklist+Proponer / Lab handoff.
 * Política motor: `backtest-assistant-full-cycle.ts`, `backtest-list-auto.ts`.
 * Documentación: `docs/engineering/session-handoff-2026-07-30.md` ·
 * `docs/engineering/list-auto-ops-2026-07-29.md`.
 */

import {
  parseTab,
  isAnalysisResultFocus,
} from "@/features/backtests/backtest-hub-nav";
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
  STRATEGY_PRESET_CATEGORY_LABELS,
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
import {
  buildOptimizeBeforeAfter,
  type OptimizeBeforeAfterSnapshot,
} from "@/features/backtests/backtest-optimize-delta";
import { BacktestOptimizeCompareCard } from "@/features/backtests/backtest-optimize-compare-card";
import { BacktestResultFocusLab } from "@/features/backtests/backtest-result-focus-lab";
import { BacktestResultFocusCoach } from "@/features/backtests/backtest-result-focus-coach";
import type {
  LabBoardZone,
  LabReanalyzeRequest,
} from "@/features/backtests/backtest-lab-board-types";
import { padLabZones } from "@/features/backtests/backtest-lab-board-types";
import {
  finalistMatrixRowIds,
  mergeUniverseTargetIds,
} from "@/features/backtests/backtest-coach-lote";
import { BacktestOptimizePanel } from "@/features/backtests/backtest-optimize-panel";
import {
  buildOptimizeSeedFromExploreRow,
  buildOptimizeSeedFromRun,
  isOptimizableStrategy,
  type OptimizeSeed,
} from "@/features/backtests/backtest-optimize-seed";
import { BacktestAssistantRail } from "@/features/backtests/backtest-assistant-rail";
import { InstrumentStrategyTopPanel } from "@/features/backtests/instrument-strategy-top-panel";
import { FundamentalCardPanel } from "@/features/instruments/fundamental-card-panel";
import { AiInfoButton } from "@/features/ai/ai-info-button";
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
  listAutoUniverseHint,
  listModeWizardTitle,
  type ListAutoCampaign,
} from "@/features/backtests/backtest-list-auto";
import {
  instrumentTopIsDurable,
  universeEmptyStatus,
} from "@/features/backtests/backtest-assistant-full-cycle";
import {
  isFinalistsSavedStatusMessage,
  isSemifinalShortcutStatusMessage,
} from "@/features/backtests/assistant-cycle-orchestrator";
import { loadBacktestRunContext } from "@/features/backtests/backtest-run-context";
import type { ListAutoBoardState } from "@/features/backtests/backtest-list-auto-board";
import { BacktestListAutoBoardPanel } from "@/features/backtests/backtest-list-auto-board-panel";
import { type AssistantStepId } from "@/features/backtests/backtest-assistant-steps";
import { buildOptimizeRequestsFromSeed } from "@/features/backtests/backtest-optimize-from-seed";
import { BacktestHubLayout } from "@/features/backtests/backtest-hub-layout";
import {
  equityCurveFromDetail,
  exportBacktestJson,
  exportEquityCsv,
  exportTradesCsv,
} from "@/features/backtests/backtest-export";
import { BacktestUniversePicker } from "@/features/backtests/backtest-universe-picker";
import { BacktestStrategyMatrixPanel } from "@/features/backtests/backtest-strategy-matrix-panel";
import { BacktestLibraryTab } from "@/features/backtests/backtest-library-tab";
import { parseLibraryFilterParam } from "@/features/backtests/library-nav";
import { BacktestHistoryTab } from "@/features/backtests/backtest-history-tab";
import {
  STRATEGY_MATRIX_MAX_SELECTED,
  buildStrategyMatrixRows,
  exploreBatteryRowIds,
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
  PAPER_PATH_MONITOR,
  PAPER_PATH_SUPERVISED,
} from "@/features/settings/paper-paths-copy";
import { proposeFinalistSupervised } from "@/features/backtests/finalist-propose-supervised";
import { isOpenAnalysisQuery } from "@/features/backtests/strategy-monitor";
import { StrategyMonitorPanel } from "@/features/backtests/strategy-monitor-panel";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useAlertsStore } from "@/stores/alerts-store";
import {
  openHelpAiPlatform,
  useSupervisedF3QueueStore,
} from "@/stores/supervised-f3-queue-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/lib/use-media-query";
import {
  DEFAULT_PERIOD_PRESET,
  PERIOD_PRESET_OPTIONS,
  effectiveDiaD,
  isDiaDInPast,
  todayIsoDate,
  type PeriodPreset,
} from "@/features/backtests/backtest-period";
import { BacktestDiaDOriginControl } from "@/features/backtests/backtest-dia-d-origin-control";
import { formatDiaDDisplay } from "@/features/backtests/dia-d-favorites";
import { DiaDVerifyHost } from "@/features/backtests/dia-d-verify-host";
import { BacktestResultFundamental } from "@/features/backtests/backtest-result-fundamental";
import { BacktestResultRanking } from "@/features/backtests/backtest-result-ranking";
import { BacktestWizardMassCompare } from "@/features/backtests/backtest-wizard-mass-compare";
import { BacktestWizardAdvancedOptions } from "@/features/backtests/backtest-wizard-advanced-options";
import { BacktestWizardListAuto } from "@/features/backtests/backtest-wizard-list-auto";
import { BacktestWizardProbeList } from "@/features/backtests/backtest-wizard-probe-list";
import { BacktestResultDetail } from "@/features/backtests/backtest-result-detail";
import { BacktestResultFocusFinalists } from "@/features/backtests/backtest-result-focus-finalists";
import { UniverseChip } from "@/features/platform/universe-chip";
import { setAdoption } from "@/features/platform/strategy-adoption";
import { useDiaDTradingSessionStore } from "@/stores/dia-d-trading-session-store";
import { createBacktestOrchestration } from "@/features/backtests/lib/backtest-orchestration";
import { createBacktestPageNavigation } from "@/features/backtests/lib/backtest-page-navigation";

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

          {tab === "run" && (
            <>
              <BacktestHubLayout
                isWide={isWide}
                className="min-h-0 flex-1"
                wizard={
                  <Card className="border-0 shadow-none">
                    <CardHeader className="space-y-0 px-3 pb-1.5 pt-3">
                      <CardTitle
                        className="text-sm font-semibold"
                        title={
                          universeMode === "list"
                            ? listAutoUniverseHint()
                            : "Elige un valor. El lote del Asistente (Play) usa genéricas ∪ Finalistas; la matriz es opcional. Periodo, capital y costes en Opciones avanzadas."
                        }
                      >
                        {universeMode === "list"
                          ? listModeWizardTitle(assistantPrefs.fullCycleOnPlay)
                          : "Probar estrategia"}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 px-3 pb-3 text-xs">
                      <BacktestUniversePicker
                        mode={universeMode}
                        onModeChange={setUniverseMode}
                        instruments={instruments}
                        instrumentId={instrumentId}
                        onInstrumentIdChange={selectInstrument}
                        lists={lists}
                        listId={listId}
                        onListIdChange={setListId}
                        listInstrumentCount={listDetail?.instrumentIds.length}
                        listsLoading={listsQuery.isLoading}
                        listMembers={listMembersWithStatus}
                        listMembersLoading={listQuotesQuery.isLoading}
                        listStatusLoading={
                          listTopsQuery.isFetching && !listTopsQuery.data
                        }
                        onOpenListMember={openInstrumentInValor}
                      />

                      <div
                        className={cn(
                          "rounded-md border px-2.5 py-2 text-[10px] leading-snug",
                          isDiaDInPast(diaD)
                            ? "border-red-600 bg-red-600 text-white shadow-sm ring-1 ring-red-700/40"
                            : "border-border/60 bg-muted/15 text-muted-foreground",
                        )}
                        role={isDiaDInPast(diaD) ? "status" : undefined}
                        data-testid={
                          isDiaDInPast(diaD) ? "dia-d-mode-banner" : undefined
                        }
                      >
                        {isDiaDInPast(diaD) ? (
                          <p>
                            <strong className="font-bold tracking-wide">
                              Origen DÍA D{" "}
                              {formatDiaDDisplay(effectiveDiaD(diaD))}
                            </strong>
                            {" — "}
                            embudo con datos ≤ esa fecha (cámbialo junto al
                            título). Tras Play → Finalistas #1 →{" "}
                            <strong className="font-semibold">
                              Verificar D→hoy
                            </strong>
                            .
                          </p>
                        ) : (
                          <p>
                            Origen{" "}
                            <strong className="text-foreground/80">
                              Hoy {formatDiaDDisplay(todayIsoDate())}
                            </strong>
                            . Para simular «como si hoy fuera el pasado», abre
                            el selector junto a{" "}
                            <strong className="text-foreground/80">
                              Backtesting
                            </strong>{" "}
                            y elige DÍA D (guarda fechas con ★).
                          </p>
                        )}
                      </div>

                      <BacktestWizardAdvancedOptions
                        periodPreset={periodPreset}
                        onPeriodPresetChange={setPeriodPreset}
                        customDateFrom={customDateFrom}
                        onCustomDateFromChange={setCustomDateFrom}
                        customDateTo={customDateTo}
                        onCustomDateToChange={setCustomDateTo}
                        initialCash={initialCash}
                        onInitialCashChange={setInitialCash}
                        runTimeframe={runTimeframe}
                        onRunTimeframeChange={setRunTimeframe}
                        commissionBps={commissionBps}
                        onCommissionBpsChange={setCommissionBps}
                        slippageBps={slippageBps}
                        onSlippageBpsChange={setSlippageBps}
                        diaD={diaD}
                        universeMode={universeMode}
                        onApplyChartDraft={applyChartDraft}
                        onSaveStrategy={(draft, name) =>
                          saveChartStrategyMutation.mutate({ draft, name })
                        }
                        isSaving={saveChartStrategyMutation.isPending}
                      />

                      {universeMode === "list" ? (
                        <>
                          <BacktestWizardListAuto
                            assistantPrefs={assistantPrefs}
                            onPrefsChange={updateAssistantPrefs}
                            listId={listId}
                            instrumentCount={
                              listDetail?.instrumentIds.length ?? 0
                            }
                            skipWithFinalists={listAutoSkipWithFinalists}
                            onSkipWithFinalistsChange={
                              setListAutoSkipWithFinalists
                            }
                            board={listAutoBoard}
                            ui={listAutoUi}
                            selectedInstrumentId={instrumentId || null}
                            onOpenInstrument={openInstrumentInValor}
                            onPause={pauseListAuto}
                            onResume={resumeListAuto}
                            onStop={stopListAuto}
                            onForceRescanRemaining={
                              forceListAutoRescanRemaining
                            }
                          />

                          <BacktestWizardProbeList
                            runSource={runSource}
                            onRunSourceChange={setRunSource}
                            strategyType={strategyType}
                            onStrategyTypeChange={setStrategyType}
                            strategies={strategies}
                            savedStrategyId={savedStrategyId}
                            onSavedStrategyIdChange={setSavedStrategyId}
                            batchRunning={batchRunning}
                            batchProgress={batchProgress}
                            onAbortBatch={() => batchAbortRef.current?.abort()}
                            onRunListBatch={() => void runListBatch()}
                            exploreRunning={exploreRunning}
                            listAutoRunning={Boolean(listAutoUi)}
                            periodPreset={periodPreset}
                            customDateFrom={customDateFrom}
                            customDateTo={customDateTo}
                            listId={listId}
                            listDetail={listDetail}
                          />

                          <BacktestWizardMassCompare
                            listDetail={listDetail}
                            labels={instrumentLabels}
                            initialCash={initialCash}
                            commissionBps={commissionBps}
                            slippageBps={slippageBps}
                            timeframe={runTimeframe}
                            periodPreset={periodPreset}
                            customDateFrom={customDateFrom}
                            customDateTo={customDateTo}
                            diaD={diaD}
                          />
                        </>
                      ) : (
                        <BacktestStrategyMatrixPanel
                          rows={matrixRowsForUi}
                          filter={matrixFilter}
                          selectedIds={matrixSelectedIds}
                          listHeightPx={zonePrefs.strategyMatrix.listHeightPx}
                          onListHeightPxChange={(next) => {
                            patchStrategyMatrixTablePrefs({
                              listHeightPx: next,
                            });
                            setZonePrefs(loadBacktestZonePrefs());
                          }}
                          running={exploreRunning}
                          progress={coachRunProgress}
                          finalistsFilterLabel={
                            instrumentSymbol
                              ? `Finalistas · ${instrumentSymbol}`
                              : "Finalistas"
                          }
                          finalistsFilterDisabled={
                            !instrumentId || !instrumentTop?.slots?.length
                          }
                          disabled={
                            !instrumentId ||
                            runMutation.isPending ||
                            batchRunning ||
                            exploreRunning ||
                            (periodPreset === "custom" &&
                              (!customDateFrom || !customDateTo))
                          }
                          onFilterChange={(next) => {
                            setMatrixFilter(next);
                            patchStrategyMatrixTablePrefs({ filter: next });
                          }}
                          onToggle={toggleMatrixRow}
                          onApplySelection={applyMatrixSelection}
                          onClearSelection={() =>
                            setMatrixSelectedIds(new Set())
                          }
                          onRunCoach={(opts) => void runCoachFromMatrixUi(opts)}
                          coachCount={matrixCoachTargetIds.length}
                          coachDisabled={
                            !instrumentId ||
                            matrixCoachTargetIds.length === 0 ||
                            runMutation.isPending ||
                            batchRunning ||
                            exploreRunning ||
                            (periodPreset === "custom" &&
                              (!customDateFrom || !customDateTo))
                          }
                          onStop={() => exploreAbortRef.current?.abort()}
                          onOpenDetail={(runId) => {
                            selectRun(runId, { tab: "run" });
                            setResultFocus("detail");
                          }}
                          onGoToStrategies={() =>
                            openLibrary({ library: "all" })
                          }
                          onOpenInLibrary={(row) => {
                            if (
                              row.kind === "saved" &&
                              row.strategyDefinitionId
                            ) {
                              openLibrary({
                                library: "mine",
                                strategyId: row.strategyDefinitionId,
                              });
                              return;
                            }
                            if (row.presetKey) {
                              openLibrary({
                                library: "generics",
                                preset: row.presetKey,
                              });
                            }
                          }}
                          onDeleteSavedStrategy={(row) => {
                            if (
                              row.kind !== "saved" ||
                              !row.strategyDefinitionId
                            )
                              return;
                            const name = row.label;
                            if (
                              !window.confirm(
                                `¿Eliminar «${name}» de Mis estrategias? Esta acción no se puede deshacer.`,
                              )
                            ) {
                              return;
                            }
                            void api
                              .deleteStrategy(row.strategyDefinitionId)
                              .then(
                                () => {
                                  void queryClient.invalidateQueries({
                                    queryKey: ["strategies"],
                                  });
                                  void queryClient.invalidateQueries({
                                    queryKey: ["instrument-strategy-top"],
                                  });
                                  if (
                                    savedStrategyId === row.strategyDefinitionId
                                  ) {
                                    setSavedStrategyId("");
                                  }
                                  setMatrixSelectedIds((prev) => {
                                    const next = new Set(prev);
                                    next.delete(row.rowId);
                                    return next;
                                  });
                                  pushToast(`Eliminada «${name}»`);
                                },
                                (err: unknown) => {
                                  pushToast(
                                    err instanceof Error
                                      ? err.message
                                      : "No se pudo eliminar la estrategia",
                                  );
                                },
                              );
                          }}
                        />
                      )}

                      {universeMode === "single" && instrumentId ? (
                        <>
                          <FundamentalCardPanel
                            instrumentId={instrumentId}
                            compact
                            className="mb-2"
                            asOf={
                              isDiaDInPast(diaD) ? effectiveDiaD(diaD) : null
                            }
                          />
                          <InstrumentStrategyTopPanel
                            instrumentId={instrumentId}
                            symbol={instrumentSymbol}
                            timeframe={runTimeframe}
                            top={instrumentTop}
                            compact
                            asOfDiaD={diaD}
                            activeProfileId={coachProfilePolicy.profileId}
                            onUseStrategy={(strategyId, slot) => {
                              const rowId = `saved:${strategyId}`;
                              setMatrixFilter("finalists");
                              patchStrategyMatrixTablePrefs({
                                filter: "finalists",
                              });
                              setMatrixSelectedIds(new Set([rowId]));
                              setSavedStrategyId(strategyId);
                              setRunSource("saved");
                              if (slot?.runId) {
                                openFinalistChecklist(slot);
                              }
                            }}
                            onOpenChecklist={(slot) =>
                              openFinalistChecklist(slot)
                            }
                            onProposeSupervised={(slot) =>
                              proposeFinalistSupervisedSlot(slot)
                            }
                            proposePendingStrategyId={
                              proposeFinalistMutation.isPending
                                ? (proposeFinalistMutation.variables
                                    ?.strategyDefinitionId ?? null)
                                : null
                            }
                          />
                        </>
                      ) : null}

                      {batchError && (
                        <p className="text-sm text-destructive">{batchError}</p>
                      )}
                      {exploreError && (
                        <p className="text-sm text-destructive">
                          {exploreError}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                }
                result={
                  <Card
                    id="backtest-result"
                    className="flex h-full min-h-0 flex-col border-0 shadow-none scroll-mt-4"
                  >
                    <CardHeader className="shrink-0 space-y-0 pb-2 pt-3">
                      <div
                        className="flex flex-wrap gap-1"
                        role="tablist"
                        aria-label="Vista del resultado"
                      >
                        {(
                          [
                            {
                              id: "detail" as const,
                              label: "Análisis técnico",
                              done: Boolean(selectedId || detail),
                              disabled: false,
                              title:
                                "Gráfico, replay, equity y operaciones de la prueba (sin tarjeta FA)",
                            },
                            {
                              id: "fundamental" as const,
                              label: "Análisis fundamental",
                              done: Boolean(instrumentId),
                              disabled: !instrumentId,
                              title:
                                "Tarjeta Valor: Score_FUND, ratios, Composite, filings y copiloto",
                            },
                            {
                              id: "coach" as const,
                              label:
                                coachPass === "post_lab"
                                  ? "Coach · Revalidar"
                                  : "Coach",
                              done:
                                assistantStepComplete.universe ||
                                exploreRows.length > 0 ||
                                coachPass === "post_lab",
                              disabled: false,
                              title:
                                coachPass === "post_lab"
                                  ? "4 · Revalidar (Coach²): tras Lab, re-evalúa Mejor(es) antes de Finalistas"
                                  : exploreRows.length === 0
                                    ? "2 · Coach: aún sin lote — Play → Probar"
                                    : "2 · Coach: estrellas ★ y dual-audit del lote",
                            },
                            {
                              id: "lab" as const,
                              label: "Lab",
                              done:
                                assistantStepComplete.lab ||
                                assistantStepComplete.semifinal,
                              disabled: !instrumentId,
                              title:
                                "3 · Lab: mejora por IA de las 3 mejores (Mejor ≥ ancla OOS)",
                            },
                            {
                              id: "finalists" as const,
                              label: "Finalistas",
                              done:
                                assistantProgress.finalistsSaved ||
                                topStrategyIds.size > 0,
                              disabled: !instrumentId,
                              title: assistantProgress.finalistsSkipped
                                ? "5 · Finalistas: ciclo cerró sin guardar TOP (revisa Revalidar / ACK)"
                                : "5 · Finalistas: TOP del valor en BD",
                            },
                          ] as const
                        ).map((t) => (
                          <Button
                            key={t.id}
                            type="button"
                            size="sm"
                            role="tab"
                            aria-selected={
                              resultFocus === t.id ||
                              (t.id === "detail" && resultFocus === "ranking")
                            }
                            variant={
                              resultFocus === t.id ||
                              (t.id === "detail" && resultFocus === "ranking")
                                ? "default"
                                : "outline"
                            }
                            disabled={t.disabled}
                            title={t.title}
                            className={cn(
                              "h-7 text-[11px]",
                              t.done &&
                                resultFocus !== t.id &&
                                !(
                                  t.id === "detail" && resultFocus === "ranking"
                                ) &&
                                "border-emerald-500/40 text-emerald-800 dark:text-emerald-200",
                              t.id === "finalists" &&
                                assistantProgress.finalistsSkipped &&
                                !assistantProgress.finalistsSaved &&
                                "border-amber-500/40 text-amber-900 dark:text-amber-200",
                              t.id === "coach" &&
                                awaitingAck &&
                                "border-amber-500/50 text-amber-900 dark:text-amber-200",
                            )}
                            onClick={() => {
                              if (t.id === "lab") setLabOpenedThisRun(true);
                              if (t.id === "finalists")
                                setStrategiesListFilter("finalists");
                              setResultFocus(t.id);
                              patchSearchParams((params) => {
                                params.set("focus", t.id);
                                if (instrumentId)
                                  params.set("instrumentId", instrumentId);
                                // Salir del modo Verificar D→hoy al cambiar de pestaña de resultado.
                                params.delete("verify");
                              });
                            }}
                          >
                            {t.id === "finalists" &&
                            assistantProgress.finalistsSkipped
                              ? "– "
                              : t.done
                                ? "✓ "
                                : awaitingAck && t.id === "coach"
                                  ? "! "
                                  : ""}
                            {t.label}
                          </Button>
                        ))}
                        {resultFocus === "coach" ? (
                          <AiInfoButton surface="backtest_coach" />
                        ) : resultFocus === "lab" ? (
                          <AiInfoButton surface="lab_optimize" />
                        ) : resultFocus === "fundamental" ? (
                          <AiInfoButton surface="fa_copilot" />
                        ) : null}
                        {batchRows.length > 0 && (
                          <Button
                            type="button"
                            size="sm"
                            role="tab"
                            aria-selected={resultFocus === "ranking"}
                            variant={
                              resultFocus === "ranking" ? "default" : "outline"
                            }
                            className="h-7 text-[11px]"
                            title="Clic en un valor para abrir su análisis técnico"
                            onClick={() => setResultFocus("ranking")}
                          >
                            Ranking lista
                          </Button>
                        )}
                        {listAutoBoard && (
                          <Button
                            type="button"
                            size="sm"
                            role="tab"
                            aria-selected={resultFocus === "list_auto"}
                            variant={
                              resultFocus === "list_auto"
                                ? "default"
                                : "outline"
                            }
                            className={cn(
                              "h-7 text-[11px]",
                              listAutoBoard.done &&
                                !listAutoBoard.aborted &&
                                resultFocus !== "list_auto" &&
                                "border-emerald-500/40 text-emerald-800 dark:text-emerald-200",
                            )}
                            title="Progreso de Lista AUTO: todos los valores, estado y Δ Finalistas"
                            onClick={() => setResultFocus("list_auto")}
                          >
                            {listAutoBoard.done && !listAutoBoard.aborted
                              ? "✓ "
                              : ""}
                            Lista AUTO
                          </Button>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent
                      className={cn(
                        "min-h-0 flex-1 p-3",
                        isAnalysisResultFocus(resultFocus) &&
                          (detail || instrumentId)
                          ? "flex flex-col overflow-hidden pt-1"
                          : "overflow-auto pt-0",
                      )}
                    >
                      {listAutoBoard && resultFocus === "list_auto" && (
                        <BacktestListAutoBoardPanel
                          board={listAutoBoard}
                          selectedInstrumentId={instrumentId || null}
                          onSelectInstrument={openInstrumentInValor}
                          campaignControls={
                            !listAutoBoard.done && !listAutoBoard.aborted
                              ? {
                                  canPause: !listAutoBoard.paused,
                                  canResume:
                                    listAutoBoard.paused &&
                                    !listAutoBoard.rows.some(
                                      (r) => r.phase === "running",
                                    ),
                                  canStop: true,
                                  onPause: pauseListAuto,
                                  onResume: resumeListAuto,
                                  onStop: stopListAuto,
                                  onForceRescanRemaining:
                                    forceListAutoRescanRemaining,
                                }
                              : undefined
                          }
                        />
                      )}

                      <BacktestResultFocusCoach
                        isCoachFocus={resultFocus === "coach"}
                        hasExploreRows={exploreRows.length > 0}
                        hasListAutoBoard={Boolean(listAutoBoard)}
                        coachPanelVisible={
                          exploreRows.length > 0 &&
                          (resultFocus === "coach" ||
                            (Boolean(listAutoBoard) &&
                              fullCycleActive &&
                              coachPass === "post_lab"))
                        }
                        coachPass={coachPass}
                        rows={exploreRows}
                        instrumentId={instrumentId || null}
                        symbol={
                          detail?.symbol ??
                          instrumentLabels[instrumentId]?.symbol ??
                          instruments.find((inst) => inst.id === instrumentId)
                            ?.symbol ??
                          "Valor"
                        }
                        timeframe={runTimeframe}
                        periodLabel={
                          PERIOD_PRESET_OPTIONS.find(
                            (o) => o.value === periodPreset,
                          )?.label ?? periodPreset
                        }
                        sort={exploreSort}
                        onSortChange={setExploreSort}
                        selectedRunId={selectedId}
                        onSelectRun={(runId) => {
                          selectRun(runId, { tab: "run" });
                          setResultFocus("detail");
                        }}
                        onOptimizeCandidate={(row) =>
                          startOptimizeFromExplore(row, "explore_best")
                        }
                        onOptimizeSemifinal={(candidates) => {
                          void optimizeSemifinalFromCoach(candidates);
                        }}
                        barLimit={
                          exploreRows.find(
                            (row) =>
                              row.status === "ok" && row.barCount != null,
                          )?.barCount ?? detail?.barCount
                        }
                        futureWeight={assistantPrefs.coach.futureWeight}
                        llmNarrate={assistantPrefs.coach.llmNarrate}
                        freshnessInputFingerprint={
                          instrumentId
                            ? currentFinalistsInputFingerprint(instrumentId)
                            : null
                        }
                        autoSaveFinalists={
                          coachPass === "post_lab" &&
                          !assistantProgress.finalistsSaved &&
                          !assistantProgress.finalistsSkipped
                        }
                        hasExistingTopForSave={hasExistingTopForSave}
                        experimentAsOf={
                          isDiaDInPast(diaD) ? effectiveDiaD(diaD) : null
                        }
                        autoSaveSemifinal={semifinalShortcutArmed}
                        cycleCoach1Active={
                          fullCycleActive &&
                          coachPass === "initial" &&
                          !exploreRunning
                        }
                        autoAckOnCycle={assistantPrefs.coach.autoAckOnCycle}
                        pauseIfAckNeeded={assistantPrefs.coach.pauseIfAckNeeded}
                        requireAckBeforeLab={
                          assistantPrefs.coach.requireAckBeforeLab
                        }
                        labImprovedCountHint={labImprovedThisCycle}
                        onAwaitingAckChange={(awaiting) => {
                          setAwaitingAck(awaiting);
                          if (!awaiting) {
                            setAwaitingAckStage(null);
                            return;
                          }
                          setAwaitingAckStage(
                            coachPass === "post_lab" ? "revalidate" : "coach1",
                          );
                        }}
                        onCoachGateChange={setCoachGate}
                        onAutoSaveStatus={(message) => {
                          if (isSemifinalShortcutStatusMessage(message)) {
                            settleFullCycle("skip_lab", message);
                            return;
                          }
                          const saved = isFinalistsSavedStatusMessage(message);
                          if (saved && !listAutoRef.current) {
                            setResultFocus("finalists");
                            setStrategiesListFilter("finalists");
                          }
                          settleFullCycle(
                            saved ? "saved" : "skip_finalists",
                            message,
                          );
                        }}
                        progress={exploreProgress}
                        running={exploreRunning}
                        equityByRunId={Object.fromEntries(
                          exploreRows
                            .filter((r) => r.runId)
                            .map((r) => {
                              const cached = queryClient.getQueryData<{
                                data?: {
                                  equityCurve?: import("@bolsa/shared").BacktestEquityPointDto[];
                                };
                              }>(["backtest", r.runId!]);
                              return [
                                r.runId!,
                                cached?.data?.equityCurve,
                              ] as const;
                            }),
                        )}
                      />

                      {(resultFocus === "lab" ||
                        (Boolean(listAutoBoard) &&
                          fullCycleActive &&
                          labOpenedThisRun &&
                          !assistantProgress.labDone)) && (
                        <BacktestResultFocusLab
                          isLabFocus={resultFocus === "lab"}
                          hasSeeds={
                            (labZones ?? []).some((z) => z.seed) ||
                            Boolean(optimizeSeed)
                          }
                          zones={
                            labZones ??
                            padLabZones(
                              optimizeSeed
                                ? [
                                    {
                                      id: `zone-1-${optimizeSeed.strategyType}`,
                                      rank: 1,
                                      seed: optimizeSeed,
                                    },
                                  ]
                                : [],
                            )
                          }
                          instruments={instrumentsQuery.data?.data ?? []}
                          defaultInstrumentId={instrumentId}
                          autoHandoff={fullCycleActive}
                          maxDrawdownSoftPct={
                            coachProfilePolicy.maxDrawdownSoftPct
                          }
                          profileId={coachProfilePolicy.profileId}
                          profileHorizon={coachProfilePolicy.horizon}
                          profileRiskTolerance={
                            coachProfilePolicy.riskTolerance
                          }
                          onGoToCoach={() => {
                            setResultFocus("coach");
                            patchSearchParams((params) => {
                              params.set("focus", "coach");
                            });
                          }}
                          onClearZoneSeed={(zoneId) => {
                            setLabZones((prev) => {
                              if (!prev) {
                                setOptimizeSeed(null);
                                return null;
                              }
                              const next = prev.map((z) =>
                                z.id === zoneId
                                  ? {
                                      ...z,
                                      seed: null,
                                      jobId: null,
                                      jobIds: null,
                                    }
                                  : z,
                              );
                              setOptimizeSeed(
                                next.find((z) => z.seed)?.seed ?? null,
                              );
                              return next;
                            });
                          }}
                          onReanalyzeWithCoach={(payload) =>
                            reanalyzeLabWithCoach(payload)
                          }
                          onAutoHandoffStatus={(message) => {
                            if (
                              message.includes("No se pisan Finalistas") ||
                              message.includes("Lab sin Mejor") ||
                              message.includes("Lab sin zonas") ||
                              message.includes("Lab timeout")
                            ) {
                              // Sin TOP durable (vacío o huérfano tras borrar estrategias):
                              // Coach² / auto-save con el lote actual (primera escritura).
                              void (async () => {
                                let durable = hasExistingTopForSave;
                                try {
                                  await queryClient.invalidateQueries({
                                    queryKey: ["strategies"],
                                  });
                                  if (instrumentId) {
                                    await queryClient.invalidateQueries({
                                      queryKey: [
                                        "instrument-strategy-top",
                                        instrumentId,
                                        runTimeframe,
                                      ],
                                    });
                                  }
                                  const [stratsRes, topRes] = await Promise.all(
                                    [
                                      queryClient.fetchQuery({
                                        queryKey: ["strategies"],
                                        queryFn: api.getStrategies,
                                      }),
                                      instrumentId
                                        ? queryClient.fetchQuery({
                                            queryKey: [
                                              "instrument-strategy-top",
                                              instrumentId,
                                              runTimeframe,
                                            ],
                                            queryFn: () =>
                                              api.getInstrumentStrategyTop(
                                                instrumentId,
                                                runTimeframe,
                                              ),
                                          })
                                        : Promise.resolve(null),
                                    ],
                                  );
                                  const ids = new Set(
                                    (stratsRes?.data ?? []).map((s) => s.id),
                                  );
                                  const top = topRes?.data ?? null;
                                  for (const slot of top?.slots ?? []) {
                                    const sid = slot.strategyDefinitionId;
                                    if (!sid || ids.has(sid)) continue;
                                    try {
                                      const one = await api.getStrategy(sid);
                                      if (one?.data?.id) ids.add(one.data.id);
                                    } catch {
                                      /* slot huérfano */
                                    }
                                  }
                                  durable = instrumentTopIsDurable(top, ids);
                                  const experimentMode = isDiaDInPast(diaD);
                                  if (
                                    (!durable || experimentMode) &&
                                    exploreOkCount > 0
                                  ) {
                                    setLabImprovedThisCycle(0);
                                    setCoachPass("post_lab");
                                    setResultFocus("coach");
                                    setAssistantStatus(
                                      experimentMode
                                        ? `Ciclo: Lab sin mejora · DÍA D ${effectiveDiaD(diaD)} → grabando F-D (F-hoy intacto)…`
                                        : top
                                          ? "Ciclo: Lab sin mejora · Finalistas huérfanos → grabando (primera escritura)…"
                                          : "Ciclo: Lab sin mejora · sin TOP previo → grabando Finalistas (primera escritura)…",
                                    );
                                    return;
                                  }
                                  settleFullCycle("skip_lab", message);
                                  return;
                                } catch {
                                  durable = hasExistingTopForSave;
                                }
                                if (
                                  (!durable || isDiaDInPast(diaD)) &&
                                  exploreOkCount > 0
                                ) {
                                  setLabImprovedThisCycle(0);
                                  setCoachPass("post_lab");
                                  setResultFocus("coach");
                                  setAssistantStatus(
                                    isDiaDInPast(diaD)
                                      ? `Ciclo: Lab sin mejora · DÍA D ${effectiveDiaD(diaD)} → grabando F-D (F-hoy intacto)…`
                                      : "Ciclo: Lab sin mejora · sin TOP previo → grabando Finalistas (primera escritura)…",
                                  );
                                  return;
                                }
                                settleFullCycle("skip_lab", message);
                              })();
                              return;
                            }
                            setAssistantStatus(message);
                          }}
                        />
                      )}

                      {resultFocus === "finalists" && (
                        <BacktestResultFocusFinalists
                          instrumentId={instrumentId}
                          symbol={
                            instrumentLabels[instrumentId]?.symbol ??
                            instruments.find((i) => i.id === instrumentId)
                              ?.symbol ??
                            "Valor"
                          }
                          timeframe={runTimeframe}
                          top={instrumentTop}
                          asOfDiaD={diaD}
                          activeProfileId={coachProfilePolicy.profileId}
                          proposePendingStrategyId={
                            proposeFinalistMutation.isPending
                              ? (proposeFinalistMutation.variables
                                  ?.strategyDefinitionId ?? null)
                              : null
                          }
                          onUseStrategy={(strategyId, slot) => {
                            setSavedStrategyId(strategyId);
                            setRunSource("saved");
                            if (slot?.runId) {
                              openFinalistChecklist(slot);
                              return;
                            }
                            setPreferOpenAnalysis(false);
                            setResultFocus("detail");
                            patchSearchParams((params) => {
                              params.set("focus", "detail");
                            });
                          }}
                          onOpenChecklist={openFinalistChecklist}
                          onProposeSupervised={proposeFinalistSupervisedSlot}
                          onGoToCoach={() => {
                            setResultFocus("coach");
                            patchSearchParams((params) => {
                              params.set("focus", "coach");
                            });
                          }}
                        />
                      )}

                      {batchRows.length > 0 && resultFocus === "ranking" && (
                        <BacktestResultRanking
                          rows={batchRows}
                          sort={batchSort}
                          onSortChange={setBatchSort}
                          selectedRunId={selectedId}
                          selectedInstrumentId={instrumentId || null}
                          onOpenInstrument={(id, runId) =>
                            openInstrumentInValor(id, {
                              runId,
                              soft: true,
                            })
                          }
                          onSelectRun={(runId) =>
                            selectRun(runId, { tab: "run", focus: "detail" })
                          }
                          progress={batchProgress}
                          listName={
                            listDetail?.name ??
                            lists.find((l) => l.id === listId)?.name
                          }
                          running={batchRunning}
                        />
                      )}

                      {resultFocus === "fundamental" && (
                        <BacktestResultFundamental
                          instrumentId={instrumentId}
                          diaD={diaD}
                        />
                      )}

                      {resultFocus === "detail" && (
                        <BacktestResultDetail
                          diaDVerifyActive={diaDVerifyActive}
                          detail={detail}
                          instrumentId={instrumentId}
                          selectedId={selectedId}
                          detailFetching={detailQuery.isFetching}
                          detailHasData={Boolean(detailQuery.data?.data)}
                          detailDataInstrumentId={
                            detailQuery.data?.data?.instrumentId
                          }
                          detailErrorActive={detailQuery.isError}
                          detailError={detailQuery.error}
                          instrumentSymbol={instrumentSymbol}
                          instrumentName={instrumentLabels[instrumentId]?.name}
                          timeframe={runTimeframe}
                          periodPreset={periodPreset}
                          customDateFrom={customDateFrom}
                          customDateTo={customDateTo}
                          diaD={diaD}
                          preferOpenAnalysis={preferOpenAnalysis}
                          bars={replayBarsQuery.data?.data}
                          barsLoading={
                            replayBarsQuery.isLoading && !replayBarsQuery.data
                          }
                          barsError={
                            replayBarsQuery.isError && !replayBarsQuery.data
                          }
                          equityCurve={equityCurve}
                          focusTimestamp={focusTimestamp}
                          focusedTrade={focusedTrade}
                          onSelectTrade={setFocusTimestamp}
                          onJumpToTrade={focusTrade}
                          displayTrialId={displayTrialId}
                          displayMetrics={displayMetrics}
                          linkedTrial={linkedTrial}
                          drawingMarkers={drawingMarkers}
                          finalistBadge={detailFinalistBadge}
                          hasRankingRows={batchRows.length > 0}
                          onBackToRanking={() => setResultFocus("ranking")}
                          onStartOptimize={startOptimizeFromDetail}
                          onExportJson={() => {
                            if (detail) exportBacktestJson(detail);
                          }}
                          onExportTrades={() => {
                            if (detail) exportTradesCsv(detail);
                          }}
                          onExportEquity={() => {
                            if (detail) exportEquityCsv(detail);
                          }}
                          deployingPaper={deployPaperMutation.isPending}
                          deployError={deployPaperMutation.error}
                          onDeployPaper={(payload) => {
                            if (!detail) return;
                            deployPaperMutation.mutate({
                              strategyId: detail.strategyDefinitionId ?? "",
                              runId: detail.id,
                              initialDeposit: detail.initialCash,
                              labEvidence: payload.labEvidence,
                            });
                          }}
                          manifestSummary={manifestSummary}
                        />
                      )}
                    </CardContent>
                  </Card>
                }
              />

              <details className="mx-auto w-full max-w-[1600px] rounded-lg border border-border/70 bg-card/40 px-1">
                <summary className="cursor-pointer list-none px-3 py-2.5 text-sm font-medium text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
                  {PAPER_PATH_MONITOR.shortTitle}
                  <span className="ml-2 text-[11px] font-normal text-muted-foreground">
                    estado TOP / paper / Proponer · solo lectura
                  </span>
                </summary>
                <div className="border-t border-border/60 px-2 pb-3 pt-2">
                  <StrategyMonitorPanel
                    embedded
                    initialListId={
                      universeMode === "list" && listId ? listId : undefined
                    }
                  />
                </div>
              </details>
            </>
          )}

          {tab === "jobs" && (
            <div className="mx-auto min-h-0 w-full max-w-[1600px] flex-1 space-y-4 overflow-auto px-1">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold tracking-tight">
                    Lab · Optimizar
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Mismo Lab del embudo Coach → Finalistas. Busca Mejor ≥ ancla
                    (OOS); no escribe Finalistas.
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
                  <p className="font-medium text-foreground">
                    Sin semilla cargada
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Desde Probar → Coach: «Pasar al Lab» o «Abrir Lab · #1».
                    También puedes elegir instrumento abajo y lanzar a mano.
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
          )}

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
