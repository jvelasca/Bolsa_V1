/**
 * Tab `run` (wizard + result + monitor) extraída de `BacktestsPage`.
 *
 * Extraído de `backtests-page.tsx` (Track B B10) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 *
 * Presentacional: props in, JSX out. Sin hooks. Recrear el ViewModel cada
 * render en el shell (no memoizar): el original no estaba memoizado.
 */

import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { QueryClient } from "@tanstack/react-query";
import type {
  BacktestEquityPointDto,
  BacktestTradeDto,
  ChartStrategySetupDraft,
  ChartTimeframe,
  DrawingReplayMarkerDto,
  OhlcvBarDto,
  ResearchTrialDto,
} from "@bolsa/shared";
import type { BacktestStrategyType } from "@bolsa/shared";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { AiInfoButton } from "@/features/ai/ai-info-button";
import {
  isFinalistsSavedStatusMessage,
  isSemifinalShortcutStatusMessage,
} from "@/features/backtests/assistant-cycle-orchestrator";
import { instrumentTopIsDurable } from "@/features/backtests/backtest-assistant-full-cycle";
import type { AssistantSessionProgress } from "@/features/backtests/backtest-assistant-completion";
import type { AssistantPrefs } from "@/features/backtests/backtest-assistant-prefs";
import type {
  BatchRankRow,
  BatchSortKey,
} from "@/features/backtests/backtest-batch-run";
import {
  exportBacktestJson,
  exportEquityCsv,
  exportTradesCsv,
} from "@/features/backtests/backtest-export";
import type {
  ExplorePresetRow,
  ExploreSortKey,
} from "@/features/backtests/backtest-explore-value";
import { isAnalysisResultFocus } from "@/features/backtests/backtest-hub-nav";
import { BacktestHubLayout } from "@/features/backtests/backtest-hub-layout";
import type { LabBoardZone } from "@/features/backtests/backtest-lab-board-types";
import { padLabZones } from "@/features/backtests/backtest-lab-board-types";
import type { ListAutoBoardState } from "@/features/backtests/backtest-list-auto-board";
import { BacktestListAutoBoardPanel } from "@/features/backtests/backtest-list-auto-board-panel";
import {
  listAutoUniverseHint,
  listModeWizardTitle,
  type ListAutoCampaign,
} from "@/features/backtests/backtest-list-auto";
import type { OptimizeSeed } from "@/features/backtests/backtest-optimize-seed";
import {
  PERIOD_PRESET_OPTIONS,
  effectiveDiaD,
  isDiaDInPast,
  todayIsoDate,
  type PeriodPreset,
} from "@/features/backtests/backtest-period";
import { BacktestResultDetail } from "@/features/backtests/backtest-result-detail";
import { BacktestResultFocusCoach } from "@/features/backtests/backtest-result-focus-coach";
import { BacktestResultFocusFinalists } from "@/features/backtests/backtest-result-focus-finalists";
import { BacktestResultFocusLab } from "@/features/backtests/backtest-result-focus-lab";
import { BacktestResultFundamental } from "@/features/backtests/backtest-result-fundamental";
import { BacktestResultRanking } from "@/features/backtests/backtest-result-ranking";
import type { StrategyMatrixFilter } from "@/features/backtests/backtest-strategy-matrix";
import { BacktestStrategyMatrixPanel } from "@/features/backtests/backtest-strategy-matrix-panel";
import { BacktestUniversePicker } from "@/features/backtests/backtest-universe-picker";
import { BacktestWizardAdvancedOptions } from "@/features/backtests/backtest-wizard-advanced-options";
import { BacktestWizardListAuto } from "@/features/backtests/backtest-wizard-list-auto";
import { BacktestWizardMassCompare } from "@/features/backtests/backtest-wizard-mass-compare";
import { BacktestWizardProbeList } from "@/features/backtests/backtest-wizard-probe-list";
import type { BacktestZonePrefs } from "@/features/backtests/backtest-zone-prefs";
import {
  loadBacktestZonePrefs,
  patchStrategyMatrixTablePrefs,
} from "@/features/backtests/backtest-zone-prefs";
import type {
  ResultFocus,
  RunSource,
  StrategiesListFilter,
  UniverseMode,
} from "@/features/backtests/backtests-page.constants";
import { formatDiaDDisplay } from "@/features/backtests/dia-d-favorites";
import type { CoachProfilePolicy } from "@/features/backtests/coach-profile-policy";
import { InstrumentStrategyTopPanel } from "@/features/backtests/instrument-strategy-top-panel";
import type { FinalistSlotUse } from "@/features/backtests/instrument-strategy-top-panel";
import { FundamentalCardPanel } from "@/features/instruments/fundamental-card-panel";
import { PAPER_PATH_MONITOR } from "@/features/settings/paper-paths-copy";
import { StrategyMonitorPanel } from "@/features/backtests/strategy-monitor-panel";
import { useBacktestDerivedData } from "@/features/backtests/hooks/use-backtest-derived-data";
import { useBacktestPageMutations } from "@/features/backtests/hooks/use-backtest-page-mutations";
import { useBacktestPageQueries } from "@/features/backtests/hooks/use-backtest-page-queries";
import { createBacktestAssistantController } from "@/features/backtests/lib/backtest-assistant-controller";
import { createBacktestLabCoachHandlers } from "@/features/backtests/lib/backtest-lab-handlers";
import {
  createBacktestListAutoController,
  type ListAutoUiState,
} from "@/features/backtests/lib/backtest-list-auto-controller";
import { createBacktestOrchestration } from "@/features/backtests/lib/backtest-orchestration";
import { createBacktestPageNavigation } from "@/features/backtests/lib/backtest-page-navigation";

