/**
 * Hub Backtesting (`/backtests`) — orquestación UI del embudo.
 *
 * Ciclo completo / Lista AUTO / Finalistas Checklist+Proponer / Lab handoff.
 * Política motor: `backtest-assistant-full-cycle.ts`, `backtest-list-auto.ts`.
 * Documentación: `docs/engineering/session-handoff-2026-07-30.md` ·
 * `docs/engineering/list-auto-ops-2026-07-29.md`.
 */

import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileJson, LineChart, SlidersHorizontal, Table } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  BACKTEST_STRATEGIES,
  STRATEGY_PRESET_CATEGORY_LABELS,
  strategyDefinitionFromChartDraft,
  type BacktestStrategyType,
  type ChartDrawing,
  type ChartStrategySetupDraft,
  type ChartTimeframe,
} from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { useListAutoActivityStore } from '@/stores/list-auto-activity-store';
import { BacktestChartImportPanel } from '@/features/backtests/backtest-chart-import-panel';
import {
  runBacktestBatch,
  type BatchRankRow,
  type BatchSortKey,
} from '@/features/backtests/backtest-batch-run';
import { BacktestExploreRanking } from '@/features/backtests/backtest-explore-panel';
import {
  matrixRowsToExploreRows,
  periodReturnsFromEquity,
  resolveMatrixCoachTargetIds,
  type ExplorePresetRow,
  type ExploreSortKey,
} from '@/features/backtests/backtest-explore-value';
import { rankTechnicalRecommendations } from '@/features/backtests/backtest-deep-coach';
import {
  buildOptimizeBeforeAfter,
  type OptimizeBeforeAfterSnapshot,
} from '@/features/backtests/backtest-optimize-delta';
import { BacktestOptimizeCompareCard } from '@/features/backtests/backtest-optimize-compare-card';
import { BacktestLabBoard } from '@/features/backtests/backtest-lab-board';
import type { LabBoardZone, LabReanalyzeRequest } from '@/features/backtests/backtest-lab-board-types';
import { padLabZones } from '@/features/backtests/backtest-lab-board-types';
import {
  buildCoachBatteryFingerprint,
  canReuseCoachLote,
  finalistMatrixRowIds,
  mergeUniverseTargetIds,
} from '@/features/backtests/backtest-coach-lote';
import { buildAuditedDeepTechnicalCoachNote } from '@/features/backtests/coach-dual-audit';
import {
  buildProfilePolicyFingerprintSegment,
  formatCoachProfileRailLabel,
  resolveCoachProfilePolicy,
  shouldAdvanceToLab,
} from '@/features/backtests/coach-profile-policy';
import { BacktestOptimizePanel } from '@/features/backtests/backtest-optimize-panel';
import {
  buildOptimizeSeedFromExploreRow,
  buildOptimizeSeedFromRun,
  isOptimizableStrategy,
  type OptimizeSeed,
} from '@/features/backtests/backtest-optimize-seed';
import { BacktestAssistantRail } from '@/features/backtests/backtest-assistant-rail';
import { InstrumentStrategyTopPanel } from '@/features/backtests/instrument-strategy-top-panel';
import { FundamentalCardPanel } from '@/features/instruments/fundamental-card-panel';
import { AiInfoButton } from '@/features/ai/ai-info-button';
import { finalistHudBadgeFromTop } from '@/features/backtests/instrument-top-match';
import {
  canAutoRunStep,
  withUniverseDone,
  emptyAssistantProgress,
  isAssistantStepComplete,
  resolveAssistantActiveStep,
  type AssistantSessionProgress,
} from '@/features/backtests/backtest-assistant-completion';
import {
  loadAssistantPrefs,
  saveAssistantPrefs,
  type AssistantPrefs,
} from '@/features/backtests/backtest-assistant-prefs';
import {
  LIST_AUTO_MAX_INSTRUMENTS,
  confirmListAutoOverCap,
  createListAutoCampaign,
  filterListAutoIdsWithoutFinalists,
  listAutoOverCapWarning,
  advanceListAutoAfterSettle,
  listAutoDoneStatus,
  listAutoPausedStatus,
  listAutoPlayTitle,
  listAutoProgressLabel,
  listAutoUniverseHint,
  listModeWizardTitle,
  pauseListAutoCampaign,
  resumeListAutoCampaign,
  shouldStartListAuto,
  stopListAutoCampaign,
  type FullCycleSettleReason,
  type ListAutoCampaign,
} from '@/features/backtests/backtest-list-auto';
import { summarizeListMemberBacktest } from '@/features/backtests/backtest-list-member-status';
import { summarizeListMemberFa } from '@/features/backtests/backtest-list-member-fa';
import { instrumentTopIsDurable, universeEmptyStatus } from '@/features/backtests/backtest-assistant-full-cycle';
import {
  isCoach1AckSatisfied,
  isFinalistsSavedStatusMessage,
  isSemifinalShortcutStatusMessage,
  resolveCoach1AdvanceAction,
  shouldReenterUniverseToLabChain,
} from '@/features/backtests/assistant-cycle-orchestrator';
import {
  loadBacktestRunContext,
  saveBacktestRunContext,
} from '@/features/backtests/backtest-run-context';
import {
  captureListAutoBeforeTop,
  createListAutoBoard,
  enrichListAutoBoardLabels,
  listAutoTopFingerprint,
  markListAutoBoardAborted,
  markListAutoBoardDone,
  markListAutoBoardPaused,
  markListAutoBoardRunning,
  markListAutoBoardSettled,
  resolveListAutoChange,
  type ListAutoBoardState,
} from '@/features/backtests/backtest-list-auto-board';
import { BacktestListAutoBoardPanel } from '@/features/backtests/backtest-list-auto-board-panel';
import {
  buildCoreRReportFromBoard,
  judgeCoreR,
  saveCoreRReport,
  type CoreRDualAuditSnap,
} from '@/features/backtests/core-r-judgment';
import { readStashedOosEvidence } from '@/features/backtests/backtest-oos-evidence';
import { readLabEvidenceFromCoachFacts } from '@/features/backtests/finalists-stability-summary';
import {
  boardFromContinueSnapshot,
  buildListAutoContinueSnapshot,
  buildListAutoPausedSnapshot,
  campaignFromPausedSnapshot,
  clearListAutoContinueSnapshot,
  clearListAutoPausedSnapshot,
  loadListAutoContinueSnapshot,
  loadListAutoPausedSnapshot,
  matchListAutoContinueSnapshot,
  saveListAutoContinueSnapshot,
  saveListAutoPausedSnapshot,
} from '@/features/backtests/backtest-list-auto-persist';
import {
  buildFinalistsFreshnessStamp,
  buildFinalistsInputFingerprint,
  formatFreshnessAge,
  freshnessSkipDenialLabel,
  instrumentLastBarDate,
  isFinalistsFreshnessContextReady,
  mergeFreshnessIntoCoachFacts,
  readFinalistsFreshness,
  readLocalFreshnessFingerprint,
  shouldSkipFinalistsSearch,
  writeLocalFreshnessFingerprint,
} from '@/features/backtests/backtest-finalists-freshness';
import { ASSISTANT_STEPS, type AssistantStepId } from '@/features/backtests/backtest-assistant-steps';
import { buildOptimizeRequestsFromSeed } from '@/features/backtests/backtest-optimize-from-seed';
import { BacktestHubLayout } from '@/features/backtests/backtest-hub-layout';
import { BacktestRankingTable } from '@/features/backtests/backtest-ranking-table';
import {
  BacktestResultView,
} from '@/features/backtests/backtest-result-view';
import {
  BacktestInstrumentPreview,
  BacktestResultEmpty,
} from '@/features/backtests/backtest-instrument-preview';
import {
  equityCurveFromDetail,
  exportBacktestJson,
  exportEquityCsv,
  exportTradesCsv,
} from '@/features/backtests/backtest-export';
import { BacktestUniversePicker } from '@/features/backtests/backtest-universe-picker';
import { BacktestStrategyMatrixPanel } from '@/features/backtests/backtest-strategy-matrix-panel';
import { BacktestMassComparePanel } from '@/features/backtests/backtest-mass-compare-panel';
import {
  BacktestLibraryTab,
  type StrategiesListFilter as LibraryStrategiesListFilter,
} from '@/features/backtests/backtest-library-tab';
import {
  parseLibraryFilterParam,
  parseLibraryNavFromSearch,
} from '@/features/backtests/library-nav';
import { filterStrategiesByLibraryBucket } from '@/features/backtests/library-strategy-buckets';
import { BacktestHistoryTab } from '@/features/backtests/backtest-history-tab';
import {
  STRATEGY_MATRIX_MAX_SELECTED,
  annotateStrategyMatrixRowsWithTop,
  buildStrategyMatrixRows,
  exploreBatteryRowIds,
  runStrategyMatrixBattery,
  type StrategyMatrixFilter,
  type StrategyMatrixRow,
  type StrategyMatrixRunProgress,
} from '@/features/backtests/backtest-strategy-matrix';
import {
  BacktestZoneSettingsButton,
  BacktestZoneSettingsDialog,
} from '@/features/backtests/backtest-zone-settings-dialog';
import {
  loadBacktestZonePrefs,
  patchStrategyMatrixTablePrefs,
  type BacktestZonePrefs,
} from '@/features/backtests/backtest-zone-prefs';
import {
  defaultMineStrategiesFilters,
  filterMineStrategies,
  uniqueSortedValues,
  type MineStrategiesFilterState,
} from '@/features/backtests/mine-strategies-filters';
import { PAPER_PATH_LAB, PAPER_PATH_MONITOR, PAPER_PATH_SUPERVISED } from '@/features/settings/paper-paths-copy';
import { proposeFinalistSupervised } from '@/features/backtests/finalist-propose-supervised';
import { isOpenAnalysisQuery } from '@/features/backtests/strategy-monitor';
import { StrategyMonitorPanel } from '@/features/backtests/strategy-monitor-panel';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { useAlertsStore } from '@/stores/alerts-store';
import {
  openHelpAiPlatform,
  useSupervisedF3QueueStore,
} from '@/stores/supervised-f3-queue-store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { useMediaQuery } from '@/lib/use-media-query';
import { useActiveChartTab } from '@/stores/workspace-store';
import {
  DEFAULT_PERIOD_PRESET,
  PERIOD_PRESET_OPTIONS,
  effectiveDiaD,
  isDiaDInPast,
  resolveBacktestWindow,
  todayIsoDate,
  type PeriodPreset,
} from '@/features/backtests/backtest-period';
import { BacktestDiaDOriginControl } from '@/features/backtests/backtest-dia-d-origin-control';
import { formatDiaDDisplay } from '@/features/backtests/dia-d-favorites';
import { DiaDVerifyHost } from '@/features/backtests/dia-d-verify-host';
import { UniverseChip } from '@/features/platform/universe-chip';
import { setAdoption } from '@/features/platform/strategy-adoption';
import { useDiaDTradingSessionStore } from '@/stores/dia-d-trading-session-store';

const STRATEGY_OPTIONS = Object.entries(BACKTEST_STRATEGIES) as [
  BacktestStrategyType,
  { label: string; description: string },
][];

type HubTab = 'run' | 'history' | 'strategies' | 'jobs';
type RunSource = 'preset' | 'saved';
type UniverseMode = 'single' | 'list';
type ResultFocus =
  | 'detail'
  | 'fundamental'
  | 'coach'
  | 'lab'
  | 'finalists'
  | 'ranking'
  | 'list_auto';

/** Vistas de análisis (técnico = legacy `detail`). */
function isAnalysisResultFocus(focus: ResultFocus): boolean {
  return focus === 'detail' || focus === 'fundamental';
}
type StrategiesListFilter = LibraryStrategiesListFilter;

function parseTab(raw: string | null): HubTab {
  if (raw === 'history') return 'history';
  if (raw === 'strategies') return 'strategies';
  if (raw === 'jobs') return 'jobs';
  // Legacy deep-links (?tab=new) → Run
  if (raw === 'new' || raw === 'run' || raw == null || raw === '') return 'run';
  return 'run';
}