type Queries = ReturnType<typeof useBacktestPageQueries>;
type Mutations = ReturnType<typeof useBacktestPageMutations>;
type Derived = ReturnType<typeof useBacktestDerivedData>;
type Nav = ReturnType<typeof createBacktestPageNavigation>;
type ListAutoCtl = ReturnType<typeof createBacktestListAutoController>;
type Orch = ReturnType<typeof createBacktestOrchestration>;
type LabCoach = ReturnType<typeof createBacktestLabCoachHandlers>;
type AsstCtl = ReturnType<typeof createBacktestAssistantController>;

type CoachGateState = {
  needsAck: boolean;
  ack: boolean;
  postLab: boolean;
  canSaveTop: boolean;
};

export type BacktestPageViewModel = {
  // --- shared (wizard + result + monitor) ---
  isWide: boolean;
  universeMode: UniverseMode;
  setUniverseMode: Dispatch<SetStateAction<UniverseMode>>;
  instrumentId: string;
  selectInstrument: Nav["selectInstrument"];
  listId: string;
  setListId: Dispatch<SetStateAction<string>>;
  listDetail: Derived["listDetail"];
  lists: Derived["lists"];
  instruments: Derived["instruments"];
  instrumentLabels: Derived["instrumentLabels"];
  instrumentSymbol: Derived["instrumentSymbol"];
  instrumentTop: Derived["instrumentTop"];
  assistantPrefs: AssistantPrefs;
  updateAssistantPrefs: AsstCtl["updateAssistantPrefs"];
  diaD: string;
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  initialCash: string;
  commissionBps: string;
  slippageBps: string;
  runTimeframe: ChartTimeframe;
  listAutoBoard: ListAutoBoardState | null;
  listAutoUi: ListAutoUiState | null;
  listAutoRef: MutableRefObject<ListAutoCampaign | null>;
  pauseListAuto: ListAutoCtl["pauseListAuto"];
  resumeListAuto: ListAutoCtl["resumeListAuto"];
  stopListAuto: ListAutoCtl["stopListAuto"];
  forceListAutoRescanRemaining: ListAutoCtl["forceListAutoRescanRemaining"];
  openInstrumentInValor: Nav["openInstrumentInValor"];
  resultFocus: ResultFocus;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  fullCycleActive: boolean;
  coachPass: "initial" | "post_lab";
  setCoachPass: Dispatch<SetStateAction<"initial" | "post_lab">>;
  queryClient: QueryClient;
  patchSearchParams: Nav["patchSearchParams"];
  selectedId: string | null;
  selectRun: Nav["selectRun"];
  savedStrategyId: string;
  setSavedStrategyId: Dispatch<SetStateAction<string>>;
  setRunSource: Dispatch<SetStateAction<RunSource>>;
  openFinalistChecklist: (slot: FinalistSlotUse) => void;
  proposeFinalistSupervisedSlot: (slot: FinalistSlotUse) => void;
  proposeFinalistMutation: {
    isPending: boolean;
    variables?: { strategyDefinitionId?: string };
  };
  coachProfilePolicy: CoachProfilePolicy;
  exploreRows: ExplorePresetRow[];
  exploreRunning: boolean;
  hasExistingTopForSave: Derived["hasExistingTopForSave"];
  settleFullCycle: Orch["settleFullCycle"];
  setAssistantStatus: Dispatch<SetStateAction<string | null>>;
  setLabImprovedThisCycle: Dispatch<SetStateAction<number>>;
  exploreOkCount: Derived["exploreOkCount"];
  labOpenedThisRun: boolean;
  labZones: LabBoardZone[] | null;
  optimizeSeed: OptimizeSeed | null;
  setLabZones: Dispatch<SetStateAction<LabBoardZone[] | null>>;
  setOptimizeSeed: Dispatch<SetStateAction<OptimizeSeed | null>>;

  // --- wizard ---
  listsQuery: Pick<Queries["listsQuery"], "isLoading">;
  listMembersWithStatus: Derived["listMembersWithStatus"];
  listQuotesQuery: Pick<Queries["listQuotesQuery"], "isLoading">;
  listTopsQuery: Pick<Queries["listTopsQuery"], "isFetching" | "data">;
  applyChartDraft: (draft: ChartStrategySetupDraft) => void;
  saveChartStrategyMutation: Pick<
    Mutations["saveChartStrategyMutation"],
    "mutate" | "isPending"
  >;
  listAutoSkipWithFinalists: boolean;
  setListAutoSkipWithFinalists: Dispatch<SetStateAction<boolean>>;
  runSource: RunSource;
  strategyType: BacktestStrategyType;
  setStrategyType: Dispatch<SetStateAction<BacktestStrategyType>>;
  strategies: Derived["strategies"];
  batchRunning: boolean;
  batchProgress: { done: number; total: number };
  batchAbortRef: MutableRefObject<AbortController | null>;
  runListBatch: Orch["runListBatch"];
  matrixRowsForUi: Derived["matrixRowsForUi"];
  matrixFilter: StrategyMatrixFilter;
  matrixSelectedIds: Set<string>;
  zonePrefs: BacktestZonePrefs;
  setZonePrefs: Dispatch<SetStateAction<BacktestZonePrefs>>;
  coachRunProgress: Derived["coachRunProgress"];
  runMutation: Pick<Mutations["runMutation"], "isPending">;
  toggleMatrixRow: (rowId: string) => void;
  applyMatrixSelection: (
    mode: "replace" | "add" | "remove",
    rowIds: string[],
  ) => void;
  runCoachFromMatrixUi: (opts?: {
    forceResim?: boolean;
  }) => void | Promise<void>;
  matrixCoachTargetIds: Derived["matrixCoachTargetIds"];
  exploreAbortRef: MutableRefObject<AbortController | null>;
  openLibrary: Nav["openLibrary"];
  pushToast: (message: string) => void;
  batchError: string | null;
  exploreError: string | null;
  setPeriodPreset: Dispatch<SetStateAction<PeriodPreset>>;
  setCustomDateFrom: Dispatch<SetStateAction<string>>;
  setCustomDateTo: Dispatch<SetStateAction<string>>;
  setInitialCash: Dispatch<SetStateAction<string>>;
  setRunTimeframe: Dispatch<SetStateAction<ChartTimeframe>>;
  setCommissionBps: Dispatch<SetStateAction<string>>;
  setSlippageBps: Dispatch<SetStateAction<string>>;
  setMatrixFilter: Dispatch<SetStateAction<StrategyMatrixFilter>>;
  setMatrixSelectedIds: Dispatch<SetStateAction<Set<string>>>;

  // --- result ---
  assistantStepComplete: Derived["assistantStepComplete"];
  assistantProgress: AssistantSessionProgress;
  topStrategyIds: Queries["topStrategyIds"];
  setLabOpenedThisRun: Dispatch<SetStateAction<boolean>>;
  setStrategiesListFilter: Dispatch<SetStateAction<StrategiesListFilter>>;
  awaitingAck: boolean;
  batchRows: BatchRankRow[];
  exploreSort: ExploreSortKey;
  setExploreSort: Dispatch<SetStateAction<ExploreSortKey>>;
  startOptimizeFromExplore: Orch["startOptimizeFromExplore"];
  optimizeSemifinalFromCoach: LabCoach["optimizeSemifinalFromCoach"];
  currentFinalistsInputFingerprint: ListAutoCtl["currentFinalistsInputFingerprint"];
  semifinalShortcutArmed: boolean;
  labImprovedThisCycle: number;
  setAwaitingAck: Dispatch<SetStateAction<boolean>>;
  setAwaitingAckStage: Dispatch<SetStateAction<"coach1" | "revalidate" | null>>;
  setCoachGate: Dispatch<SetStateAction<CoachGateState>>;
  exploreProgress: { done: number; total: number };
  instrumentsQuery: Pick<Queries["instrumentsQuery"], "data">;
  reanalyzeLabWithCoach: LabCoach["reanalyzeLabWithCoach"];
  batchSort: BatchSortKey;
  setBatchSort: Dispatch<SetStateAction<BatchSortKey>>;
  diaDVerifyActive: boolean;
  detail: Derived["detail"];
  detailQuery: Pick<
    Queries["detailQuery"],
    "isFetching" | "data" | "isError" | "error"
  >;
  preferOpenAnalysis: boolean;
  setPreferOpenAnalysis: Dispatch<SetStateAction<boolean>>;
  replayBarsQuery: {
    data?: { data?: OhlcvBarDto[] };
    isLoading: boolean;
    isError: boolean;
  };
  equityCurve: BacktestEquityPointDto[];
  focusTimestamp: string | null;
  focusedTrade: BacktestTradeDto | null;
  setFocusTimestamp: Dispatch<SetStateAction<string | null>>;
  focusTrade: (timestamp: string) => void;
  displayTrialId: string | undefined;
  displayMetrics: ResearchTrialDto["isMetrics"] | undefined;
  linkedTrial: ResearchTrialDto | undefined;
  drawingMarkers: DrawingReplayMarkerDto[];
  detailFinalistBadge: Derived["detailFinalistBadge"];
  startOptimizeFromDetail: () => void;
  deployPaperMutation: Pick<
    Mutations["deployPaperMutation"],
    "isPending" | "error" | "mutate"
  >;
  manifestSummary: {
    engine: string;
    dataVersion: string | null | undefined;
    barCount: number | null | undefined;
    metricsHash: string;
  } | null;

  // --- monitor: universeMode + listId (shared) ---
};

export type BacktestPageRunSharedVm = Pick<
  BacktestPageViewModel,
  | "isWide"
  | "universeMode"
  | "setUniverseMode"
  | "instrumentId"
  | "selectInstrument"
  | "listId"
  | "setListId"
  | "listDetail"
  | "lists"
  | "instruments"
  | "instrumentLabels"
  | "instrumentSymbol"
  | "instrumentTop"
  | "assistantPrefs"
  | "updateAssistantPrefs"
  | "diaD"
  | "periodPreset"
  | "customDateFrom"
  | "customDateTo"
  | "initialCash"
  | "commissionBps"
  | "slippageBps"
  | "runTimeframe"
  | "listAutoBoard"
  | "listAutoUi"
  | "listAutoRef"
  | "pauseListAuto"
  | "resumeListAuto"
  | "stopListAuto"
  | "forceListAutoRescanRemaining"
  | "openInstrumentInValor"
  | "resultFocus"
  | "setResultFocus"
  | "fullCycleActive"
  | "coachPass"
  | "setCoachPass"
  | "queryClient"
  | "patchSearchParams"
  | "selectedId"
  | "selectRun"
  | "savedStrategyId"
  | "setSavedStrategyId"
  | "setRunSource"
  | "openFinalistChecklist"
  | "proposeFinalistSupervisedSlot"
  | "proposeFinalistMutation"
  | "coachProfilePolicy"
  | "exploreRows"
  | "exploreRunning"
  | "hasExistingTopForSave"
  | "settleFullCycle"
  | "setAssistantStatus"
  | "setLabImprovedThisCycle"
  | "exploreOkCount"
  | "labOpenedThisRun"
  | "labZones"
  | "optimizeSeed"
  | "setLabZones"
  | "setOptimizeSeed"