export function BacktestsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const onBacktestsRoute = pathname.startsWith('/backtests');
  const tabParam = searchParams.get('tab');
  // Solo redirigir legacy en la ruta real (no en keep-alive Lista AUTO fuera de /backtests).
  if (onBacktestsRoute && tabParam === 'screeners') {
    return <Navigate to="/screeners" replace />;
  }
  const tab = parseTab(tabParam);
  const runIdFromUrl = searchParams.get('runId');

  const queryClient = useQueryClient();
  const { effectiveAccountId } = useActiveAccount();
  const diaDVerifySession = useDiaDTradingSessionStore((s) => s.session);
  /** Solo hijack Análisis técnico con ?verify=1 (no por sesión residual en localStorage). */
  const diaDVerifyActive =
    searchParams.get('verify') === '1' && Boolean(diaDVerifySession);
  const diaDVerifyFullBleed = Boolean(
    diaDVerifyActive && diaDVerifySession?.fullBleedMovie,
  );
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enqueueSupervised = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActiveSupervised = useSupervisedF3QueueStore((s) => s.setActive);
  const [instrumentId, setInstrumentId] = useState(searchParams.get('instrumentId') ?? '');
  const [universeMode, setUniverseMode] = useState<UniverseMode>('single');
  const [listId, setListId] = useState('');
  const [runSource, setRunSource] = useState<RunSource>('preset');
  const [strategyType, setStrategyType] = useState<BacktestStrategyType>('sma_crossover');
  const [savedStrategyId, setSavedStrategyId] = useState('');
  const [initialCash, setInitialCash] = useState(
    () => loadBacktestRunContext().initialCash || '10000',
  );
  const [commissionBps, setCommissionBps] = useState(
    () => loadBacktestRunContext().commissionBps || '0',
  );
  const [slippageBps, setSlippageBps] = useState(
    () => loadBacktestRunContext().slippageBps || '0',
  );
  const [runTimeframe, setRunTimeframe] = useState<ChartTimeframe>(
    () => (loadBacktestRunContext().timeframe as ChartTimeframe) || '1d',
  );
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>(
    () => (loadBacktestRunContext().periodPreset as PeriodPreset) || DEFAULT_PERIOD_PRESET,
  );
  const [customDateFrom, setCustomDateFrom] = useState(
    () => loadBacktestRunContext().customDateFrom,
  );
  const [customDateTo, setCustomDateTo] = useState(() => loadBacktestRunContext().customDateTo);
  const [diaD, setDiaD] = useState(() => loadBacktestRunContext().diaD);
  const [selectedId, setSelectedId] = useState<string | null>(() => runIdFromUrl);
  const [newStrategyName, setNewStrategyName] = useState('');
  const [newStrategyPreset, setNewStrategyPreset] = useState<BacktestStrategyType>('sma_crossover');
  const [replayDrawings, setReplayDrawings] = useState<ChartDrawing[] | null>(null);
  const [drawingLoadHint, setDrawingLoadHint] = useState<string | null>(null);
  const [focusTimestamp, setFocusTimestamp] = useState<string | null>(null);
  const [batchRows, setBatchRows] = useState<BatchRankRow[]>([]);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ done: 0, total: 0 });
  const [batchSort, setBatchSort] = useState<BatchSortKey>('excess');
  const [batchError, setBatchError] = useState<string | null>(null);
  const [exploreRows, setExploreRows] = useState<ExplorePresetRow[]>([]);
  const [exploreRunning, setExploreRunning] = useState(false);
  const [exploreProgress, setExploreProgress] = useState({ done: 0, total: 0 });
  const [exploreSort, setExploreSort] = useState<ExploreSortKey>('excess');
  const [exploreError, setExploreError] = useState<string | null>(null);
  const [resultFocus, setResultFocus] = useState<ResultFocus>(() => {
    const focus = searchParams.get('focus');
    if (
      focus === 'coach' ||
      focus === 'lab' ||
      focus === 'finalists' ||
      focus === 'detail' ||
      focus === 'fundamental' ||
      focus === 'ranking' ||
      focus === 'list_auto'
    ) {
      return focus;
    }
    return 'detail';
  });
  const [optimizeSeed, setOptimizeSeed] = useState<OptimizeSeed | null>(null);
  const [labZones, setLabZones] = useState<LabBoardZone[] | null>(null);
  /** Coach tras Lab: techo ★5 + Guardar Finalistas. */
  const [coachPass, setCoachPass] = useState<'initial' | 'post_lab'>('initial');
  const [optimizeCompare, setOptimizeCompare] = useState<OptimizeBeforeAfterSnapshot | null>(null);
  const [assistantStatus, setAssistantStatus] = useState<string | null>(null);
  const [strategiesListFilter, setStrategiesListFilter] = useState<StrategiesListFilter>(() =>
    parseLibraryFilterParam(searchParams.get('library')) ?? 'all',
  );
  const [mineFilters, setMineFilters] = useState<MineStrategiesFilterState>(() => {
    const base = defaultMineStrategiesFilters();
    const q = searchParams.get('q');
    return q ? { ...base, query: q } : base;
  });
  const [libraryFocusStrategyId, setLibraryFocusStrategyId] = useState<string | null>(
    () => searchParams.get('strategyId'),
  );
  const [libraryFocusPreset, setLibraryFocusPreset] = useState<string | null>(
    () => searchParams.get('preset'),
  );
  const [cloneOpen, setCloneOpen] = useState(false);
  const [semifinalEnqueuePending, setSemifinalEnqueuePending] = useState(false);
  const [semifinalJobsQueued, setSemifinalJobsQueued] = useState(false);
  const [assistantPrefs, setAssistantPrefs] = useState<AssistantPrefs>(() => loadAssistantPrefs());
  const [assistantProgress, setAssistantProgress] = useState<AssistantSessionProgress>(() =>
    emptyAssistantProgress(),
  );
  /** Mirror sync del progreso: encadenar pasos en el mismo tick sin race de setState. */
  const assistantProgressRef = useRef(assistantProgress);
  assistantProgressRef.current = assistantProgress;
  /** Paso destacado en el rail mientras se ejecuta. */
  const [assistantFocus, setAssistantFocus] = useState<AssistantStepId | null>(null);
  /** El usuario abrió Lab en esta pasada (evita ✓ lab por un TOP viejo en BD). */
  const [labOpenedThisRun, setLabOpenedThisRun] = useState(false);
  /** Play con ciclo completo activo (Coach → Lab → Coach² → Finalistas). */
  const [fullCycleActive, setFullCycleActive] = useState(false);
  /** Ciclo parado en Coach¹ / Revalidar esperando ACK humano. */
  const [awaitingAck, setAwaitingAck] = useState(false);
  const [awaitingAckStage, setAwaitingAckStage] = useState<
    'coach1' | 'revalidate' | null
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
    isOpenAnalysisQuery(searchParams.get('openAnalysis')),
  );
  /** Campaña lista AUTO (ref = fuente de verdad; UI = progreso). */
  const listAutoRef = useRef<ListAutoCampaign | null>(null);
  const listAutoPendingStartRef = useRef<number | null>(null);
  const [listAutoUi, setListAutoUi] = useState<{
    index: number;
    total: number;
    symbol: string;
  } | null>(null);
  /** Tablero visual de la campaña (persiste al terminar para revisar Δ). */
  const [listAutoBoard, setListAutoBoard] = useState<ListAutoBoardState | null>(null);
  /** Filtro opcional: no encolar tickers que ya tienen Finalistas TOP. */
  const [listAutoSkipWithFinalists, setListAutoSkipWithFinalists] = useState(false);
  /** Fingerprints ya analizados en esta pestaña (skip sin stamp BD). */
  const listAutoFreshnessMemoryRef = useRef<Map<string, string>>(new Map());
  /** Token: fuerza el efecto de arranque aunque instrumentId no cambie. */
  const [listAutoStartToken, setListAutoStartToken] = useState(0);
  const listAutoPauseRestoredRef = useRef(false);
  /** Evita doble settle del mismo índice (saltaría tickers). */
  const listAutoSettleLockRef = useRef<number | null>(null);
  const assistantChainRef = useRef<string>('');
  const [zonePrefs, setZonePrefs] = useState<BacktestZonePrefs>(() => loadBacktestZonePrefs());
  const [zoneSettingsOpen, setZoneSettingsOpen] = useState(false);
  const [matrixFilter, setMatrixFilter] = useState<StrategyMatrixFilter>(
    () => loadBacktestZonePrefs().strategyMatrix.filter,
  );
  const [matrixRows, setMatrixRows] = useState<StrategyMatrixRow[]>(() =>
    buildStrategyMatrixRows([]),
  );
  const [matrixSelectedIds, setMatrixSelectedIds] = useState<Set<string>>(() => new Set());
  const batchAbortRef = useRef<AbortController | null>(null);
  const exploreAbortRef = useRef<AbortController | null>(null);

  const activeChartTab = useActiveChartTab();
  const isWide = useMediaQuery('(min-width: 1024px)');

  const pruneHistory = useCallback(
    async (keep: number) => {
      try {
        await api.pruneBacktests(keep);
      } catch {
        // Non-blocking: list still refreshes; user can retry via settings.
      }
      void queryClient.invalidateQueries({ queryKey: ['backtests'] });
    },
    [queryClient],
  );

  /** Keep detail available after multi-run even before list refresh; avoid 404 after prune. */
  const seedBacktestDetail = useCallback(
    (detail: import('@bolsa/shared').BacktestRunDetailDto) => {
      queryClient.setQueryData(['backtest', detail.id], { data: detail });
    },
    [queryClient],
  );

  /** Never prune below the OK count of the lote just created. */
  function pruneAfterBatch(okCount: number) {
    void pruneHistory(Math.max(zonePrefs.historyMaxKept, okCount));
  }

  const instrumentsQuery = useQuery({
    queryKey: ['instruments'],
    queryFn: api.getInstruments,
    staleTime: 60_000,
  });

  const listsQuery = useQuery({
    queryKey: ['lists'],
    queryFn: api.getLists,
  });

  const listDetailQuery = useQuery({
    queryKey: ['list', listId],
    queryFn: () => api.getList(listId),
    enabled: universeMode === 'list' && Boolean(listId),
  });

  /** Símbolos/nombres de la lista activa (cubre índices recién suscritos aún no en catálogo cacheado). */
  const listQuotesQuery = useQuery({
    queryKey: ['list-quotes', listId],
    queryFn: () => api.getListQuotes(listId),
    enabled: universeMode === 'list' && Boolean(listId),
    staleTime: 30_000,
  });

  const listMemberIdsKey = useMemo(() => {
    const ids = listQuotesQuery.data?.data?.map((q) => q.id) ?? [];
    return ids.slice().sort().join(',');
  }, [listQuotesQuery.data?.data]);

  /** TOPs en batch para resumen de estado en Lista valores. */
  const listTopsQuery = useQuery({
    queryKey: ['instrument-strategy-tops-batch', listId, runTimeframe, listMemberIdsKey],
    queryFn: () =>
      api.queryInstrumentStrategyTops({
        instrumentIds: (listQuotesQuery.data?.data ?? []).map((q) => q.id),
        timeframe: runTimeframe,
      }),
    enabled:
      universeMode === 'list' &&
      Boolean(listId) &&
      Boolean(listMemberIdsKey) &&
      (listQuotesQuery.data?.data.length ?? 0) > 0,
    staleTime: 20_000,
  });

  /** Chips FA en batch (PR3) — Score_FUND compacto por miembro. */
  const listFaQuery = useQuery({
    queryKey: ['instrument-fundamentals-batch', listId, listMemberIdsKey],
    queryFn: () =>
      api.queryInstrumentFundamentals({
        instrumentIds: (listQuotesQuery.data?.data ?? []).map((q) => q.id),
      }),
    enabled:
      universeMode === 'list' &&
      Boolean(listId) &&
      Boolean(listMemberIdsKey) &&
      (listQuotesQuery.data?.data.length ?? 0) > 0,
    staleTime: 60_000,
  });

  const strategiesQuery = useQuery({
    queryKey: ['strategies'],
    queryFn: api.getStrategies,
  });

  const instrumentTopQuery = useQuery({
    queryKey: ['instrument-strategy-top', instrumentId, runTimeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId, runTimeframe),
    enabled: Boolean(instrumentId),
    staleTime: 15_000,
    retry: false,
  });

  /** Perfil de la cuenta activa → CORE-P gate Coach¹→Lab. */
  const accountProfileQuery = useQuery({
    queryKey: ['account-active-profile', effectiveAccountId],
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
        riskTolerance: accountProfileQuery.data?.data?.declared?.riskTolerance ?? null,
      }),
    [accountProfileQuery.data?.data],
  );

  const coachProfileRailLabel = useMemo(
    () => formatCoachProfileRailLabel(coachProfilePolicy),
    [coachProfilePolicy],
  );

  const playContextKey = `${effectiveAccountId ?? ''}|${coachProfilePolicy.profileId ?? 'none'}`;

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
      !(
        assistantPrefs.universe.includeMineStrategies ||
        assistantPrefs.universe.includeOptimizedStrategies
      ) || strategiesQuery.isFetched,
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
      queryKey: ['strategy', id] as const,
      queryFn: () => api.getStrategy(id),
      staleTime: 60_000,
      retry: false,
    })),
  });
  const missingFinalistKey = missingFinalistQueries
    .map((q) => q.data?.data?.id ?? '')
    .join(',');

  const runsQuery = useQuery({
    queryKey: ['backtests', zonePrefs.historyMaxKept],
    queryFn: () => api.getBacktests(zonePrefs.historyMaxKept),
  });

  const detailQuery = useQuery({
    queryKey: ['backtest', selectedId],
    queryFn: () => api.getBacktest(selectedId!),
    enabled: Boolean(selectedId),
  });

  const runMutation = useMutation({
    mutationFn: (overrides?: {
      instrumentId?: string;
      strategyDefinitionId?: string;
      initialCash?: number;
      timeframe?: ChartTimeframe;
      limit?: number;
      dateFrom?: string;
      dateTo?: string;
      labEvidence?: import('@bolsa/shared').PaperLabEvidenceSnapshot | null;
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
            : resolveBacktestWindow(periodPreset, customDateFrom, customDateTo, diaD);
      const nextInstrumentId = overrides?.instrumentId ?? instrumentId;
      const nextCash = overrides?.initialCash ?? Number(initialCash);
      const nextTf = overrides?.timeframe ?? runTimeframe;
      return api.runBacktest({
        instrumentId: nextInstrumentId,
        ...(overrides?.strategyDefinitionId
          ? { strategyDefinitionId: overrides.strategyDefinitionId }
          : runSource === 'saved'
            ? { strategyDefinitionId: savedStrategyId }
            : { strategyType }),
        initialCash: nextCash,
        commissionBps: Number(commissionBps) || 0,
        slippageBps: Number(slippageBps) || 0,
        timeframe: nextTf,
        ...window,
        ...(overrides?.labEvidence ? { labEvidence: overrides.labEvidence } : {}),
      });
    },
    onSuccess: (result) => {
      setBatchRows([]);
      setExploreRows([]);
      setResultFocus('detail');
      // Seed detail cache immediately so the chart does not wait on a second GET.
      queryClient.setQueryData(['backtest', result.data.id], { data: result.data });
      selectRun(result.data.id, { tab: 'run' });
      void pruneHistory(zonePrefs.historyMaxKept);
      void queryClient.invalidateQueries({ queryKey: ['research'] });
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
      setNewStrategyName('');
      setCloneOpen(false);
      openLibrary({ library: 'optimized' });
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const deployPaperMutation = useMutation({
    mutationFn: (payload: {
      strategyId: string;
      runId?: string;
      initialDeposit?: number;
      labEvidence?: import('@bolsa/shared').PaperLabEvidenceSnapshot | null;
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
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      navigate(`/accounts?type=paper&selected=${result.data.id}`, {
        state: {
          paperLabEvidence: result.data.labEvidence ?? null,
          paperDeployNote: 'Cuenta paper creada. Evidencia lab = provenance, no producción.',
        },
      });
    },
  });

  const saveChartStrategyMutation = useMutation({
    mutationFn: ({ draft, name }: { draft: ChartStrategySetupDraft; name: string }) => {
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
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
      setSavedStrategyId(result.data.id);
      setRunSource('saved');
      setTab('run');
    },
  });

  function applyChartDraft(draft: ChartStrategySetupDraft) {
    selectInstrument(draft.instrumentId);
    setUniverseMode('single');
    setRunTimeframe(draft.timeframe);
    if (draft.inferredPresetKey) {
      setRunSource('preset');
      setStrategyType(draft.inferredPresetKey);
      setMatrixSelectedIds(new Set([`preset:${draft.inferredPresetKey}`]));
      setMatrixFilter('preset');
      patchStrategyMatrixTablePrefs({ filter: 'preset' });
    }
  }

  const instruments = instrumentsQuery.data?.data ?? [];
  const lists = listsQuery.data?.data ?? [];
  const listDetail = listDetailQuery.data?.data;
  const listQuotes = listQuotesQuery.data?.data ?? [];
  const listTopsById = useMemo(() => {
    const map = new Map<string, import('@bolsa/shared').InstrumentStrategyTopV1>();
    for (const top of listTopsQuery.data?.data ?? []) {
      map.set(top.instrumentId, top);
    }
    return map;
  }, [listTopsQuery.data?.data]);
  const listFaById = useMemo(() => {
    const map = new Map<string, import('@bolsa/shared').FundamentalChipDto>();
    for (const row of listFaQuery.data?.data ?? []) {
      map.set(row.instrumentId, row);
    }
    return map;
  }, [listFaQuery.data?.data]);
  const listAutoPhaseById = useMemo(() => {
    const map = new Map<string, import('@/features/backtests/backtest-list-auto-board').ListAutoRowPhase>();
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
        instrumentIds: d.instrumentIds ?? d.definition?.universe?.instrumentIds ?? [],
        updatedAt: d.updatedAt,
        createdAt: d.createdAt,
      });
    }
    return [...byId.values()];
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
      .sort((a, b) => a.symbol.localeCompare(b.symbol, 'es'));
  }, [strategies, instrumentSymbolById]);

  const filteredStrategies = useMemo(() => {
    if (strategiesListFilter === 'generics') {
      return [];
    }
    const base =
      strategiesListFilter === 'finalists'
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

  const exploreOkCount = exploreRows.filter((r) => r.status === 'ok').length;
  const coachRunProgress = useMemo((): StrategyMatrixRunProgress => {
    const ok = exploreRows.filter((r) => r.status === 'ok').length;
    const error = exploreRows.filter((r) => r.status === 'error').length;
    const skipped = exploreRows.filter((r) => r.status === 'skipped').length;
    const runningLabels = exploreRows
      .filter((r) => r.status === 'running')
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
    universe: isAssistantStepComplete('universe', assistantProgress),
    semifinal: isAssistantStepComplete('semifinal', assistantProgress),
    lab: isAssistantStepComplete('lab', assistantProgress),
    finalists: isAssistantStepComplete('finalists', assistantProgress),
  };
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
  ].join('|');
  const matrixFingerprintRef = useRef(matrixRunFingerprint);
  const lastBatteryFingerprintRef = useRef<string | null>(null);
  useEffect(() => {
    if (matrixFingerprintRef.current === matrixRunFingerprint) return;
    matrixFingerprintRef.current = matrixRunFingerprint;
    lastBatteryFingerprintRef.current = null;
    setMatrixRows((prev) =>
      prev.map((row) => ({
        ...row,
        status: 'idle',
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
  // Never fall back to a stale mutation run when viewing another selectedId (ranking → detalle).
  const rawDetail =
    (detailQuery.data?.data?.id === selectedId ? detailQuery.data.data : undefined) ??
    (runMutation.data?.data?.id === selectedId ? runMutation.data.data : undefined);
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
    () => resolveMatrixCoachTargetIds(matrixRowsForUi, matrixFilter, matrixSelectedIds),
    [matrixRowsForUi, matrixFilter, matrixSelectedIds],
  );

  // Al elegir un valor: Detalle con vista previa (gráfico + B&H).
  function selectInstrument(
    id: string,
    opts?: { forceClear?: boolean; preserveListAutoFocus?: boolean; skipUrl?: boolean },
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
      setCoachPass('initial');
      setOptimizeCompare(null);
      lastBatteryFingerprintRef.current = null;
      setAssistantProgress(emptyAssistantProgress());
      setAwaitingAck(false);
      setAwaitingAckStage(null);
      setLabImprovedThisCycle(0);
      setSemifinalShortcutArmed(false);
      setLabOpenedThisRun(false);
      assistantChainRef.current = '';
      setAssistantFocus(null);
      if (fullCycleActive && !listAutoRef.current) {
        setFullCycleActive(false);
        setAssistantStatus('Instrumento cambiado · ciclo reiniciado. Pulsa Play.');
      }
    }
    setSelectedId(null);
    setInstrumentId(id);
    if (!opts?.preserveListAutoFocus) {
      setResultFocus('detail');
    }
    setTab('run');
    if (!opts?.skipUrl) {
      patchSearchParams((params) => {
        if (id) params.set('instrumentId', id);
        else params.delete('instrumentId');
        params.delete('runId');
        params.set('tab', 'run');
        if (!opts?.preserveListAutoFocus) {
          params.set('focus', 'detail');
        }
      });
    }
  }

  /** Desde lista / tablero AUTO / ranking → pestaña Universo Valor + Detalle. */
  function openInstrumentInValor(
    id: string,
    opts?: { runId?: string | null; soft?: boolean },
  ) {
    if (!id) return;
    const campaignLive = Boolean(listAutoRef.current && !listAutoRef.current.aborted);
    const soft = Boolean(opts?.soft) || campaignLive;
    setUniverseMode('single');
    if (soft) {
      // No tumba ranking / campaña AUTO: solo cambia el valor activo.
      setInstrumentId(id);
      setSelectedId(opts?.runId ?? null);
      setResultFocus('detail');
      setTab('run');
    } else {
      selectInstrument(id, { skipUrl: true });
      if (opts?.runId) setSelectedId(opts.runId);
      setResultFocus('detail');
    }
    patchSearchParams((params) => {
      params.set('instrumentId', id);
      params.set('focus', 'detail');
      params.set('tab', 'run');
      if (opts?.runId) params.set('runId', opts.runId);
      else params.delete('runId');
    });
  }

  async function runListBatch() {
    if (!listDetail?.instrumentIds.length) {
      setBatchError('La lista no tiene valores.');
      return;
    }
    if (runSource === 'saved' && !savedStrategyId) {
      setBatchError('Elige una estrategia guardada.');
      return;
    }
    if (periodPreset === 'custom' && (!customDateFrom || !customDateTo)) {
      setBatchError('Indica fechas desde/hasta.');
      return;
    }

    batchAbortRef.current?.abort();
    const controller = new AbortController();
    batchAbortRef.current = controller;
    setBatchError(null);
    setExploreRows([]);
    setBatchRunning(true);
    setResultFocus('ranking');
    setBatchProgress({ done: 0, total: listDetail.instrumentIds.length });

    try {
      const rows = await runBacktestBatch({
        instrumentIds: listDetail.instrumentIds,
        labels: instrumentLabels,
        ...(runSource === 'saved'
          ? { strategyDefinitionId: savedStrategyId }
          : { strategyType }),
        initialCash: Number(initialCash),
        commissionBps: Number(commissionBps) || 0,
        slippageBps: Number(slippageBps) || 0,
        timeframe: runTimeframe,
        window: resolveBacktestWindow(periodPreset, customDateFrom, customDateTo, diaD),
        signal: controller.signal,
        onProgress: (next, done, total) => {
          setBatchRows(next);
          setBatchProgress({ done, total });
        },
        onRunComplete: seedBacktestDetail,
      });
      setBatchRows(rows);
      setSelectedId(null);
      setResultFocus('ranking');
      patchSearchParams((params) => {
        params.delete('runId');
        params.set('tab', 'run');
      });
      pruneAfterBatch(rows.filter((r) => r.status === 'ok').length);
      void queryClient.invalidateQueries({ queryKey: ['research'] });
    } catch (error) {
      setBatchError(error instanceof Error ? error.message : 'Error en la batería');
    } finally {
      setBatchRunning(false);
      batchAbortRef.current = null;
    }
  }

  useEffect(() => {
    return () => {
      batchAbortRef.current?.abort();
      // Si Lista AUTO sigue activa (keep-alive en PlatformShell), no abortar explore.
      if (useListAutoActivityStore.getState().active) return;
      exploreAbortRef.current?.abort();
    };
  }, []);

  /** Publica resumen Lista AUTO → barra Trading / badge nav (y keep-alive). */
  useEffect(() => {
    const board = listAutoBoard;
    const campaignLive = Boolean(
      listAutoRef.current && !listAutoRef.current.aborted,
    );
    const boardLive = Boolean(board && !board.done && !board.aborted);
    const active = campaignLive || boardLive || Boolean(listAutoUi);

    if (!active) {
      if (useListAutoActivityStore.getState().active) {
        useListAutoActivityStore.getState().clear();
      }
      return;
    }

    const index =
      listAutoUi?.index ??
      board?.rows.findIndex((r) => r.phase === 'running') ??
      0;
    const total =
      listAutoUi?.total ||
      board?.rows.length ||
      listAutoRef.current?.instrumentIds.length ||
      0;
    const symbol =
      listAutoUi?.symbol ||
      (index >= 0 && board?.rows[index]?.symbol) ||
      '…';

    useListAutoActivityStore.getState().publish({
      active: true,
      paused: Boolean(board?.paused || listAutoRef.current?.paused),
      listId: board?.listId ?? listId ?? null,
      listName: listDetail?.name ?? null,
      index: Math.max(0, index),
      total: Math.max(total, 1),
      symbol,
      detail: assistantStatus,
    });
  }, [
    listAutoBoard,
    listAutoUi,
    assistantStatus,
    listId,
    listDetail?.name,
  ]);

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
  function applyMatrixSelection(mode: 'replace' | 'add' | 'remove', rowIds: string[]) {
    setMatrixSelectedIds((prev) => {
      if (mode === 'replace') {
        return new Set(rowIds.slice(0, STRATEGY_MATRIX_MAX_SELECTED));
      }
      const next = new Set(prev);
      if (mode === 'remove') {
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

  function enrichExplorePeriodReturns(rows: ExplorePresetRow[]): ExplorePresetRow[] {
    return rows.map((row) => {
      if (!row.runId || row.periodReturns) return row;
      const cached = queryClient.getQueryData<{
        data?: { equityCurve?: import('@bolsa/shared').BacktestEquityPointDto[] };
      }>(['backtest', row.runId]);
      return {
        ...row,
        periodReturns: periodReturnsFromEquity(cached?.data?.equityCurve),
      };
    });
  }

  function exploreRowsFromMatrix(
    next: StrategyMatrixRow[],
    targetIds: ReadonlySet<string>,
  ): ExplorePresetRow[] {
    return enrichExplorePeriodReturns(
      matrixRowsToExploreRows(next.filter((row) => targetIds.has(row.rowId))),
    );
  }

  /**
   * Batería → matriz + Coach.
   * - Botón UI: ids del filtro/selección actual (no cambia el filtro).
   * - Asistente Universo: genéricas (± Mis estrategias según prefs).
   * - Reutiliza lote si fingerprint coincide y prefs.reuseLoteIfUnchanged.
   */
  async function runCoachBattery(
    targetRowIds: string[],
    opts?: {
      lockFilterToPreset?: boolean;
      lockFilter?: 'preset' | 'all';
      /** Filas extra (p. ej. Mejores Lab recién creados) no aún en matrixRowsForUi. */
      extraRows?: StrategyMatrixRow[];
      pass?: 'initial' | 'post_lab';
      /** Se fusionan tras la batería (avisos sin re-score). */
      carryRows?: ExplorePresetRow[];
      markLabImproved?: boolean;
      forceResim?: boolean;
    },
  ): Promise<{ okCount: number; error?: string }> {
    if (!instrumentId) {
      setExploreError('Elige un valor.');
      return { okCount: 0, error: 'Elige un valor.' };
    }
    if (periodPreset === 'custom' && (!customDateFrom || !customDateTo)) {
      setExploreError('Indica fechas desde/hasta.');
      return { okCount: 0, error: 'Indica fechas desde/hasta.' };
    }
    if (targetRowIds.length === 0 && !(opts?.carryRows?.length)) {
      const err =
        matrixFilter === 'finalists'
          ? 'No hay finalistas en este valor. Guarda un TOP desde Coach o cambia de filtro.'
          : matrixFilter === 'mine'
            ? 'No hay estrategias en Mis estrategias (o ninguna seleccionada).'
            : matrixFilter === 'optimized'
              ? 'No hay Optimizadas seleccionadas en este filtro.'
            : matrixFilter === 'preset'
              ? 'No hay genéricas seleccionadas en este filtro.'
              : 'No hay estrategias para probar en este filtro.';
      setExploreError(err);
      return { okCount: 0, error: err };
    }

    exploreAbortRef.current?.abort();
    batchAbortRef.current?.abort();
    const controller = new AbortController();
    exploreAbortRef.current = controller;
    setExploreError(null);
    setBatchRows([]);
    setResultFocus('coach');
    setCoachPass(opts?.pass ?? 'initial');
    const lock = opts?.lockFilter ?? (opts?.lockFilterToPreset ? 'preset' : undefined);
    if (lock === 'preset') {
      setMatrixFilter('preset');
      patchStrategyMatrixTablePrefs({ filter: 'preset' });
    } else if (lock === 'all') {
      setMatrixFilter('all');
      patchStrategyMatrixTablePrefs({ filter: 'all' });
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
      opts?.pass === 'post_lab';
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
      setExploreProgress({ done: targetRowIds.length, total: Math.max(1, targetRowIds.length) });
      const explore = [
        ...exploreRowsFromMatrix(batteryRows, targetSet).map((r) =>
          opts?.markLabImproved ? { ...r, labPass: 'lab_improved' as const } : r,
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
        params.delete('runId');
        params.set('tab', 'run');
      });
      return { okCount: explore.filter((r) => r.status === 'ok').length };
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
          window: resolveBacktestWindow(periodPreset, customDateFrom, customDateTo, diaD),
          concurrency: 4,
          signal: controller.signal,
          onProgress: (next, progress) => {
            setMatrixRows(next);
            setExploreProgress({ done: progress.done, total: progress.total });
            const partial = exploreRowsFromMatrix(next, targetSet).map((r) =>
              opts?.markLabImproved ? { ...r, labPass: 'lab_improved' as const } : r,
            );
            setExploreRows([...partial, ...(opts?.carryRows ?? [])]);
          },
          onRunComplete: seedBacktestDetail,
        });
        setMatrixRows(rows);
        explore = [
          ...exploreRowsFromMatrix(rows, targetSet).map((r) =>
            opts?.markLabImproved ? { ...r, labPass: 'lab_improved' as const } : r,
          ),
          ...(opts?.carryRows ?? []),
        ];
        pruneAfterBatch(rows.filter((r) => targetSet.has(r.rowId) && r.status === 'ok').length);
        lastBatteryFingerprintRef.current = fingerprint;
      }
      setExploreRows(explore);
      setSelectedId(null);
      setResultFocus('coach');
      patchSearchParams((params) => {
        params.delete('runId');
        params.set('tab', 'run');
      });
      void queryClient.invalidateQueries({ queryKey: ['research'] });
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
      return { okCount: explore.filter((r) => r.status === 'ok').length };
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Error en la exploración';
      setExploreError(msg);
      lastBatteryFingerprintRef.current = null;
      return { okCount: 0, error: msg };
    } finally {
      setExploreRunning(false);
      exploreAbortRef.current = null;
    }
  }

  /** Lab → Coach²: re-simula Mejores; carries van sin re-score. */
  async function reanalyzeLabWithCoach(payload: LabReanalyzeRequest) {
    if (!instrumentId) {
      setAssistantStatus('Elige un valor antes de reanalizar.');
      return;
    }
    await queryClient.invalidateQueries({ queryKey: ['strategies'] });

    const extraRows: StrategyMatrixRow[] = payload.improved.map((item) => ({
      rowId: `saved:${item.strategyId}`,
      kind: 'saved' as const,
      label: item.label,
      subtitle: 'Lab · Mejor',
      // Identidad explore/coach = tipo Coach original (evita colapsar 2 proxies SMA en 1).
      // El preset ejecutable va en la def; buildCoachTopSlots/sanitize lo usan al grabar TOP.
      presetKey: (item.strategyType ?? item.presetKey ?? undefined) as
        | BacktestStrategyType
        | undefined,
      strategyDefinitionId: item.strategyId,
      origin: 'preset',
      savedBucket: 'optimized' as const,
      status: 'idle' as const,
    }));

    const carryRows: ExplorePresetRow[] = payload.carried.map((c) => {
      const strategyType = (c.strategyType ?? 'sma_crossover') as BacktestStrategyType;
      const meta = BACKTEST_STRATEGIES[strategyType];
      const category = meta?.category ?? 'trend';
      return {
        strategyType,
        label: `${c.label} · no mejoró en Lab`,
        category,
        categoryLabel: STRATEGY_PRESET_CATEGORY_LABELS[category] ?? category,
        status: 'ok' as const,
        labPass: 'lab_carry' as const,
      };
    });

    setAssistantStatus(
      `Reanalizando ${payload.improved.length} Mejor(es) Lab con Coach` +
        (payload.carried.length ? ` · ${payload.carried.length} aviso(s) sin mejora` : '') +
        '…',
    );

    setLabImprovedThisCycle(payload.improved.length);
    setResultFocus('coach');
    await runCoachBattery(
      payload.improved.map((i) => `saved:${i.strategyId}`),
      {
        extraRows,
        pass: 'post_lab',
        carryRows,
        markLabImproved: true,
      },
    );
    setAssistantProgress((p) => ({ ...p, labDone: true }));
    if (fullCycleActive) {
      setAssistantStatus(
        payload.improved.length
          ? 'Ciclo: Coach² listo · evaluando Finalistas…'
          : 'Ciclo: Lab sin Mejor guardable. No se pisan Finalistas active.',
      );
    } else {
      setAssistantStatus(
        payload.improved.length
          ? 'Coach tras Lab listo. Revisa ★ y guarda Finalistas si te convencen.'
          : 'Coach: solo avisos sin mejora. Optimiza de nuevo en Lab o cambia de candidatas.',
      );
    }
  }

  /** Asistente / revalidar: genéricas ∪ Finalistas (± Optimizadas ± Mis). */
  async function runExploreValue(): Promise<{ okCount: number; error?: string }> {
    setCoachPass('initial');
    const includeOptimized = assistantPrefs.universe.includeOptimizedStrategies;
    const includeMine = assistantPrefs.universe.includeMineStrategies;
    const includeFinalists = assistantPrefs.universe.includeFinalistsInBattery;
    const optimizedIds = matrixRowsForUi
      .filter((r) => r.kind === 'saved' && r.savedBucket === 'optimized')
      .map((r) => r.rowId);
    const mineIds = matrixRowsForUi
      .filter((r) => r.kind === 'saved' && r.savedBucket === 'mine')
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
          ? 'all'
          : 'preset',
    });
  }

  /** Botón matriz: respeta filtro actual y selección. */
  async function runCoachFromMatrixUi(opts?: { forceResim?: boolean }) {
    if (opts?.forceResim) {
      lastBatteryFingerprintRef.current = null;
      setAssistantStatus('Coach: forzando re-sim del lote…');
    }
    await runCoachBattery(matrixCoachTargetIds, { forceResim: opts?.forceResim });
  }

  const linkedTrialQuery = useQuery({
    queryKey: ['research', 'by-run', detail?.id],
    queryFn: () =>
      api.getResearchTrials({
        backtestRunId: detail!.id,
        limit: 1,
        sort: 'created_at',
        sortDir: 'desc',
      }),
    enabled: Boolean(detail?.id),
  });
  const linkedTrial = linkedTrialQuery.data?.data?.[0];
  const freshRun = runMutation.data?.data?.id === detail?.id ? runMutation.data : undefined;
  const displayTrialId = freshRun?.trialId ?? linkedTrial?.id;
  const displayMetrics = freshRun?.metrics ?? linkedTrial?.isMetrics;

  const replayBarsQuery = useQuery({
    queryKey: [
      'backtest-replay-ohlcv',
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
        detail!.timeframe ?? '1d',
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
      document.getElementById('backtest-replay')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    });
  }

  const focusedTrade = useMemo(
    () => detail?.trades.find((trade) => trade.timestamp === focusTimestamp) ?? null,
    [detail?.trades, focusTimestamp],
  );
  const replayRunBars = useMemo(() => {
    const bars = replayBarsQuery.data?.data;
    if (!bars || !detail) return [];
    return bars.filter(
      (bar) => bar.timestamp >= detail.firstDate && bar.timestamp <= detail.lastDate,
    );
  }, [detail, replayBarsQuery.data?.data]);

  const drawingReplayQuery = useQuery({
    queryKey: [
      'drawing-replay',
      detail?.id,
      replayDrawings?.map((drawing) => drawing.id).join(','),
    ],
    queryFn: () =>
      api.replayDrawings({
        bars: replayRunBars,
        drawings: replayDrawings!,
      }),
    enabled: Boolean(
      detail && replayDrawings && replayDrawings.length > 0 && replayRunBars.length >= 2,
    ),
  });

  const drawingMarkers = drawingReplayQuery.data?.data ?? [];

  const strategyMeta =
    runSource === 'preset' && strategyType
      ? BACKTEST_STRATEGIES[strategyType]
      : null;

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

  function patchSearchParams(
    mutate: (params: URLSearchParams) => void,
    opts?: { replace?: boolean },
  ) {
    // Keep-alive fuera de /backtests: no pisar la URL de Trading/otros hubs.
    if (!pathname.startsWith('/backtests')) return;
    const next = new URLSearchParams(searchParams);
    mutate(next);
    setSearchParams(next, { replace: opts?.replace });
  }

  /** Abre Biblioteca con filtro / foco (entra en historial ←→). */
  function openLibrary(opts?: {
    library?: StrategiesListFilter;
    strategyId?: string | null;
    preset?: string | null;
    q?: string | null;
  }) {
    const library = opts?.library ?? 'mine';
    setStrategiesListFilter(library);
    setLibraryFocusStrategyId(opts?.strategyId ?? null);
    setLibraryFocusPreset(opts?.preset ?? null);
    if (opts?.q != null) {
      setMineFilters((prev) => ({ ...prev, query: opts.q ?? '' }));
    }
    patchSearchParams((params) => {
      params.set('tab', 'strategies');
      params.set('library', library);
      if (opts?.strategyId) params.set('strategyId', opts.strategyId);
      else params.delete('strategyId');
      if (opts?.preset) params.set('preset', opts.preset);
      else params.delete('preset');
      if (opts?.q?.trim()) params.set('q', opts.q.trim());
      else if (opts?.q === '') params.delete('q');
    });
  }

  function setLibraryFilter(next: StrategiesListFilter) {
    setStrategiesListFilter(next);
    setLibraryFocusStrategyId(null);
    setLibraryFocusPreset(null);
    patchSearchParams((params) => {
      params.set('tab', 'strategies');
      params.set('library', next);
      params.delete('strategyId');
      params.delete('preset');
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
    setTab('run');
    setResultFocus('lab');
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
    setTab('run');
    setResultFocus('lab');
  }

  function startOptimizeFromExplore(row: ExplorePresetRow, source: OptimizeSeed['source']) {
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

  async function optimizeSemifinalFromCoach(
    candidates: Array<{
      row: ExplorePresetRow;
      stars?: number;
      starsCapped?: boolean;
      rank?: number;
    }>,
  ): Promise<'opened' | 'skipped'> {
    if (!instrumentId) {
      setAssistantStatus('Elige un valor antes de optimizar la semifinal.');
      return 'skipped';
    }
    const symbol =
      instrumentLabels[instrumentId]?.symbol ??
      instruments.find((inst) => inst.id === instrumentId)?.symbol;
    const top3 = candidates.slice(0, 3);
    const withGrid = top3.filter((c) => isOptimizableStrategy(c.row.strategyType));
    const skipped = top3.filter((c) => !isOptimizableStrategy(c.row.strategyType));

    if (withGrid.length === 0) {
      const msg = skipped.length
        ? `Ninguna de las ${skipped.length} candidatas tiene grid nativo (p. ej. Bollinger). Guarda TOP semifinal o elige otras.`
        : 'No hay candidatas para el laboratorio.';
      setAssistantStatus(msg);
      if (fullCycleActive || listAutoRef.current) {
        settleFullCycle('skip_lab', universeEmptyStatus(msg));
      }
      return 'skipped';
    }

    setSemifinalEnqueuePending(true);
    setAssistantStatus(null);
    const zones: LabBoardZone[] = [];
    const errors: string[] = [];
    try {
      for (let i = 0; i < withGrid.length; i++) {
        const cand = withGrid[i]!;
        const row = cand.row;
        const rank = ((i + 1) as 1 | 2 | 3);
        const seed = buildOptimizeSeedFromExploreRow(row, {
          instrumentId,
          symbol,
          initialCash: Number(initialCash) || 10_000,
          timeframe: runTimeframe,
          barLimit: row.barCount,
          source: 'explore_best',
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
              errors.push(`${row.label} (${body.engine ?? 'job'})`);
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
        ? ` · omitidas sin grid: ${skipped.map((c) => c.row.label).join(', ')}`
        : '';
      const errNote = errors.length ? ` · fallos: ${errors.join(', ')}` : '';
      const queued = zones.reduce((n, z) => n + (z.jobIds?.length ?? (z.jobId ? 1 : 0)), 0);
      const smaDual = zones.some((z) => (z.jobIds?.length ?? 0) > 1);
      setAssistantStatus(
        `Lab: ${zones.length} zona(s)${
          queued ? ` · ${queued} job(s) en curso${smaDual ? ' (H0+Optuna)' : ''}` : ''
        }${skipNote}${errNote}. Adopta solo si Mejor ≥ ancla (OOS).`,
      );
      if (queued > 0) setSemifinalJobsQueued(true);
      if (zones.length > 0 && queued > 0) {
        openLabBoard(zones);
        return 'opened';
      }
      // Zonas sin jobs encolados → el board las marcaría terminal al instante;
      // cerramos aquí para no dejar «Lab en curso» colgado.
      setLabOpenedThisRun(true);
      setTab('run');
      setResultFocus('lab');
      if (fullCycleActive || listAutoRef.current) {
        settleFullCycle(
          'skip_lab',
          universeEmptyStatus(errors.length ? errors.join(', ') : 'sin jobs Lab'),
        );
      }
      return 'skipped';
    } catch {
      if (fullCycleActive || listAutoRef.current) {
        settleFullCycle('skip_lab', universeEmptyStatus('error Lab enqueue'));
      }
      return 'skipped';
    } finally {
      setSemifinalEnqueuePending(false);
    }
  }

  function startOptimizeFromDetail() {
    if (!detail) return;
    const excess =
      typeof displayMetrics?.excessReturnPct === 'number'
        ? displayMetrics.excessReturnPct
        : typeof linkedTrial?.isMetrics?.excessReturnPct === 'number'
          ? linkedTrial.isMetrics.excessReturnPct
          : null;
    const seed = buildOptimizeSeedFromRun({
      instrumentId: detail.instrumentId,
      symbol: detail.symbol,
      strategyType: detail.strategyType,
      strategyLabel:
        BACKTEST_STRATEGIES[detail.strategyType]?.label ?? detail.name ?? detail.strategyType,
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

  function setTab(next: HubTab) {
    patchSearchParams((params) => {
      params.set('tab', next);
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
      params.set('runId', id);
      params.set('tab', options?.tab ?? 'run');
      if (options?.focus) params.set('focus', options.focus);
      if (options?.openAnalysis) params.set('openAnalysis', '1');
      else params.delete('openAnalysis');
      // Ver / checklist = Análisis técnico normal (no Verificar D→hoy).
      params.delete('verify');
    });
  }

  /** Finalistas → Detalle + checklist (Camino A). Sin re-Lab ni deploy directo. */
  function openFinalistChecklist(slot: {
    strategyDefinitionId: string;
    runId?: string | null;
    label?: string;
  }) {
    setSavedStrategyId(slot.strategyDefinitionId);
    setRunSource('saved');
    if (instrumentId && effectiveAccountId) {
      setAdoption({
        instrumentId,
        accountId: effectiveAccountId,
        state: 'adoptada',
        strategyDefinitionId: slot.strategyDefinitionId,
        strategyLabel: slot.label ?? null,
        timeframe: runTimeframe,
      });
    }
    if (slot.runId) {
      selectRun(slot.runId, { tab: 'run', openAnalysis: true, focus: 'detail' });
      setAssistantStatus(PAPER_PATH_LAB.finalistsHint);
      return;
    }
    setPreferOpenAnalysis(false);
    setResultFocus('detail');
    setAssistantStatus(
      'Este Finalista no tiene run guardado. Usa Usar → Probar (genera resultado) y luego Checklist.',
    );
  }

  const proposeFinalistMutation = useMutation({
    mutationFn: async (slot: {
      strategyDefinitionId: string;
      label: string;
    }) => {
      if (!instrumentId) throw new Error('Elige un valor');
      if (!effectiveAccountId) throw new Error('Selecciona una cuenta activa (perfil FA)');
      const symbol =
        instrumentLabels[instrumentId]?.symbol ??
        instruments.find((i) => i.id === instrumentId)?.symbol ??
        'Valor';
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
          state: 'propuesta',
          strategyDefinitionId: slot.strategyDefinitionId,
          strategyLabel: slot.label,
          timeframe: runTimeframe,
        });
      }
      const id = enqueueSupervised(payload, {
        symbol: payload.symbol ?? undefined,
        origin: 'finalists',
      });
      setActiveSupervised(id);
      const msg = `${PAPER_PATH_SUPERVISED.shortTitle}: ${slot.label} → ${payload.action} · revisa Supervisado F3`;
      setAssistantStatus(msg);
      pushToast(msg);
      openHelpAiPlatform({ panel: 'supervised-f3' });
    },
    onError: (err: Error) => {
      setAssistantStatus(err.message || 'No se pudo proponer al Supervisado F3');
      pushToast(err.message || 'Error al proponer Finalista');
    },
  });

  function proposeFinalistSupervisedSlot(slot: {
    strategyDefinitionId: string;
    label: string;
  }) {
    proposeFinalistMutation.mutate(slot);
  }

  // Deep-link: ?focus=finalists|coach|lab|detail|fundamental (solo en /backtests)
  useEffect(() => {
    if (!onBacktestsRoute) return;
    const focus = searchParams.get('focus');
    if (
      focus === 'coach' ||
      focus === 'lab' ||
      focus === 'finalists' ||
      focus === 'detail' ||
      focus === 'fundamental' ||
      focus === 'ranking' ||
      focus === 'list_auto'
    ) {
      setResultFocus(focus);
    }
  }, [searchParams, onBacktestsRoute]);

  // ADR-019 U2: ?verify=1 → Análisis técnico + host Verificar (sesión LAB)
  useEffect(() => {
    if (!onBacktestsRoute) return;
    if (searchParams.get('verify') !== '1') return;
    setTab('run');
    setResultFocus('detail');
  }, [searchParams, onBacktestsRoute]);

  // Si la URL pide verify pero no hay sesión LAB, quitar el flag (evita pantallas rotas).
  useEffect(() => {
    if (!onBacktestsRoute) return;
    if (searchParams.get('verify') !== '1') return;
    if (diaDVerifySession) return;
    patchSearchParams((params) => {
      params.delete('verify');
    });
  }, [searchParams, onBacktestsRoute, diaDVerifySession]);

  // Deep-link Biblioteca: ?tab=strategies&library=&strategyId=&preset=&q=
  useEffect(() => {
    if (!onBacktestsRoute) return;
    const nav = parseLibraryNavFromSearch(searchParams);
    if (!nav) {
      setLibraryFocusStrategyId(null);
      setLibraryFocusPreset(null);
      return;
    }
    setStrategiesListFilter(nav.library);
    setLibraryFocusStrategyId(nav.strategyId ?? null);
    setLibraryFocusPreset(nav.preset ?? null);
    if (nav.q != null) {
      setMineFilters((prev) =>
        prev.query === nav.q ? prev : { ...prev, query: nav.q ?? '' },
      );
    }
  }, [searchParams, onBacktestsRoute]);

  // Deep-link: ?focus=monitor → abrir Monitor Finalistas (CORE-R cola)
  useEffect(() => {
    if (!onBacktestsRoute) return;
    if (searchParams.get('focus') !== 'monitor') return;
    setTab('run');
    const id = window.setTimeout(() => {
      const el = document.getElementById('strategy-monitor-hub');
      const details = el?.closest('details');
      if (details) details.open = true;
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 120);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, onBacktestsRoute]);

  // Deep-link: ?openAnalysis=1 (+ runId) → abrir checklist paper (Camino A).
  useEffect(() => {
    if (!onBacktestsRoute || !runIdFromUrl) return;
    if (isOpenAnalysisQuery(searchParams.get('openAnalysis'))) {
      setPreferOpenAnalysis(true);
    }
  }, [searchParams, runIdFromUrl, onBacktestsRoute]);

  useEffect(() => {
    if (!onBacktestsRoute) return;
    const fromUrl = searchParams.get('instrumentId');
    if (fromUrl && fromUrl !== instrumentId) {
      setInstrumentId(fromUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, onBacktestsRoute]);

  // Deep-link: /backtests?listId=… (hub Listas → Backtesting).
  const appliedListIdFromUrlRef = useRef(false);
  useEffect(() => {
    if (!onBacktestsRoute || appliedListIdFromUrlRef.current) return;
    const fromUrl = searchParams.get('listId')?.trim();
    if (!fromUrl) return;
    const lists = listsQuery.data?.data ?? [];
    if (!listsQuery.isSuccess) return;
    if (!lists.some((list) => list.id === fromUrl)) return;
    appliedListIdFromUrlRef.current = true;
    setUniverseMode('list');
    setListId(fromUrl);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete('listId');
        if (!next.get('tab')) next.set('tab', 'run');
        return next;
      },
      { replace: true },
    );
  }, [onBacktestsRoute, searchParams, listsQuery.isSuccess, listsQuery.data, setSearchParams]);

  // Deep-link: /backtests?runId=… (Research → resultado).
  // Solo reacciona a cambios de la URL — no re-aplicar un runId viejo cuando
  // selectInstrument ya puso selectedId=null y el patch de URL aún no ha llegado.
  useEffect(() => {
    if (!onBacktestsRoute || !runIdFromUrl) return;
    setSelectedId((prev) => (prev === runIdFromUrl ? prev : runIdFromUrl));
  }, [runIdFromUrl, onBacktestsRoute]);

  useEffect(() => {
    if (!runIdFromUrl || !detail?.id || detail.id !== runIdFromUrl) return;
    const el = document.getElementById('backtest-result');
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [runIdFromUrl, detail?.id]);

  function goAssistantStep(step: AssistantStepId) {
    setTab('run');
    if (step === 'universe') {
      setResultFocus(detail || selectedId ? 'detail' : exploreRows.length > 0 ? 'coach' : 'detail');
      return;
    }
    if (step === 'semifinal') {
      setResultFocus('coach');
      return;
    }
    if (step === 'lab') {
      setLabOpenedThisRun(true);
      setResultFocus('lab');
      return;
    }
    setStrategiesListFilter('finalists');
    setResultFocus('finalists');
  }

  /** Play: paso a paso, ciclo 1 valor, o lista AUTO (lista + ciclo completo). */
  async function playAssistantSequence() {
    if (
      shouldStartListAuto({
        universeMode,
        fullCycleOnPlay: assistantPrefs.fullCycleOnPlay,
        listId,
        instrumentCount: listDetail?.instrumentIds.length ?? 0,
      })
    ) {
      if (listAutoRef.current && !listAutoRef.current.aborted) {
        setAssistantStatus('Lista AUTO ya en curso. Usa ↻ para cancelar.');
        return;
      }
      const instrumentIds = listDetail!.instrumentIds;

      let queueIds = instrumentIds;
      if (listAutoSkipWithFinalists) {
        setAssistantStatus('Lista AUTO: filtrando valores sin Finalistas…');
        queueIds = await filterListAutoIdsWithoutFinalists(instrumentIds, (id) =>
          api.getInstrumentStrategyTop(id, runTimeframe),
        );
        if (queueIds.length === 0) {
          setAssistantStatus('Lista AUTO: todos tienen Finalistas (nada que encolar).');
          return;
        }
      }
      if (!confirmListAutoOverCap(queueIds.length)) {
        setAssistantStatus('Lista AUTO cancelada (soft-cap).');
        return;
      }
      const campaign = createListAutoCampaign({
        listId,
        instrumentIds: queueIds,
      });
      if (campaign.instrumentIds.length === 0) {
        setAssistantStatus('La lista no tiene valores.');
        return;
      }

      // Resolver tickers vía quotes de lista (catálogo global puede no tener SP100 recién importado).
      const labels: Record<string, { symbol: string; name: string }> = { ...instrumentLabels };
      const missing = campaign.instrumentIds.filter((id) => !labels[id]?.symbol);
      if (missing.length > 0) {
        setAssistantStatus('Lista AUTO: cargando tickers de la lista…');
        try {
          const res = await api.getListQuotes(listId);
          queryClient.setQueryData(['list-quotes', listId], res);
          for (const q of res.data) {
            labels[q.id] = { symbol: q.symbol, name: q.name };
          }
          void queryClient.invalidateQueries({ queryKey: ['instruments'] });
        } catch {
          /* seguimos con fallback; enrich posterior puede corregir */
        }
      }
      const resolveSym = (id: string) => labels[id]?.symbol ?? id.slice(0, 8);
      const resolveName = (id: string) => labels[id]?.name;

      const cont = matchListAutoContinueSnapshot(loadListAutoContinueSnapshot(), {
        listId: campaign.listId,
        instrumentIds: campaign.instrumentIds,
      });
      const startIndex = cont?.nextIndex ?? 0;
      if (cont?.freshnessMemory) {
        listAutoFreshnessMemoryRef.current = new Map(Object.entries(cont.freshnessMemory));
      }

      listAutoRef.current = campaign;
      clearPersistedListAutoPause();
      // No borramos continue hasta completar o ↻: otro Stop debe poder re-guardar.
      const board = cont
        ? enrichListAutoBoardLabels(boardFromContinueSnapshot(cont), labels)
        : createListAutoBoard({
            listId: campaign.listId,
            instruments: campaign.instrumentIds.map((id) => ({
              instrumentId: id,
              symbol: resolveSym(id),
              name: resolveName(id),
            })),
          });
      setListAutoBoard(board);
      setResultFocus('list_auto');
      const startSym = resolveSym(campaign.instrumentIds[startIndex]!);
      setAssistantStatus(
        cont
          ? `Lista AUTO: continúa desde #${startIndex + 1} ${startSym} (tras Stop) · ${campaign.instrumentIds.length} valor(es)…`
          : `Lista AUTO: ${campaign.instrumentIds.length} valor(es)` +
              (listDetail!.instrumentIds.length > LIST_AUTO_MAX_INSTRUMENTS
                ? ` (máx. ${LIST_AUTO_MAX_INSTRUMENTS})`
                : '') +
              '…',
      );
      queueListAutoTicker(startIndex);
      return;
    }

    const next = ASSISTANT_STEPS.find((s) => !assistantStepComplete[s.id]);
    if (!next) {
      setFullCycleActive(false);
      setAssistantStatus(
        'Asistente completo. Revisa Análisis técnico / fundamental / Coach / Lab / Finalistas.',
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

  function symbolForInstrument(id: string): string {
    return (
      instrumentLabels[id]?.symbol ??
      instruments.find((i) => i.id === id)?.symbol ??
      id.slice(0, 8)
    );
  }

  // Si las quotes llegan después de crear el tablero, corrige columna VALOR.
  useEffect(() => {
    setListAutoBoard((prev) => (prev ? enrichListAutoBoardLabels(prev, instrumentLabels) : prev));
  }, [instrumentLabels]);

  /** Prepara un ticker de la campaña y encola el arranque del ciclo (tras setState). */
  function queueListAutoTicker(index: number) {
    const campaign = listAutoRef.current;
    if (!campaign || campaign.aborted) return;
    listAutoSettleLockRef.current = null;
    if (index >= campaign.instrumentIds.length) {
      const total = campaign.instrumentIds.length;
      listAutoRef.current = null;
      listAutoPendingStartRef.current = null;
      setListAutoUi(null);
      setListAutoBoard((b) => (b ? markListAutoBoardDone(b) : null));
      setFullCycleActive(false);
      clearListAutoContinueSnapshot();
      clearPersistedListAutoPause();
      setAssistantStatus(listAutoDoneStatus(total));
      setResultFocus('list_auto');
      return;
    }

    const id = campaign.instrumentIds[index]!;
    campaign.index = index;
    const symbol = symbolForInstrument(id);
    setListAutoUi({ index, total: campaign.instrumentIds.length, symbol });
    setListAutoBoard((b) => (b ? markListAutoBoardRunning(b, index) : b));
    setAssistantProgress(emptyAssistantProgress());
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    setLabOpenedThisRun(false);
    assistantChainRef.current = '';
    setFullCycleActive(true);
    setAssistantStatus(
      `${listAutoProgressLabel({ index, total: campaign.instrumentIds.length, symbol })}: comprobando frescura…`,
    );
    setResultFocus('list_auto');

    listAutoPendingStartRef.current = index;
    // preserveListAutoFocus: no pisar tablero ni abortar; el token fuerza el efecto
    // aunque instrumentId ya fuera este valor (bug: Play no omitía tras reinicio).
    selectInstrument(id, { forceClear: true, preserveListAutoFocus: true });
    setListAutoStartToken((n) => n + 1);
  }

  function persistListAutoPauseNow(
    campaign: ListAutoCampaign,
    board: ListAutoBoardState,
  ) {
    const snap = buildListAutoPausedSnapshot({
      campaign,
      board,
      freshnessMemory: listAutoFreshnessMemoryRef.current,
    });
    if (snap) saveListAutoPausedSnapshot(snap);
  }

  function clearPersistedListAutoPause() {
    clearListAutoPausedSnapshot();
  }

  /** Fin de un ciclo (1 valor): avanza lista AUTO o cierra. */
  function settleFullCycle(reason: FullCycleSettleReason, statusMessage?: string) {
    if (statusMessage) setAssistantStatus(statusMessage);
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    coach1AdvancePendingRef.current = false;
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    const saved = reason === 'saved';
    const skippedFinalists =
      reason === 'skip_finalists' ||
      reason === 'skip_lab' ||
      reason === 'skip_fresh';
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
      setResultFocus('finalists');
      patchSearchParams((params) => {
        params.set('focus', 'finalists');
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
      const facts = instrumentTop?.coachFacts as Record<string, unknown> | null | undefined;
      const slot1StrategyId = instrumentTop?.slots?.[0]?.strategyDefinitionId ?? null;
      const oosFromFacts = readLabEvidenceFromCoachFacts(facts);
      const oosStash = readStashedOosEvidence(slot1StrategyId);
      const oosForJudge =
        oosFromFacts && oosFromFacts.kind !== 'none' ? oosFromFacts : oosStash;
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
          typeof facts?.profileId === 'string' ? facts.profileId : null,
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
          reason === 'skip_fresh'
            ? freshness?.lastSearchAt
            : new Date().toISOString(),
      });
      const stampPromise =
        reason === 'skip_fresh'
          ? Promise.resolve()
          : rememberListAutoFreshness(settledId, settledFp, {
              lab: reason === 'saved',
            });
      setListAutoBoard((b) =>
        b
          ? markListAutoBoardSettled(b, settledIndex, reason, {
              detail: statusMessage ?? reeval.reason,
              afterTopKey: afterKey,
              lastSearchAt:
                reason === 'skip_fresh'
                  ? freshness?.lastSearchAt ?? new Date().toISOString()
                  : reason === 'saved'
                    ? new Date().toISOString()
                    : freshness?.lastSearchAt ?? new Date().toISOString(),
              reeval,
            })
          : b,
      );

      void stampPromise.finally(() => {
        const live = listAutoRef.current;
        if (!live || live.aborted) return;
        const adv = advanceListAutoAfterSettle(live);
        if (adv === 'done' || adv === 'aborted') {
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
          setResultFocus('list_auto');
          return;
        }
        if (adv === 'paused') {
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
          setResultFocus('list_auto');
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

  function pauseListAuto() {
    const campaign = listAutoRef.current;
    if (!campaign || campaign.aborted || campaign.paused) return;
    pauseListAutoCampaign(campaign);
    setListAutoBoard((b) => {
      const next = b ? markListAutoBoardPaused(b, true) : b;
      if (next && !next.rows.some((r) => r.phase === 'running')) {
        persistListAutoPauseNow(campaign, next);
      }
      return next;
    });
    setAssistantStatus('Pausa: termina el valor actual y no arranca el siguiente…');
    setResultFocus('list_auto');
  }

  function resumeListAuto() {
    const campaign = listAutoRef.current;
    if (!campaign || campaign.aborted || !campaign.paused) return;
    if (listAutoBoard?.rows.some((r) => r.phase === 'running')) {
      setAssistantStatus('Pausa: espera a que termine el valor en curso…');
      return;
    }
    clearPersistedListAutoPause();
    if (campaign.index >= campaign.instrumentIds.length) {
      setListAutoBoard((b) => (b ? markListAutoBoardDone(b) : null));
      listAutoRef.current = null;
      setListAutoUi(null);
      setAssistantStatus(listAutoDoneStatus(campaign.instrumentIds.length));
      return;
    }
    resumeListAutoCampaign(campaign);
    setListAutoBoard((b) => (b ? markListAutoBoardPaused(b, false) : b));
    setAssistantStatus(
      `${listAutoProgressLabel({
        index: campaign.index,
        total: campaign.instrumentIds.length,
        symbol: symbolForInstrument(campaign.instrumentIds[campaign.index]!),
      })}: reanudando…`,
    );
    queueListAutoTicker(campaign.index);
  }

  function stopListAuto() {
    const campaign = listAutoRef.current;
    // Guardar cursor ANTES de abortar: el próximo Play continúa aquí.
    if (campaign && listAutoBoard) {
      const snap = buildListAutoContinueSnapshot({
        listId: campaign.listId,
        instrumentIds: campaign.instrumentIds,
        nextIndex: campaign.index,
        board: listAutoBoard,
        freshnessMemory: listAutoFreshnessMemoryRef.current,
      });
      if (snap) saveListAutoContinueSnapshot(snap);
    }
    if (campaign) stopListAutoCampaign(campaign);
    exploreAbortRef.current?.abort();
    setExploreRunning(false);
    clearPersistedListAutoPause();
    abortListAutoCampaign({ keepContinue: true });
    setFullCycleActive(false);
    const nextSym =
      campaign && campaign.index < campaign.instrumentIds.length
        ? symbolForInstrument(campaign.instrumentIds[campaign.index]!)
        : null;
    setAssistantStatus(
      nextSym
        ? `Lista AUTO: Stop. Pulsa Play para continuar en ${nextSym}.`
        : 'Lista AUTO: Stop.',
    );
    setResultFocus('list_auto');
  }

  function forceListAutoRescanRemaining() {
    const campaign = listAutoRef.current;
    if (!campaign || campaign.aborted) return;
    campaign.forceRescan = true;
    // Olvida memoria de sesión de los que aún no están settled.
    if (listAutoBoard) {
      for (const row of listAutoBoard.rows) {
        if (row.phase === 'queued' || row.phase === 'running') {
          listAutoFreshnessMemoryRef.current.delete(row.instrumentId);
        }
      }
    }
    setAssistantStatus('CORE-R: reevaluar resto (ignora frescura / Omitido).');
  }

  function abortListAutoCampaign(opts?: { keepContinue?: boolean }) {
    if (listAutoRef.current) {
      listAutoRef.current.aborted = true;
    }
    listAutoRef.current = null;
    listAutoPendingStartRef.current = null;
    setListAutoUi(null);
    setListAutoBoard((b) => (b ? markListAutoBoardAborted(b) : null));
    clearPersistedListAutoPause();
    if (!opts?.keepContinue) {
      clearListAutoContinueSnapshot();
    }
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
    setCoachPass('initial');
    setOptimizeCompare(null);
    setAssistantProgress(emptyAssistantProgress());
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    setAssistantFocus(null);
    setLabOpenedThisRun(false);
    setFullCycleActive(false);
    assistantChainRef.current = '';
    listAutoFreshnessMemoryRef.current = new Map();
    setListAutoBoard(null);
    setResultFocus('detail');
    setAssistantStatus(
      `DÍA D ${formatDiaDDisplay(effectiveDiaD(next))} · asistente reiniciado. Pulsa Play.`,
    );
  }

  function currentFinalistsInputFingerprint(forInstrumentId: string): string {
    const lastBarDate = instrumentLastBarDate(
      instruments.find((i) => i.id === forInstrumentId),
    );
    // Lote de frescura = genéricas (± optimizadas ± mine). No mete Finalistas actuales:
    // al guardar TOP cambiarían y nunca habría skip_fresh.
    const lote = mergeUniverseTargetIds({
      presetIds: exploreBatteryRowIds(),
      finalistRowIds: [],
      includeFinalists: false,
      optimizedRowIds: matrixRowsForUi
        .filter((r) => r.kind === 'saved' && r.savedBucket === 'optimized')
        .map((r) => r.rowId),
      includeOptimized: assistantPrefs.universe.includeOptimizedStrategies,
      mineRowIds: matrixRowsForUi
        .filter((r) => r.kind === 'saved' && r.savedBucket === 'mine')
        .map((r) => r.rowId),
      includeMine: assistantPrefs.universe.includeMineStrategies,
      max: STRATEGY_MATRIX_MAX_SELECTED,
    });
    return buildFinalistsInputFingerprint({
      instrumentId: forInstrumentId,
      timeframe: runTimeframe,
      periodPreset,
      dateFrom: customDateFrom,
      dateTo: resolveBacktestWindow(periodPreset, customDateFrom, customDateTo, diaD).dateTo ?? customDateTo,
      initialCash,
      commissionBps,
      slippageBps,
      lastBarDate,
      loteRowIds: lote,
      profilePolicyVersion: `${buildProfilePolicyFingerprintSegment(coachProfilePolicy)}|ff:${assistantPrefs.universe.includeFinalistsInBattery ? 1 : 0}|diaD:${effectiveDiaD(diaD)}`,
    });
  }

  /** Tras analizar un valor: memoria + localStorage + stamp en TOP (fetch fresco). */
  async function rememberListAutoFreshness(
    forInstrumentId: string,
    fingerprint: string,
    opts?: { lab?: boolean },
  ) {
    listAutoFreshnessMemoryRef.current.set(forInstrumentId, fingerprint);
    try {
      const res = await queryClient.fetchQuery({
        queryKey: ['instrument-strategy-top', forInstrumentId, runTimeframe],
        queryFn: () => api.getInstrumentStrategyTop(forInstrumentId, runTimeframe),
      });
      const top = res.data;
      if (!top?.slots?.length) return;
      // Local siempre (aunque no sea active): skip_lab / semifinal también omiten tras reinicio.
      writeLocalFreshnessFingerprint({
        instrumentId: forInstrumentId,
        timeframe: runTimeframe,
        fingerprint,
      });
      await api.upsertInstrumentStrategyTop(forInstrumentId, {
        instrumentId: forInstrumentId,
        symbol: top.symbol ?? undefined,
        timeframe: top.timeframe || runTimeframe,
        periodLabel: top.periodLabel ?? null,
        status: top.status,
        evidenceLevel: top.evidenceLevel,
        slots: top.slots,
        coachHeadline: top.coachHeadline ?? null,
        coachFacts: mergeFreshnessIntoCoachFacts(
          top.coachFacts as Record<string, unknown> | null | undefined,
          buildFinalistsFreshnessStamp({
            inputFingerprint: fingerprint,
            lab: Boolean(opts?.lab),
          }),
        ),
      });
      void queryClient.invalidateQueries({
        queryKey: ['instrument-strategy-top', forInstrumentId, runTimeframe],
      });
      void queryClient.invalidateQueries({
        queryKey: ['instrument-strategy-tops-batch'],
      });
    } catch {
      // localStorage (si hubo TOP active) + memoria de sesión cubren el skip.
    }
  }

  function updateAssistantPrefs(next: AssistantPrefs) {
    setAssistantPrefs(next);
    saveAssistantPrefs(next);
  }

  async function runSemifinalOptimizeFromRows(): Promise<'opened' | 'skipped'> {
    const symbol =
      instrumentLabels[instrumentId]?.symbol ??
      instruments.find((i) => i.id === instrumentId)?.symbol ??
      'Valor';
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
        step === 'universe'
          ? 'Elige un valor para Universo.'
          : 'Completa el paso anterior (✓) o pulsa Play.',
      );
      goAssistantStep(step);
      return;
    }

    setAssistantFocus(step);
    goAssistantStep(step);

    if (step === 'universe') {
      if (assistantPrefs.universe.selectAllGenerics) {
        setMatrixFilter('preset');
        patchStrategyMatrixTablePrefs({ filter: 'preset' });
        setMatrixSelectedIds(new Set(exploreBatteryRowIds()));
      }
      if (!assistantPrefs.universe.runCoachOnEnter) {
        setAssistantStatus('Universo: marca Probar + coach en prefs o lanza a mano.');
        if (cycle) {
          settleFullCycle(
            'skip_lab',
            universeEmptyStatus('prefs sin Probar + coach'),
          );
        }
        return;
      }
      setAssistantStatus(
        cycle ? 'Ciclo: Universo · Probar + coach…' : 'Universo: Probar + coach…',
      );
      const battery = await runExploreValue();
      // El efecto Universo→Lab encadena si hay OK; si 0 OK, cerrar ciclo (evita hang en RED etc.).
      if (cycle && battery.okCount === 0) {
        settleFullCycle('skip_lab', universeEmptyStatus(battery.error ?? '0 OK'));
      }
      return;
    }

    if (step === 'semifinal') {
      const doOptimize =
        assistantPrefs.semifinal.optimizeTop3OnEnter || cycle;
      let labOutcome: 'opened' | 'skipped' | 'idle' = 'idle';
      if (doOptimize) {
        setAssistantStatus(
          cycle ? 'Ciclo: Coach → Lab TOP-3…' : 'Coach: Optimizar TOP-3…',
        );
        labOutcome = await runSemifinalOptimizeFromRows();
      } else {
        setAssistantStatus('Coach listo.');
      }
      if (labOutcome === 'skipped') {
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
        setResultFocus('lab');
        setAssistantStatus(
          'Ciclo: Lab en curso. Al terminar con mejora → Coach² → Finalistas.',
        );
      } else {
        setAssistantStatus('Coach ✓. Pulsa Play para Lab.');
      }
      return;
    }

    if (step === 'lab') {
      setLabOpenedThisRun(true);
      setAssistantFocus(null);
      setAssistantStatus(
        cycle
          ? 'Ciclo: Lab abierto. Espera resultados; handoff a Coach² automático si hay mejora.'
          : 'Lab: adopta Mejor ≥ ancla (OOS). Luego Play → Finalistas.',
      );
      return;
    }

    if (step === 'finalists') {
      setStrategiesListFilter('finalists');
      setAssistantFocus(null);
      if (cycle && coachPass === 'post_lab') {
        setAssistantStatus('Ciclo: revisando Finalistas (auto-guardado si procede)…');
        setResultFocus('coach');
        return;
      }
      setAssistantProgress((p) => ({ ...p, finalistsDone: true }));
      setFullCycleActive(false);
      if (assistantPrefs.finalists.revalidateCoachOnEnter) {
        setAssistantStatus('Finalistas: Revalidar + coach…');
        await runExploreValue();
      } else {
        setAssistantStatus('Finalistas ✓ · TOP del valor.');
      }
    }
  }

  // Universo terminado → Coach¹; en ciclo: gate perfil → Lab o skip_lab
  useEffect(() => {
    if (exploreRunning) return;
    if (exploreOkCount === 0) return;
    if (assistantProgress.semifinalDone) return;

    const fp = `u2s:${exploreRows
      .filter((r) => r.status === 'ok')
      .map((r) => r.runId ?? r.strategyType)
      .join(',')}`;
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
    setResultFocus('coach');
    setAssistantFocus(null);

    if (!fullCycleActive) {
      setAssistantStatus('Universo ✓. Pulsa Play para Coach.');
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
      'Valor';
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
        evidenceLevel: 'in_sample_only',
      },
      undefined,
      { coachPass: 'initial' },
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

    if (action.type === 'skip_lab') {
      coach1AdvancePendingRef.current = false;
      const skipped = { ...nextProgress, semifinalDone: true, labDone: true };
      assistantProgressRef.current = skipped;
      setAssistantProgress(skipped);
      settleFullCycle('skip_lab', `Ciclo: ${action.reason}`);
      return;
    }

    if (action.type === 'wait_ack1') {
      coach1AdvancePendingRef.current = true;
      setAwaitingAck(true);
      setAwaitingAckStage('coach1');
      setAssistantStatus(`Ciclo: Universo ✓ · falta ACK¹ para Lab (${action.reason})`);
      return;
    }

    if (action.type === 'save_semifinal') {
      coach1AdvancePendingRef.current = false;
      setAwaitingAck(false);
      setAwaitingAckStage(null);
      setSemifinalShortcutArmed(true);
      setAssistantStatus(`Ciclo: ${action.reason}…`);
      setResultFocus('coach');
      return;
    }

    coach1AdvancePendingRef.current = false;
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    setAssistantStatus(`Ciclo: Universo ✓ → Lab (${action.reason})…`);
    void executeAssistantStep('semifinal', { fullCycle: true, progress: nextProgress });
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
    setCoachPass('initial');
    setOptimizeCompare(null);
    setAssistantProgress(emptyAssistantProgress());
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    setAssistantFocus(null);
    setLabOpenedThisRun(false);
    setFullCycleActive(false);
    assistantChainRef.current = '';
    listAutoFreshnessMemoryRef.current = new Map();
    setListAutoBoard(null);
    setResultFocus('detail');
    setAssistantStatus('Cuenta o perfil cambiado · ciclo reiniciado. Pulsa Play.');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playContextKey, fullCycleActive, listAutoUi, listAutoBoard]);

  // Lab terminado (paso a paso): TOP active + Lab abierto en esta pasada
  useEffect(() => {
    if (fullCycleActive) return;
    if (!assistantProgress.semifinalDone) return;
    if (!labOpenedThisRun) return;
    if (assistantProgress.labDone) return;
    if (instrumentTop?.status !== 'active') return;

    const fp = `l2f:${instrumentTop.id}:v${instrumentTop.version}`;
    if (assistantChainRef.current === fp) return;
    assistantChainRef.current = fp;

    setAssistantProgress((p) => ({ ...p, labDone: true }));
    setAssistantStatus('Lab ✓ (TOP active). Pulsa Play para Finalistas.');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    fullCycleActive,
    assistantProgress.semifinalDone,
    assistantProgress.labDone,
    labOpenedThisRun,
    instrumentTop?.status,
    instrumentTop?.id,
    instrumentTop?.version,
  ]);

  // Restaurar Lista AUTO en pausa tras reinicio de la app
  useEffect(() => {
    if (listAutoPauseRestoredRef.current) return;
    listAutoPauseRestoredRef.current = true;
    const snap = loadListAutoPausedSnapshot();
    if (!snap) return;
    const campaign = campaignFromPausedSnapshot(snap);
    listAutoRef.current = campaign;
    setUniverseMode('list');
    setListId(campaign.listId);
    setListAutoBoard(snap.board);
    const row = snap.board.rows[campaign.index];
    const symbol =
      row?.symbol ?? campaign.instrumentIds[campaign.index]?.slice(0, 8) ?? '…';
    setListAutoUi({
      index: campaign.index,
      total: campaign.instrumentIds.length,
      symbol,
    });
    if (snap.freshnessMemory) {
      listAutoFreshnessMemoryRef.current = new Map(Object.entries(snap.freshnessMemory));
    }
    setTab('run');
    setResultFocus('list_auto');
    setAssistantStatus(
      `${listAutoPausedStatus({
        index: campaign.index,
        total: campaign.instrumentIds.length,
        symbol,
      })} · restaurada tras reinicio.`,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persistir pausa cuando el tablero queda estable (sin fila running)
  useEffect(() => {
    const campaign = listAutoRef.current;
    if (!campaign?.paused || !listAutoBoard?.paused) return;
    if (listAutoBoard.done || listAutoBoard.aborted) return;
    if (listAutoBoard.rows.some((r) => r.phase === 'running')) return;
    persistListAutoPauseNow(campaign, listAutoBoard);
  }, [listAutoBoard]);

  // Lista AUTO: arranque explícito por token (aunque instrumentId no cambie).
  useEffect(() => {
    const pending = listAutoPendingStartRef.current;
    if (pending == null) return;
    const campaign = listAutoRef.current;
    if (!campaign || campaign.aborted) {
      listAutoPendingStartRef.current = null;
      return;
    }
    const expectedId = campaign.instrumentIds[pending];
    if (!expectedId || instrumentId !== expectedId) return;
    // Esperar perfil/instrumentos (± mine) — si no, huella con pid:none ≠ stamp y re-analiza todo.
    if (!freshnessContextReady) {
      setAssistantStatus(
        `${listAutoProgressLabel({
          index: pending,
          total: campaign.instrumentIds.length,
          symbol: symbolForInstrument(expectedId),
        })}: esperando perfil/datos…`,
      );
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const topRes = await queryClient.fetchQuery({
          queryKey: ['instrument-strategy-top', expectedId, runTimeframe],
          queryFn: () => api.getInstrumentStrategyTop(expectedId, runTimeframe),
          staleTime: 0,
        });
        if (cancelled) return;
        if (listAutoPendingStartRef.current !== pending) return;
        const live = listAutoRef.current;
        if (!live || live.aborted) return;

        listAutoPendingStartRef.current = null;
        const top = topRes.data ?? null;
        const fp = currentFinalistsInputFingerprint(expectedId);
        const stored = readFinalistsFreshness(
          top?.coachFacts as Record<string, unknown> | null | undefined,
        );
        const local = readLocalFreshnessFingerprint(expectedId, runTimeframe);

        const skip = shouldSkipFinalistsSearch({
          preferSkip: assistantPrefs.universe.skipFreshIfUnchanged,
          forceRescan: live.forceRescan,
          topStatus: top?.status,
          evidenceLevel: top?.evidenceLevel,
          stored,
          currentFingerprint: fp,
          memoryFingerprint: listAutoFreshnessMemoryRef.current.get(expectedId) ?? null,
          localFingerprint: local?.fingerprint ?? null,
          hasSlots: Boolean(top?.slots?.length),
        });

        if (skip.adoptFingerprint) {
          listAutoFreshnessMemoryRef.current.set(expectedId, fp);
          writeLocalFreshnessFingerprint({
            instrumentId: expectedId,
            timeframe: runTimeframe,
            fingerprint: fp,
            at: top?.updatedAt,
          });
          void rememberListAutoFreshness(expectedId, fp, { lab: true });
        }

        setListAutoBoard((b) => {
          if (!b) return b;
          let next = captureListAutoBeforeTop(b, pending, listAutoTopFingerprint(top));
          const lastSearchAt =
            stored?.lastSearchAt ?? local?.lastSearchAt ?? top?.updatedAt;
          if (lastSearchAt) {
            next = {
              ...next,
              rows: next.rows.map((r) =>
                r.index === pending ? { ...r, lastSearchAt } : r,
              ),
            };
          }
          return next;
        });

        if (skip.skip) {
          const ageSource =
            skip.reason === 'local_fresh'
              ? local?.lastSearchAt
              : stored?.lastSearchAt ?? local?.lastSearchAt ?? top?.updatedAt;
          const why =
            skip.reason === 'session_fresh'
              ? 'ya analizado en esta sesión'
              : skip.reason === 'local_fresh'
                ? 'huella local igual'
                : skip.reason === 'bar_hysteresis'
                  ? 'barra reciente (histéresis)'
                  : skip.reason === 'adopt_existing_top'
                    ? 'Finalistas active adoptados'
                    : 'datos igual';
          settleFullCycle(
            'skip_fresh',
            `Ciclo: omitido · ${why} (${formatFreshnessAge(ageSource)})`,
          );
          return;
        }

        setListAutoBoard((b) =>
          b
            ? {
                ...b,
                rows: b.rows.map((r) =>
                  r.index === pending
                    ? {
                        ...r,
                        detail: `Analizando · ${freshnessSkipDenialLabel(skip.reason)}`,
                      }
                    : r,
                ),
              }
            : b,
        );
        setAssistantStatus(
          `${listAutoProgressLabel({
            index: pending,
            total: live.instrumentIds.length,
            symbol: symbolForInstrument(expectedId),
          })}: Universo…`,
        );
        void executeAssistantStep('universe', { fullCycle: true });
      } catch (err) {
        if (cancelled) return;
        if (listAutoPendingStartRef.current !== pending) return;
        const live = listAutoRef.current;
        if (!live || live.aborted) return;

        // Sin TOP legible no podemos saber si hay Finalistas → no Omitido a ciegas (v1.2).
        listAutoPendingStartRef.current = null;
        const msg = err instanceof Error ? err.message : 'error TOP';
        setListAutoBoard((b) =>
          b
            ? {
                ...b,
                rows: b.rows.map((r) =>
                  r.index === pending
                    ? {
                        ...r,
                        detail: `Skip · no se pudo leer TOP (${msg})`,
                      }
                    : r,
                ),
              }
            : b,
        );
        settleFullCycle(
          'skip_lab',
          `Ciclo: sin TOP legible (${msg}) · no se omite ni se re-analiza a ciegas`,
        );
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    listAutoStartToken,
    instrumentId,
    freshnessContextReady,
    instruments,
    runTimeframe,
    coachProfilePolicy.profileId,
  ]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {diaDVerifyFullBleed ? (
        <DiaDVerifyHost fullBleed />
      ) : null}
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
          <BacktestDiaDOriginControl diaD={diaD} onDiaDChange={handleDiaDChange} className="mb-0.5" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap rounded-lg border border-border p-0.5">
            <HubTabButton active={tab === 'run'} onClick={() => setTab('run')}>
              Probar estrategia
            </HubTabButton>
            <HubTabButton
              active={tab === 'strategies'}
              onClick={() => openLibrary({ library: strategiesListFilter })}
            >
              Biblioteca
            </HubTabButton>
            <HubTabButton active={tab === 'jobs'} onClick={() => setTab('jobs')}>
              Lab · Optimizar
            </HubTabButton>
            <HubTabButton active={tab === 'history'} onClick={() => setTab('history')}>
              Pruebas anteriores
            </HubTabButton>
          </div>
          <BacktestZoneSettingsButton onClick={() => setZoneSettingsOpen(true)} />
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
          !(listAutoBoard?.paused)
        }
        playDisabled={
          Boolean(listAutoUi) ||
          Boolean(listAutoBoard && !listAutoBoard.done && !listAutoBoard.aborted) ||
          exploreRunning ||
          semifinalEnqueuePending ||
          !(
            Boolean(instrumentId) ||
            (universeMode === 'list' &&
              assistantPrefs.fullCycleOnPlay &&
              Boolean(listId) &&
              (listDetail?.instrumentIds.length ?? 0) > 0)
          )
        }
        playTitle={listAutoPlayTitle({
          fullCycleOnPlay: assistantPrefs.fullCycleOnPlay,
          listMode: universeMode === 'list',
        })}
        listAutoControls={
          listAutoBoard && !listAutoBoard.done && !listAutoBoard.aborted
            ? {
                visible: true,
                paused: listAutoBoard.paused,
                canPause: !listAutoBoard.paused,
                canResume:
                  listAutoBoard.paused &&
                  !listAutoBoard.rows.some((r) => r.phase === 'running'),
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
          setCoachPass('initial');
          setOptimizeCompare(null);
          setAssistantProgress(emptyAssistantProgress());
          setAwaitingAck(false);
          setAwaitingAckStage(null);
          setLabImprovedThisCycle(0);
          setSemifinalShortcutArmed(false);
          setAssistantFocus(null);
          setLabOpenedThisRun(false);
          setFullCycleActive(false);
          assistantChainRef.current = '';
          setListAutoBoard(null);
          setResultFocus('detail');
          setStrategiesListFilter('all');
          setTab('run');
          setAssistantStatus(
            instrumentId
              ? 'Listo. Pulsa Play para Universo.'
              : 'Elige un valor y pulsa Play.',
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

      {tab === 'run' && (
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
                  universeMode === 'list'
                    ? listAutoUniverseHint()
                    : 'Elige un valor. El lote del Asistente (Play) usa genéricas ∪ Finalistas; la matriz es opcional. Periodo, capital y costes en Opciones avanzadas.'
                }
              >
                {universeMode === 'list'
                  ? listModeWizardTitle(assistantPrefs.fullCycleOnPlay)
                  : 'Probar estrategia'}
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
                listStatusLoading={listTopsQuery.isFetching && !listTopsQuery.data}
                onOpenListMember={openInstrumentInValor}
              />

              <div
                className={cn(
                  'rounded-md border px-2.5 py-2 text-[10px] leading-snug',
                  isDiaDInPast(diaD)
                    ? 'border-red-600 bg-red-600 text-white shadow-sm ring-1 ring-red-700/40'
                    : 'border-border/60 bg-muted/15 text-muted-foreground',
                )}
                role={isDiaDInPast(diaD) ? 'status' : undefined}
                data-testid={isDiaDInPast(diaD) ? 'dia-d-mode-banner' : undefined}
              >
                {isDiaDInPast(diaD) ? (
                  <p>
                    <strong className="font-bold tracking-wide">
                      Origen DÍA D {formatDiaDDisplay(effectiveDiaD(diaD))}
                    </strong>
                    {' — '}
                    embudo con datos ≤ esa fecha (cámbialo junto al título). Tras Play → Finalistas #1 →{' '}
                    <strong className="font-semibold">Verificar D→hoy</strong>.
                  </p>
                ) : (
                  <p>
                    Origen <strong className="text-foreground/80">Hoy {formatDiaDDisplay(todayIsoDate())}</strong>
                    . Para simular «como si hoy fuera el pasado», abre el selector junto a{' '}
                    <strong className="text-foreground/80">Backtesting</strong> y elige DÍA D (guarda fechas con ★).
                  </p>
                )}
              </div>

              <details className="rounded-md border border-border/60 bg-muted/15">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-2.5 py-1.5 text-[11px] text-muted-foreground marker:content-none [&::-webkit-details-marker]:hidden">
                  <span className="font-medium text-foreground/80">Opciones avanzadas</span>
                  <span className="min-w-0 truncate tabular-nums opacity-80">
                    {isDiaDInPast(diaD) ? `DÍA D ${effectiveDiaD(diaD)} · ` : ''}
                    {PERIOD_PRESET_OPTIONS.find((o) => o.value === periodPreset)?.label ?? periodPreset}
                    {' · '}
                    {Number(initialCash || 0).toLocaleString('es-ES')} €
                    {' · '}
                    {runTimeframe}
                    {(Number(commissionBps) > 0 || Number(slippageBps) > 0) &&
                      ` · ${commissionBps}/${slippageBps} bps`}
                  </span>
                </summary>
                <div className="space-y-2.5 border-t border-border/50 px-2.5 py-2.5">
                  <label
                    className="block text-[11px] font-medium"
                    title="Para análisis con IA: usa todo el historial sincronizado (máx. 10 000 velas). Un solo año sirve para humo rápido, pero overfittea fácil. Luego puedes validar en un subperiodo (p. ej. último año)."
                  >
                    Periodo
                    <select
                      value={periodPreset}
                      onChange={(e) => setPeriodPreset(e.target.value as PeriodPreset)}
                      className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                    >
                      {PERIOD_PRESET_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {isDiaDInPast(diaD) ? (
                    <p className="rounded border border-red-600/50 bg-red-600/10 px-2 py-1 text-[10px] font-medium leading-snug text-red-800 dark:text-red-300">
                      Periodo anclado a DÍA D {effectiveDiaD(diaD)} (no al calendario de hoy).
                    </p>
                  ) : null}
                  {periodPreset === '1y' && (
                    <p className="text-[10px] leading-snug text-amber-700 dark:text-amber-400">
                      Periodo corto: útil para una prueba rápida; no basta para declarar una estrategia
                      sólida. Mejor «Todo el historial» o ≥3–5 años.
                    </p>
                  )}
                  {periodPreset === 'custom' && (
                    <div className="grid grid-cols-2 gap-2">
                      <label className="block text-[11px] font-medium">
                        Desde
                        <input
                          type="date"
                          value={customDateFrom}
                          onChange={(e) => setCustomDateFrom(e.target.value)}
                          className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                        />
                      </label>
                      <label className="block text-[11px] font-medium">
                        Hasta
                        <input
                          type="date"
                          value={customDateTo}
                          onChange={(e) => setCustomDateTo(e.target.value)}
                          className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                        />
                      </label>
                    </div>
                  )}

                  <label
                    className="block text-[11px] font-medium"
                    title="Dinero virtual al empezar cada prueba. En una lista, CADA valor arranca con ese mismo capital (no se reparte). En cada compra se invierte casi todo el efectivo disponible (acciones enteras); al vender, el resultado vuelve a caja y la siguiente compra reinvierte ese capital actualizado."
                  >
                    Capital inicial (€)
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      name="bolsa-backtest-initial-cash"
                      autoComplete="off"
                      autoCorrect="off"
                      autoCapitalize="off"
                      spellCheck={false}
                      list="bolsa-no-cash-suggestions"
                      value={initialCash}
                      onChange={(e) => {
                        const next = e.target.value.replace(/[^\d]/g, '');
                        setInitialCash(next);
                      }}
                      className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                    />
                    <datalist id="bolsa-no-cash-suggestions" />
                  </label>
                  <p className="text-[10px] leading-snug text-muted-foreground">
                    {universeMode === 'list'
                      ? `Cada valor simula aparte con ${Number(initialCash || 0).toLocaleString('es-ES')} € (no es cartera multi-activo).`
                      : 'Compra = máximo de acciones enteras; venta = vuelve a caja (reinversión).'}
                  </p>

                  <label
                    className="block text-[11px] font-medium"
                    title="Frecuencia de las velas. Diario (1d) es el más habitual."
                  >
                    Timeframe
                    <select
                      value={runTimeframe}
                      onChange={(e) => setRunTimeframe(e.target.value as ChartTimeframe)}
                      className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                    >
                      <option value="1d">1 día</option>
                      <option value="1h">1 hora</option>
                      <option value="4h">4 horas</option>
                      <option value="1wk">1 semana</option>
                    </select>
                  </label>

                  <div className="grid grid-cols-2 gap-2">
                    <label
                      className="block text-[11px] font-medium"
                      title="Coste por operación en puntos básicos (1 bps = 0,01%)."
                    >
                      Comisión (bps)
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={commissionBps}
                        onChange={(e) => setCommissionBps(e.target.value)}
                        className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                      />
                    </label>
                    <label
                      className="block text-[11px] font-medium"
                      title="Deslizamiento de precio al ejecutar la orden, en puntos básicos."
                    >
                      Slippage (bps)
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={slippageBps}
                        onChange={(e) => setSlippageBps(e.target.value)}
                        className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                      />
                    </label>
                  </div>

                  <BacktestChartImportPanel
                    onApply={applyChartDraft}
                    onSaveStrategy={(draft, name) =>
                      saveChartStrategyMutation.mutate({ draft, name })
                    }
                    isSaving={saveChartStrategyMutation.isPending}
                  />
                </div>
              </details>

              {universeMode === 'list' ? (
                <>
                  <div className="space-y-1.5 rounded-md border border-border/60 bg-muted/20 px-2.5 py-2">
                    <p className="text-[11px] font-medium text-foreground">Lista AUTO · Play</p>
                    <p className="text-[10px] leading-snug text-muted-foreground">
                      {listAutoUniverseHint()}
                    </p>
                    {!assistantPrefs.fullCycleOnPlay ? (
                      <p className="text-[10px] leading-snug text-amber-700 dark:text-amber-400">
                        Activa «Play: ciclo completo» en el Asistente para lanzar Lista AUTO.
                      </p>
                    ) : !listId ? (
                      <p className="text-[10px] leading-snug text-muted-foreground">
                        Elige una lista arriba y pulsa Play en el Asistente.
                      </p>
                    ) : (
                      <>
                        <label className="flex items-start gap-2 text-[10px] leading-snug text-muted-foreground">
                          <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={listAutoSkipWithFinalists}
                            onChange={(e) => setListAutoSkipWithFinalists(e.target.checked)}
                          />
                          <span>
                            Solo sin Finalistas (excluye tickers que ya tienen TOP; útil en S&P /
                            listas grandes).
                          </span>
                        </label>
                        <p className="text-[10px] leading-snug text-muted-foreground">
                          {Math.min(
                            LIST_AUTO_MAX_INSTRUMENTS,
                            listDetail?.instrumentIds.length ?? 0,
                          )}{' '}
                          valor
                          {(listDetail?.instrumentIds.length ?? 0) === 1 ? '' : 'es'} en cola
                          {listAutoSkipWithFinalists ? ' (antes del filtro)' : ''}. Pulsa Play — no
                          elijas estrategia.
                        </p>
                        {(() => {
                          const warn = listAutoOverCapWarning(
                            listDetail?.instrumentIds.length ?? 0,
                          );
                          return warn ? (
                            <p className="text-[10px] leading-snug text-amber-700 dark:text-amber-400">
                              {warn}
                            </p>
                          ) : null;
                        })()}
                      </>
                    )}
                    {listAutoBoard ? (
                      <BacktestListAutoBoardPanel
                        board={listAutoBoard}
                        compact
                        selectedInstrumentId={instrumentId || null}
                        onSelectInstrument={openInstrumentInValor}
                        campaignControls={
                          !listAutoBoard.done && !listAutoBoard.aborted
                            ? {
                                canPause: !listAutoBoard.paused,
                                canResume:
                                  listAutoBoard.paused &&
                                  !listAutoBoard.rows.some((r) => r.phase === 'running'),
                                canStop: true,
                                onPause: pauseListAuto,
                                onResume: resumeListAuto,
                                onStop: stopListAuto,
                                onForceRescanRemaining: forceListAutoRescanRemaining,
                              }
                            : undefined
                        }
                      />
                    ) : listAutoUi ? (
                      <p className="text-[11px] font-medium text-foreground" aria-live="polite">
                        {listAutoProgressLabel(listAutoUi)} en curso… ↻ cancela.
                      </p>
                    ) : null}
                  </div>

                  <details className="rounded-md border border-border/60 bg-muted/10">
                    <summary className="cursor-pointer list-none px-2.5 py-1.5 text-[11px] font-medium text-foreground/90 marker:content-none [&::-webkit-details-marker]:hidden">
                      Probar lista (opcional) · 1 estrategia × N valores
                    </summary>
                    <div className="space-y-2 border-t border-border/50 px-2.5 py-2.5">
                      <p className="text-[10px] leading-snug text-muted-foreground">
                        Ranking rápido Fase C. No es el embudo Play / Lista AUTO.
                      </p>
                      <fieldset className="space-y-2">
                        <legend
                          className="text-[11px] font-medium"
                          title="Genérica = catálogo. Optimizadas = Lab/clones. Mis estrategias = autoría (prompt/manual)."
                        >
                          Estrategia para «Probar lista»
                        </legend>
                        <label className="flex items-center gap-2 text-xs">
                          <input
                            type="radio"
                            checked={runSource === 'preset'}
                            onChange={() => setRunSource('preset')}
                          />
                          Genérica
                        </label>
                        <label className="flex items-center gap-2 text-xs">
                          <input
                            type="radio"
                            checked={runSource === 'saved'}
                            onChange={() => setRunSource('saved')}
                            disabled={strategies.length === 0}
                          />
                          Mis estrategias / Optimizadas
                        </label>
                      </fieldset>

                      {runSource === 'preset' ? (
                        <>
                          <label className="block text-[11px] font-medium">
                            Estrategia
                            <select
                              value={strategyType}
                              onChange={(e) =>
                                setStrategyType(e.target.value as BacktestStrategyType)
                              }
                              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                            >
                              {STRATEGY_OPTIONS.map(([key, meta]) => (
                                <option key={key} value={key}>
                                  {meta.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          {strategyMeta && (
                            <p className="text-[11px] text-muted-foreground">
                              {strategyMeta.description}
                            </p>
                          )}
                        </>
                      ) : (
                        <label className="block text-[11px] font-medium">
                          Estrategia (guardada)
                          <select
                            value={savedStrategyId}
                            onChange={(e) => setSavedStrategyId(e.target.value)}
                            className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                          >
                            <option value="">Selecciona…</option>
                            {strategies.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.name}
                                {s.presetKey
                                  ? ` · ${BACKTEST_STRATEGIES[s.presetKey]?.label ?? s.presetKey}`
                                  : ''}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}

                      {batchRunning ? (
                        <div className="flex gap-2">
                          <Button className="flex-1" disabled>
                            Probando lista… {batchProgress.done}/{batchProgress.total}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => batchAbortRef.current?.abort()}
                          >
                            Parar
                          </Button>
                        </div>
                      ) : (
                        <Button
                          className="w-full"
                          variant="secondary"
                          onClick={() => void runListBatch()}
                          disabled={
                            batchRunning ||
                            exploreRunning ||
                            Boolean(listAutoUi) ||
                            (runSource === 'saved' && !savedStrategyId) ||
                            (periodPreset === 'custom' &&
                              (!customDateFrom || !customDateTo)) ||
                            !listId
                          }
                        >
                          {`Probar lista${
                            listDetail
                              ? ` (${Math.min(
                                  LIST_AUTO_MAX_INSTRUMENTS,
                                  listDetail.instrumentIds.length,
                                )})`
                              : ''
                          }`}
                        </Button>
                      )}
                    </div>
                  </details>

                  <details className="rounded-md border border-border/60 bg-muted/10">
                    <summary className="cursor-pointer list-none px-2.5 py-1.5 text-[11px] font-medium text-foreground/90 marker:content-none [&::-webkit-details-marker]:hidden">
                      Comparación masiva (Q3.3) · N estrategias × N valores
                    </summary>
                    <div className="border-t border-border/50 px-2.5 py-2.5">
                      {listDetail ? (
                        <BacktestMassComparePanel
                          instrumentIds={listDetail.instrumentIds}
                          labels={instrumentLabels}
                          strategyOptions={STRATEGY_OPTIONS.slice(0, 10).map(([key, meta]) => ({
                            key,
                            label: meta.label,
                            strategyType: key,
                          }))}
                          initialCash={Number(initialCash)}
                          commissionBps={Number(commissionBps) || 0}
                          slippageBps={Number(slippageBps) || 0}
                          timeframe={runTimeframe}
                          window={resolveBacktestWindow(
                            periodPreset,
                            customDateFrom,
                            customDateTo,
                            diaD,
                          )}
                        />
                      ) : (
                        <p className="text-[10px] text-muted-foreground">
                          Elige una lista en Universo para comparar.
                        </p>
                      )}
                    </div>
                  </details>
                </>
              ) : (
                <BacktestStrategyMatrixPanel
                  rows={matrixRowsForUi}
                  filter={matrixFilter}
                  selectedIds={matrixSelectedIds}
                  listHeightPx={zonePrefs.strategyMatrix.listHeightPx}
                  onListHeightPxChange={(next) => {
                    patchStrategyMatrixTablePrefs({ listHeightPx: next });
                    setZonePrefs(loadBacktestZonePrefs());
                  }}
                  running={exploreRunning}
                  progress={coachRunProgress}
                  finalistsFilterLabel={
                    instrumentSymbol ? `Finalistas · ${instrumentSymbol}` : 'Finalistas'
                  }
                  finalistsFilterDisabled={!instrumentId || !(instrumentTop?.slots?.length)}
                  disabled={
                    !instrumentId ||
                    runMutation.isPending ||
                    batchRunning ||
                    exploreRunning ||
                    (periodPreset === 'custom' && (!customDateFrom || !customDateTo))
                  }
                  onFilterChange={(next) => {
                    setMatrixFilter(next);
                    patchStrategyMatrixTablePrefs({ filter: next });
                  }}
                  onToggle={toggleMatrixRow}
                  onApplySelection={applyMatrixSelection}
                  onClearSelection={() => setMatrixSelectedIds(new Set())}
                  onRunCoach={(opts) => void runCoachFromMatrixUi(opts)}
                  coachCount={matrixCoachTargetIds.length}
                  coachDisabled={
                    !instrumentId ||
                    matrixCoachTargetIds.length === 0 ||
                    runMutation.isPending ||
                    batchRunning ||
                    exploreRunning ||
                    (periodPreset === 'custom' && (!customDateFrom || !customDateTo))
                  }
                  onStop={() => exploreAbortRef.current?.abort()}
                  onOpenDetail={(runId) => {
                    selectRun(runId, { tab: 'run' });
                    setResultFocus('detail');
                  }}
                  onGoToStrategies={() => openLibrary({ library: 'all' })}
                  onOpenInLibrary={(row) => {
                    if (row.kind === 'saved' && row.strategyDefinitionId) {
                      openLibrary({
                        library: 'mine',
                        strategyId: row.strategyDefinitionId,
                      });
                      return;
                    }
                    if (row.presetKey) {
                      openLibrary({
                        library: 'generics',
                        preset: row.presetKey,
                      });
                    }
                  }}
                  onDeleteSavedStrategy={(row) => {
                    if (row.kind !== 'saved' || !row.strategyDefinitionId) return;
                    const name = row.label;
                    if (
                      !window.confirm(
                        `¿Eliminar «${name}» de Mis estrategias? Esta acción no se puede deshacer.`,
                      )
                    ) {
                      return;
                    }
                    void api.deleteStrategy(row.strategyDefinitionId).then(
                      () => {
                        void queryClient.invalidateQueries({ queryKey: ['strategies'] });
                        void queryClient.invalidateQueries({
                          queryKey: ['instrument-strategy-top'],
                        });
                        if (savedStrategyId === row.strategyDefinitionId) {
                          setSavedStrategyId('');
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
                            : 'No se pudo eliminar la estrategia',
                        );
                      },
                    );
                  }}
                />
              )}

              {universeMode === 'single' && instrumentId ? (
                <>
                  <FundamentalCardPanel
                    instrumentId={instrumentId}
                    compact
                    className="mb-2"
                    asOf={isDiaDInPast(diaD) ? effectiveDiaD(diaD) : null}
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
                    setMatrixFilter('finalists');
                    patchStrategyMatrixTablePrefs({ filter: 'finalists' });
                    setMatrixSelectedIds(new Set([rowId]));
                    setSavedStrategyId(strategyId);
                    setRunSource('saved');
                    if (slot?.runId) {
                      openFinalistChecklist(slot);
                    }
                  }}
                  onOpenChecklist={(slot) => openFinalistChecklist(slot)}
                  onProposeSupervised={(slot) => proposeFinalistSupervisedSlot(slot)}
                  proposePendingStrategyId={
                    proposeFinalistMutation.isPending
                      ? proposeFinalistMutation.variables?.strategyDefinitionId ?? null
                      : null
                  }
                />
                </>
              ) : null}

              {batchError && (
                <p className="text-sm text-destructive">{batchError}</p>
              )}
              {exploreError && (
                <p className="text-sm text-destructive">{exploreError}</p>
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
                      id: 'detail' as const,
                      label: 'Análisis técnico',
                      done: Boolean(selectedId || detail),
                      disabled: false,
                      title:
                        'Gráfico, replay, equity y operaciones de la prueba (sin tarjeta FA)',
                    },
                    {
                      id: 'fundamental' as const,
                      label: 'Análisis fundamental',
                      done: Boolean(instrumentId),
                      disabled: !instrumentId,
                      title:
                        'Tarjeta Valor: Score_FUND, ratios, Composite, filings y copiloto',
                    },
                    {
                      id: 'coach' as const,
                      label:
                        coachPass === 'post_lab' ? 'Coach · Revalidar' : 'Coach',
                      done:
                        assistantStepComplete.universe ||
                        exploreRows.length > 0 ||
                        coachPass === 'post_lab',
                      disabled: false,
                      title:
                        coachPass === 'post_lab'
                          ? '4 · Revalidar (Coach²): tras Lab, re-evalúa Mejor(es) antes de Finalistas'
                          : exploreRows.length === 0
                            ? '2 · Coach: aún sin lote — Play → Probar'
                            : '2 · Coach: estrellas ★ y dual-audit del lote',
                    },
                    {
                      id: 'lab' as const,
                      label: 'Lab',
                      done: assistantStepComplete.lab || assistantStepComplete.semifinal,
                      disabled: !instrumentId,
                      title:
                        '3 · Lab: mejora por IA de las 3 mejores (Mejor ≥ ancla OOS)',
                    },
                    {
                      id: 'finalists' as const,
                      label: 'Finalistas',
                      done:
                        assistantProgress.finalistsSaved ||
                        topStrategyIds.size > 0,
                      disabled: !instrumentId,
                      title: assistantProgress.finalistsSkipped
                        ? '5 · Finalistas: ciclo cerró sin guardar TOP (revisa Revalidar / ACK)'
                        : '5 · Finalistas: TOP del valor en BD',
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
                      (t.id === 'detail' && resultFocus === 'ranking')
                    }
                    variant={
                      resultFocus === t.id ||
                      (t.id === 'detail' && resultFocus === 'ranking')
                        ? 'default'
                        : 'outline'
                    }
                    disabled={t.disabled}
                    title={t.title}
                    className={cn(
                      'h-7 text-[11px]',
                      t.done &&
                        resultFocus !== t.id &&
                        !(t.id === 'detail' && resultFocus === 'ranking') &&
                        'border-emerald-500/40 text-emerald-800 dark:text-emerald-200',
                      t.id === 'finalists' &&
                        assistantProgress.finalistsSkipped &&
                        !assistantProgress.finalistsSaved &&
                        'border-amber-500/40 text-amber-900 dark:text-amber-200',
                      t.id === 'coach' &&
                        awaitingAck &&
                        'border-amber-500/50 text-amber-900 dark:text-amber-200',
                    )}
                    onClick={() => {
                      if (t.id === 'lab') setLabOpenedThisRun(true);
                      if (t.id === 'finalists') setStrategiesListFilter('finalists');
                      setResultFocus(t.id);
                      patchSearchParams((params) => {
                        params.set('focus', t.id);
                        if (instrumentId) params.set('instrumentId', instrumentId);
                        // Salir del modo Verificar D→hoy al cambiar de pestaña de resultado.
                        params.delete('verify');
                      });
                    }}
                  >
                    {t.id === 'finalists' && assistantProgress.finalistsSkipped
                      ? '– '
                      : t.done
                        ? '✓ '
                        : awaitingAck && t.id === 'coach'
                          ? '! '
                          : ''}
                    {t.label}
                  </Button>
                ))}
                {resultFocus === 'coach' ? (
                  <AiInfoButton surface="backtest_coach" />
                ) : resultFocus === 'lab' ? (
                  <AiInfoButton surface="lab_optimize" />
                ) : resultFocus === 'fundamental' ? (
                  <AiInfoButton surface="fa_copilot" />
                ) : null}
                {batchRows.length > 0 && (
                  <Button
                    type="button"
                    size="sm"
                    role="tab"
                    aria-selected={resultFocus === 'ranking'}
                    variant={resultFocus === 'ranking' ? 'default' : 'outline'}
                    className="h-7 text-[11px]"
                    title="Clic en un valor para abrir su análisis técnico"
                    onClick={() => setResultFocus('ranking')}
                  >
                    Ranking lista
                  </Button>
                )}
                {listAutoBoard && (
                  <Button
                    type="button"
                    size="sm"
                    role="tab"
                    aria-selected={resultFocus === 'list_auto'}
                    variant={resultFocus === 'list_auto' ? 'default' : 'outline'}
                    className={cn(
                      'h-7 text-[11px]',
                      listAutoBoard.done &&
                        !listAutoBoard.aborted &&
                        resultFocus !== 'list_auto' &&
                        'border-emerald-500/40 text-emerald-800 dark:text-emerald-200',
                    )}
                    title="Progreso de Lista AUTO: todos los valores, estado y Δ Finalistas"
                    onClick={() => setResultFocus('list_auto')}
                  >
                    {listAutoBoard.done && !listAutoBoard.aborted ? '✓ ' : ''}
                    Lista AUTO
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent
              className={cn(
                'min-h-0 flex-1 p-3',
                isAnalysisResultFocus(resultFocus) && (detail || instrumentId)
                  ? 'flex flex-col overflow-hidden pt-1'
                  : 'overflow-auto pt-0',
              )}
            >
              {listAutoBoard && resultFocus === 'list_auto' && (
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
                            !listAutoBoard.rows.some((r) => r.phase === 'running'),
                          canStop: true,
                          onPause: pauseListAuto,
                          onResume: resumeListAuto,
                          onStop: stopListAuto,
                          onForceRescanRemaining: forceListAutoRescanRemaining,
                        }
                      : undefined
                  }
                />
              )}

              {resultFocus === 'coach' && exploreRows.length === 0 && !listAutoBoard && (
                <p className="text-sm text-muted-foreground">
                  Sin lote de coach aún. Pulsa Play en Universo (o Probar + coach) para rellenarlo.
                </p>
              )}
              {resultFocus === 'coach' && exploreRows.length === 0 && listAutoBoard && (
                <p className="text-sm text-muted-foreground">
                  Lista AUTO en marcha. El Coach del valor actual aparece aquí al terminar su
                  Universo; el tablero completo está en «Lista AUTO».
                </p>
              )}
              {exploreRows.length > 0 &&
                (resultFocus === 'coach' ||
                  (Boolean(listAutoBoard) &&
                    fullCycleActive &&
                    coachPass === 'post_lab')) && (
                <div
                  className={
                    resultFocus === 'coach'
                      ? 'h-full min-h-0 overflow-auto'
                      : 'hidden'
                  }
                  aria-hidden={resultFocus !== 'coach'}
                >
                <BacktestExploreRanking
                  rows={exploreRows}
                  instrumentId={instrumentId || null}
                  coachPass={coachPass}
                  symbol={
                    detail?.symbol ??
                    instrumentLabels[instrumentId]?.symbol ??
                    instruments.find((inst) => inst.id === instrumentId)?.symbol ??
                    'Valor'
                  }
                  timeframe={runTimeframe}
                  periodLabel={
                    PERIOD_PRESET_OPTIONS.find((o) => o.value === periodPreset)?.label ??
                    periodPreset
                  }
                  sort={exploreSort}
                  onSortChange={setExploreSort}
                  selectedRunId={selectedId}
                  onSelectRun={(runId) => {
                    selectRun(runId, { tab: 'run' });
                    setResultFocus('detail');
                  }}
                  onOptimizeCandidate={(row) =>
                    startOptimizeFromExplore(row, 'explore_best')
                  }
                  onOptimizeSemifinal={(candidates) => {
                    void optimizeSemifinalFromCoach(candidates);
                  }}
                  barLimit={
                    exploreRows.find((row) => row.status === 'ok' && row.barCount != null)
                      ?.barCount ?? detail?.barCount
                  }
                  futureWeight={assistantPrefs.coach.futureWeight}
                  llmNarrate={assistantPrefs.coach.llmNarrate}
                  freshnessInputFingerprint={
                    instrumentId ? currentFinalistsInputFingerprint(instrumentId) : null
                  }
                  autoSaveFinalists={
                    coachPass === 'post_lab' &&
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
                    coachPass === 'initial' &&
                    !exploreRunning
                  }
                  autoAckOnCycle={assistantPrefs.coach.autoAckOnCycle}
                  pauseIfAckNeeded={assistantPrefs.coach.pauseIfAckNeeded}
                  requireAckBeforeLab={assistantPrefs.coach.requireAckBeforeLab}
                  labImprovedCountHint={labImprovedThisCycle}
                  onAwaitingAckChange={(awaiting) => {
                    setAwaitingAck(awaiting);
                    if (!awaiting) {
                      setAwaitingAckStage(null);
                      return;
                    }
                    setAwaitingAckStage(
                      coachPass === 'post_lab' ? 'revalidate' : 'coach1',
                    );
                  }}
                  onCoachGateChange={setCoachGate}
                  onAutoSaveStatus={(message) => {
                    if (isSemifinalShortcutStatusMessage(message)) {
                      settleFullCycle('skip_lab', message);
                      return;
                    }
                    const saved = isFinalistsSavedStatusMessage(message);
                    if (saved && !listAutoRef.current) {
                      setResultFocus('finalists');
                      setStrategiesListFilter('finalists');
                    }
                    settleFullCycle(saved ? 'saved' : 'skip_finalists', message);
                  }}
                  progress={exploreProgress}
                  running={exploreRunning}
                  equityByRunId={Object.fromEntries(
                    exploreRows
                      .filter((r) => r.runId)
                      .map((r) => {
                        const cached = queryClient.getQueryData<{
                          data?: { equityCurve?: import('@bolsa/shared').BacktestEquityPointDto[] };
                        }>(['backtest', r.runId!]);
                        return [r.runId!, cached?.data?.equityCurve] as const;
                      }),
                  )}
                />
                </div>
              )}

              {(resultFocus === 'lab' ||
                (Boolean(listAutoBoard) &&
                  fullCycleActive &&
                  labOpenedThisRun &&
                  !assistantProgress.labDone)) && (
                <div
                  className={
                    resultFocus === 'lab'
                      ? 'flex h-full min-h-0 flex-col gap-3 overflow-auto'
                      : 'hidden'
                  }
                  aria-hidden={resultFocus !== 'lab'}
                >
                  {!(
                    (labZones ?? []).some((z) => z.seed) || Boolean(optimizeSeed)
                  ) && (
                    <div className="rounded-lg border border-dashed border-border bg-muted/10 px-3 py-2.5 text-sm">
                      <p className="font-medium text-foreground">Lab sin semillas</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Desde Coach: «Pasar al Lab» o «Abrir Lab · #1». Aquí optimizas parámetros; no
                        escribe Finalistas.
                      </p>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="mt-2"
                        onClick={() => {
                          setResultFocus('coach');
                          patchSearchParams((params) => {
                            params.set('focus', 'coach');
                          });
                        }}
                      >
                        Ir al Coach
                      </Button>
                    </div>
                  )}
                  <BacktestLabBoard
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
                    onClearZoneSeed={(zoneId) => {
                      setLabZones((prev) => {
                        if (!prev) {
                          setOptimizeSeed(null);
                          return null;
                        }
                        const next = prev.map((z) =>
                          z.id === zoneId ? { ...z, seed: null, jobId: null, jobIds: null } : z,
                        );
                        setOptimizeSeed(next.find((z) => z.seed)?.seed ?? null);
                        return next;
                      });
                    }}
                    onReanalyzeWithCoach={(payload) => reanalyzeLabWithCoach(payload)}
                    autoHandoff={fullCycleActive}
                    maxDrawdownSoftPct={coachProfilePolicy.maxDrawdownSoftPct}
                    profileId={coachProfilePolicy.profileId}
                    profileHorizon={coachProfilePolicy.horizon}
                    profileRiskTolerance={coachProfilePolicy.riskTolerance}
                    onAutoHandoffStatus={(message) => {
                      if (
                        message.includes('No se pisan Finalistas') ||
                        message.includes('Lab sin Mejor') ||
                        message.includes('Lab sin zonas') ||
                        message.includes('Lab timeout')
                      ) {
                        // Sin TOP durable (vacío o huérfano tras borrar estrategias):
                        // Coach² / auto-save con el lote actual (primera escritura).
                        void (async () => {
                          let durable = hasExistingTopForSave;
                          try {
                            await queryClient.invalidateQueries({
                              queryKey: ['strategies'],
                            });
                            if (instrumentId) {
                              await queryClient.invalidateQueries({
                                queryKey: [
                                  'instrument-strategy-top',
                                  instrumentId,
                                  runTimeframe,
                                ],
                              });
                            }
                            const [stratsRes, topRes] = await Promise.all([
                              queryClient.fetchQuery({
                                queryKey: ['strategies'],
                                queryFn: api.getStrategies,
                              }),
                              instrumentId
                                ? queryClient.fetchQuery({
                                    queryKey: [
                                      'instrument-strategy-top',
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
                            ]);
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
                            if ((!durable || experimentMode) && exploreOkCount > 0) {
                              setLabImprovedThisCycle(0);
                              setCoachPass('post_lab');
                              setResultFocus('coach');
                              setAssistantStatus(
                                experimentMode
                                  ? `Ciclo: Lab sin mejora · DÍA D ${effectiveDiaD(diaD)} → grabando F-D (F-hoy intacto)…`
                                  : top
                                    ? 'Ciclo: Lab sin mejora · Finalistas huérfanos → grabando (primera escritura)…'
                                    : 'Ciclo: Lab sin mejora · sin TOP previo → grabando Finalistas (primera escritura)…',
                              );
                              return;
                            }
                            settleFullCycle('skip_lab', message);
                            return;
                          } catch {
                            durable = hasExistingTopForSave;
                          }
                          if (
                            (!durable || isDiaDInPast(diaD)) &&
                            exploreOkCount > 0
                          ) {
                            setLabImprovedThisCycle(0);
                            setCoachPass('post_lab');
                            setResultFocus('coach');
                            setAssistantStatus(
                              isDiaDInPast(diaD)
                                ? `Ciclo: Lab sin mejora · DÍA D ${effectiveDiaD(diaD)} → grabando F-D (F-hoy intacto)…`
                                : 'Ciclo: Lab sin mejora · sin TOP previo → grabando Finalistas (primera escritura)…',
                            );
                            return;
                          }
                          settleFullCycle('skip_lab', message);
                        })();
                        return;
                      }
                      setAssistantStatus(message);
                    }}
                  />
                </div>
              )}

              {resultFocus === 'finalists' && (
                <div className="space-y-3 overflow-auto">
                  {instrumentId ? (
                    <InstrumentStrategyTopPanel
                      instrumentId={instrumentId}
                      symbol={
                        instrumentLabels[instrumentId]?.symbol ??
                        instruments.find((i) => i.id === instrumentId)?.symbol
                      }
                      timeframe={runTimeframe}
                      top={instrumentTop}
                      asOfDiaD={diaD}
                      activeProfileId={coachProfilePolicy.profileId}
                      onUseStrategy={(strategyId, slot) => {
                        setSavedStrategyId(strategyId);
                        setRunSource('saved');
                        if (slot?.runId) {
                          openFinalistChecklist(slot);
                          return;
                        }
                        setPreferOpenAnalysis(false);
                        setResultFocus('detail');
                        patchSearchParams((params) => {
                          params.set('focus', 'detail');
                        });
                      }}
                      onOpenChecklist={(slot) => openFinalistChecklist(slot)}
                      onProposeSupervised={(slot) => proposeFinalistSupervisedSlot(slot)}
                      proposePendingStrategyId={
                        proposeFinalistMutation.isPending
                          ? proposeFinalistMutation.variables?.strategyDefinitionId ?? null
                          : null
                      }
                      onGoToCoach={() => {
                        setResultFocus('coach');
                        patchSearchParams((params) => {
                          params.set('focus', 'coach');
                        });
                      }}
                    />
                  ) : (
                    <div className="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">
                      <p className="font-medium text-foreground">Elige un valor</p>
                      <p className="mt-1">
                        Universo → Lista: clic en un miembro (IBEX, S&P…) para abrirlo en Valor. O
                        elige un ticker en la pestaña Valor. Aquí verás Checklist y Proponer cuando
                        haya TOP.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {batchRows.length > 0 && resultFocus === 'ranking' && (
                <BacktestRankingTable
                  rows={batchRows}
                  sort={batchSort}
                  onSortChange={setBatchSort}
                  selectedRunId={selectedId}
                  selectedInstrumentId={instrumentId || null}
                  onSelectInstrument={(id) => {
                    const row = batchRows.find((r) => r.instrumentId === id);
                    openInstrumentInValor(id, { runId: row?.runId ?? null, soft: true });
                  }}
                  onSelectRun={(runId) => {
                    selectRun(runId, { tab: 'run', focus: 'detail' });
                  }}
                  progress={batchProgress}
                  listName={listDetail?.name ?? lists.find((l) => l.id === listId)?.name}
                  running={batchRunning}
                />
              )}

              {resultFocus === 'fundamental' && instrumentId && (
                <div className="min-h-0 flex-1 overflow-auto">
                  <FundamentalCardPanel
                    instrumentId={instrumentId}
                    asOf={isDiaDInPast(diaD) ? effectiveDiaD(diaD) : null}
                  />
                </div>
              )}

              {resultFocus === 'fundamental' && !instrumentId && (
                <p className="text-sm text-muted-foreground">
                  Elige un valor en Universo para ver la Tarjeta Valor (análisis fundamental).
                </p>
              )}

              {resultFocus === 'detail' && diaDVerifyActive ? (
                <div className="flex min-h-0 flex-1 flex-col">
                  <DiaDVerifyHost />
                </div>
              ) : null}

              {resultFocus === 'detail' &&
                !diaDVerifyActive &&
                !detail &&
                instrumentId &&
                !(
                  selectedId &&
                  detailQuery.isFetching &&
                  (!detailQuery.data?.data ||
                    detailQuery.data.data.instrumentId === instrumentId)
                ) && (
                <div className="flex min-h-0 flex-1 flex-col">
                  <BacktestInstrumentPreview
                    key={instrumentId}
                    instrumentId={instrumentId}
                    symbol={instrumentSymbol ?? 'Valor'}
                    name={instrumentLabels[instrumentId]?.name}
                    timeframe={runTimeframe}
                    periodPreset={periodPreset}
                    customDateFrom={customDateFrom}
                    customDateTo={customDateTo}
                    diaD={diaD}
                  />
                </div>
              )}

              {resultFocus === 'detail' && !diaDVerifyActive && !detail && !instrumentId && (
                <BacktestResultEmpty />
              )}

              {resultFocus === 'detail' &&
                !diaDVerifyActive &&
                !detail &&
                selectedId &&
                detailQuery.isFetching &&
                (!detailQuery.data?.data ||
                  detailQuery.data.data.instrumentId === instrumentId) && (
                <p className="text-sm text-muted-foreground">Cargando resultado…</p>
              )}

              {resultFocus === 'detail' &&
                !diaDVerifyActive &&
                selectedId &&
                !detail &&
                detailQuery.isError && (
                <p className="text-sm text-destructive">
                  {detailQuery.error instanceof ApiError
                    ? detailQuery.error.message
                    : detailQuery.error instanceof Error
                      ? detailQuery.error.message
                      : 'No se pudo cargar el detalle de esta prueba.'}
                </p>
              )}

              {resultFocus === 'detail' && !diaDVerifyActive && detail && (
                <div className="flex min-h-0 flex-1 flex-col">
                  <BacktestResultView
                  fillHeight
                  detail={detail}
                  preferOpenAnalysis={preferOpenAnalysis}
                  bars={replayBarsQuery.data?.data}
                  barsLoading={replayBarsQuery.isLoading && !replayBarsQuery.data}
                  barsError={replayBarsQuery.isError && !replayBarsQuery.data}
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
                  actions={
                    <>
                      {batchRows.length > 0 && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setResultFocus('ranking')}
                        >
                          Volver al ranking
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="default"
                        size="sm"
                        className="gap-1.5"
                        title="Abre Lab con este valor, esta estrategia y estos resultados como punto de partida."
                        aria-label="Optimizar a partir de esta prueba"
                        onClick={startOptimizeFromDetail}
                      >
                        <SlidersHorizontal className="h-4 w-4" />
                        Lab
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-8 w-8 p-0"
                        title="Exportar resultado completo (JSON)"
                        aria-label="Exportar JSON"
                        onClick={() => exportBacktestJson(detail)}
                      >
                        <FileJson className="h-4 w-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-8 w-8 p-0"
                        title="Exportar operaciones (CSV)"
                        aria-label="Exportar trades CSV"
                        disabled={detail.trades.length === 0}
                        onClick={() => exportTradesCsv(detail)}
                      >
                        <Table className="h-4 w-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-8 w-8 p-0"
                        title="Exportar evolución del patrimonio (CSV)"
                        aria-label="Exportar equity CSV"
                        disabled={equityCurve.length === 0}
                        onClick={() => exportEquityCsv(detail)}
                      >
                        <LineChart className="h-4 w-4" />
                      </Button>
                    </>
                  }
                  deployingPaper={deployPaperMutation.isPending}
                  onDeployPaper={(payload) =>
                    deployPaperMutation.mutate({
                      strategyId: detail.strategyDefinitionId ?? '',
                      runId: detail.id,
                      initialDeposit: detail.initialCash,
                      labEvidence: payload.labEvidence,
                    })
                  }
                  footerNote={
                    <>
                      {deployPaperMutation.isError && (
                        <p className="text-sm text-destructive">
                          {deployPaperMutation.error instanceof ApiError
                            ? deployPaperMutation.error.message
                            : 'No se pudo crear la cuenta paper'}
                        </p>
                      )}
                      {manifestSummary && (
                        <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs">
                          <p className="font-medium text-foreground">Manifiesto de la prueba</p>
                          <ul className="mt-1 space-y-0.5 text-muted-foreground">
                            <li>Motor: {manifestSummary.engine}</li>
                            <li>Versión datos: {manifestSummary.dataVersion ?? '—'}</li>
                            <li>Barras: {manifestSummary.barCount ?? detail.barCount}</li>
                            <li>Hash métricas: {manifestSummary.metricsHash}</li>
                          </ul>
                        </div>
                      )}
                      <p className="text-xs text-muted-foreground">
                        El checklist Lab habilita «{PAPER_PATH_LAB.cta}» ({PAPER_PATH_LAB.shortTitle};
                        distinto del Paper automático del rastreador). Cuenta simulada desde este
                        run; sin auto-ejecución.
                      </p>
                    </>
                  }
                />
                </div>
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
                initialListId={universeMode === 'list' && listId ? listId : undefined}
              />
            </div>
          </details>
        </>
      )}

      {tab === 'jobs' && (
        <div className="mx-auto min-h-0 w-full max-w-[1600px] flex-1 space-y-4 overflow-auto px-1">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold tracking-tight">Lab · Optimizar</h3>
              <p className="text-sm text-muted-foreground">
                Mismo Lab del embudo Coach → Finalistas. Busca Mejor ≥ ancla (OOS); no escribe
                Finalistas.
              </p>
            </div>
            {!optimizeSeed && !(labZones ?? []).some((z) => z.seed) && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setTab('run');
                  setResultFocus('coach');
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
                Desde Probar → Coach: «Pasar al Lab» o «Abrir Lab · #1». También puedes elegir
                instrumento abajo y lanzar a mano.
              </p>
            </div>
          )}
          {optimizeCompare && (
            <BacktestOptimizeCompareCard
              snapshot={optimizeCompare}
              onDismiss={() => setOptimizeCompare(null)}
              onBackToCoach={() => {
                setTab('run');
                setResultFocus('coach');
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
              setRunSource('saved');
              setInstrumentId(nextInstrumentId);
              setInitialCash(String(cash));
              setRunTimeframe(timeframe);
              setPeriodPreset('all');
              setUniverseMode('single');
              setTab('run');
              setResultFocus('detail');
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

      {tab === 'strategies' && (
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
                params.set('tab', 'strategies');
                params.set('library', strategiesListFilter);
                if (next.query.trim()) params.set('q', next.query.trim());
                else params.delete('q');
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
            setRunSource('preset');
            setTab('run');
          }}
          onUseSaved={(strategyId) => {
            setSavedStrategyId(strategyId);
            setRunSource('saved');
            setTab('run');
            setResultFocus('detail');
            setAssistantStatus(PAPER_PATH_LAB.libraryHint);
          }}
          onOpenFinalistChecklist={(slot) => {
            setTab('run');
            openFinalistChecklist(slot);
          }}
          onProposeFinalistSupervised={(slot) => {
            setTab('run');
            proposeFinalistSupervisedSlot(slot);
          }}
          proposeFinalistPendingStrategyId={
            proposeFinalistMutation.isPending
              ? proposeFinalistMutation.variables?.strategyDefinitionId ?? null
              : null
          }
          onDeleted={(id) => {
            if (savedStrategyId === id) setSavedStrategyId('');
            if (libraryFocusStrategyId === id) {
              setLibraryFocusStrategyId(null);
              patchSearchParams((params) => {
                params.delete('strategyId');
              });
            }
          }}
          onGoToCoach={() => {
            setTab('run');
            setResultFocus('coach');
          }}
        />
      )}

      {tab === 'history' && (
        <BacktestHistoryTab
          runs={runs}
          historyMaxKept={zonePrefs.historyMaxKept}
          selectedId={selectedId}
          onOpenSettings={() => setZoneSettingsOpen(true)}
          onSelectRun={(runId) => selectRun(runId, { tab: 'run' })}
          onGoToRun={() => setTab('run')}
        />
      )}
      </>
      ) : null}
    </div>
  );
}

function HubTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
        active ? 'bg-accent text-primary' : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {children}
    </button>
  );
}