>;

export type BacktestPageRunWizardVm = Pick<
  BacktestPageViewModel,
  | "listsQuery"
  | "listMembersWithStatus"
  | "listQuotesQuery"
  | "listTopsQuery"
  | "applyChartDraft"
  | "saveChartStrategyMutation"
  | "listAutoSkipWithFinalists"
  | "setListAutoSkipWithFinalists"
  | "runSource"
  | "strategyType"
  | "setStrategyType"
  | "strategies"
  | "batchRunning"
  | "batchProgress"
  | "batchAbortRef"
  | "runListBatch"
  | "matrixRowsForUi"
  | "matrixFilter"
  | "matrixSelectedIds"
  | "zonePrefs"
  | "setZonePrefs"
  | "coachRunProgress"
  | "runMutation"
  | "toggleMatrixRow"
  | "applyMatrixSelection"
  | "runCoachFromMatrixUi"
  | "matrixCoachTargetIds"
  | "exploreAbortRef"
  | "openLibrary"
  | "pushToast"
  | "batchError"
  | "exploreError"
  | "setPeriodPreset"
  | "setCustomDateFrom"
  | "setCustomDateTo"
  | "setInitialCash"
  | "setRunTimeframe"
  | "setCommissionBps"
  | "setSlippageBps"
  | "setMatrixFilter"
  | "setMatrixSelectedIds"
>;

export type BacktestPageRunResultVm = Pick<
  BacktestPageViewModel,
  | "assistantStepComplete"
  | "assistantProgress"
  | "topStrategyIds"
  | "setLabOpenedThisRun"
  | "setStrategiesListFilter"
  | "awaitingAck"
  | "batchRows"
  | "exploreSort"
  | "setExploreSort"
  | "startOptimizeFromExplore"
  | "optimizeSemifinalFromCoach"
  | "currentFinalistsInputFingerprint"
  | "semifinalShortcutArmed"
  | "labImprovedThisCycle"
  | "setAwaitingAck"
  | "setAwaitingAckStage"
  | "setCoachGate"
  | "exploreProgress"
  | "instrumentsQuery"
  | "reanalyzeLabWithCoach"
  | "batchSort"
  | "setBatchSort"
  | "diaDVerifyActive"
  | "detail"
  | "detailQuery"
  | "preferOpenAnalysis"
  | "setPreferOpenAnalysis"
  | "replayBarsQuery"
  | "equityCurve"
  | "focusTimestamp"
  | "focusedTrade"
  | "setFocusTimestamp"
  | "focusTrade"
  | "displayTrialId"
  | "displayMetrics"
  | "linkedTrial"
  | "drawingMarkers"
  | "detailFinalistBadge"
  | "startOptimizeFromDetail"
  | "deployPaperMutation"
  | "manifestSummary"
>;

/** Monitor slot reuses shared universeMode + listId. */
export type BacktestPageRunMonitorVm = Pick<
  BacktestPageViewModel,
  "universeMode" | "listId"
>;

export function BacktestsPageRunTab({ vm }: { vm: BacktestPageViewModel }) {
  const {
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
  } = vm;

  return (
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
                      Origen DÍA D {formatDiaDDisplay(effectiveDiaD(diaD))}
                    </strong>
                    {" — "}
                    embudo con datos ≤ esa fecha (cámbialo junto al título).
                    Tras Play → Finalistas #1 →{" "}
                    <strong className="font-semibold">Verificar D→hoy</strong>.
                  </p>
                ) : (
                  <p>
                    Origen{" "}
                    <strong className="text-foreground/80">
                      Hoy {formatDiaDDisplay(todayIsoDate())}
                    </strong>
                    . Para simular «como si hoy fuera el pasado», abre el
                    selector junto a{" "}
                    <strong className="text-foreground/80">Backtesting</strong>{" "}
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
                    instrumentCount={listDetail?.instrumentIds.length ?? 0}
                    skipWithFinalists={listAutoSkipWithFinalists}
                    onSkipWithFinalistsChange={setListAutoSkipWithFinalists}
                    board={listAutoBoard}
                    ui={listAutoUi}
                    selectedInstrumentId={instrumentId || null}
                    onOpenInstrument={openInstrumentInValor}
                    onPause={pauseListAuto}
                    onResume={resumeListAuto}
                    onStop={stopListAuto}
                    onForceRescanRemaining={forceListAutoRescanRemaining}
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
                  onClearSelection={() => setMatrixSelectedIds(new Set())}
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
                  onGoToStrategies={() => openLibrary({ library: "all" })}
                  onOpenInLibrary={(row) => {
                    if (row.kind === "saved" && row.strategyDefinitionId) {
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
                    if (row.kind !== "saved" || !row.strategyDefinitionId)
                      return;
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
                        void queryClient.invalidateQueries({
                          queryKey: ["strategies"],
                        });
                        void queryClient.invalidateQueries({
                          queryKey: ["instrument-strategy-top"],
                        });
                        if (savedStrategyId === row.strategyDefinitionId) {
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
                    onOpenChecklist={(slot) => openFinalistChecklist(slot)}
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
                        !(t.id === "detail" && resultFocus === "ranking") &&
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
                    {t.id === "finalists" && assistantProgress.finalistsSkipped
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
                    variant={resultFocus === "ranking" ? "default" : "outline"}
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
                      resultFocus === "list_auto" ? "default" : "outline"
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
                    {listAutoBoard.done && !listAutoBoard.aborted ? "✓ " : ""}
                    Lista AUTO
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent
              className={cn(
                "min-h-0 flex-1 p-3",
                isAnalysisResultFocus(resultFocus) && (detail || instrumentId)
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
                          onForceRescanRemaining: forceListAutoRescanRemaining,
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
                  PERIOD_PRESET_OPTIONS.find((o) => o.value === periodPreset)
                    ?.label ?? periodPreset
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
                    (row) => row.status === "ok" && row.barCount != null,
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
                experimentAsOf={isDiaDInPast(diaD) ? effectiveDiaD(diaD) : null}
                autoSaveSemifinal={semifinalShortcutArmed}
                cycleCoach1Active={
                  fullCycleActive && coachPass === "initial" && !exploreRunning
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
                  settleFullCycle(saved ? "saved" : "skip_finalists", message);
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
                      return [r.runId!, cached?.data?.equityCurve] as const;
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
                  maxDrawdownSoftPct={coachProfilePolicy.maxDrawdownSoftPct}
                  profileId={coachProfilePolicy.profileId}
                  profileHorizon={coachProfilePolicy.horizon}
                  profileRiskTolerance={coachProfilePolicy.riskTolerance}
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
                      setOptimizeSeed(next.find((z) => z.seed)?.seed ?? null);
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
                          const [stratsRes, topRes] = await Promise.all([
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
                    instruments.find((i) => i.id === instrumentId)?.symbol ??
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
                    listDetail?.name ?? lists.find((l) => l.id === listId)?.name
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
                  detailDataInstrumentId={detailQuery.data?.data?.instrumentId}
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
  );
}
