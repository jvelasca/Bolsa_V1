/**
 * Hub Backtesting (`/backtests`) — orquestación UI del embudo.
 *
 * Ciclo completo / Lista AUTO / Finalistas Checklist+Proponer / Lab handoff.
 * Política motor: `backtest-assistant-full-cycle.ts`, `backtest-list-auto.ts`.
 * Documentación: `docs/engineering/session-handoff-2026-07-30.md` ·
 * `docs/engineering/list-auto-ops-2026-07-29.md`.
 *
 * Thin shell (Track B B12): composición en `useBacktestPageModel`.
 */

import { STRATEGY_OPTIONS } from "@/features/backtests/backtests-page.constants";
import { BacktestHubTabsBar } from "@/features/backtests/backtest-hub-tabs";
import { Navigate } from "react-router-dom";
import { BacktestAssistantRail } from "@/features/backtests/backtest-assistant-rail";
import { listAutoPlayTitle } from "@/features/backtests/backtest-list-auto";
import { BacktestLibraryTab } from "@/features/backtests/backtest-library-tab";
import { BacktestHistoryTab } from "@/features/backtests/backtest-history-tab";
import {
  BacktestZoneSettingsButton,
  BacktestZoneSettingsDialog,
} from "@/features/backtests/backtest-zone-settings-dialog";
import { PAPER_PATH_LAB } from "@/features/settings/paper-paths-copy";
import { BacktestDiaDOriginControl } from "@/features/backtests/backtest-dia-d-origin-control";
import { DiaDVerifyHost } from "@/features/backtests/dia-d-verify-host";
import { UniverseChip } from "@/features/platform/universe-chip";
import { BacktestsPageJobsTab } from "@/features/backtests/backtests-page-jobs-tab";
import { BacktestsPageRunTab } from "@/features/backtests/backtests-page-run-tab";
import { useBacktestPageModel } from "@/features/backtests/hooks/use-backtest-page-model";

export function BacktestsPage() {
  const model = useBacktestPageModel();

  // Redirección legacy ejecutada tras el hook de composición para respetar la
  // Regla de Hooks (el componente no debe variar el número de hooks entre
  // renders por un early return). Solo en la ruta real, no en keep-alive Lista
  // AUTO fuera de /backtests.
  if (model.onBacktestsRoute && model.tabParam === "screeners") {
    return <Navigate to="/screeners" replace />;
  }

  const { runTabVm, jobsTabVm, chrome } = model;
  const {
    diaDVerifyFullBleed,
    diaD,
    handleDiaDChange,
    tab,
    setTab,
    openLibrary,
    strategiesListFilter,
    setZoneSettingsOpen,
    zoneSettingsOpen,
    setZonePrefs,
    pruneHistory,
    assistantStep,
    assistantPrefs,
    updateAssistantPrefs,
    assistantProgress,
    coachPass,
    fullCycleActive,
    listAutoUi,
    awaitingAck,
    awaitingAckStage,
    assistantStatus,
    goAssistantStep,
    playAssistantSequence,
    coachProfileRailLabel,
    coachProfilePolicy,
    exploreRunning,
    semifinalEnqueuePending,
    listAutoBoard,
    pauseListAuto,
    resumeListAuto,
    stopListAuto,
    instrumentId,
    universeMode,
    listId,
    listDetail,
    resetAssistantRail,
    strategies,
    filteredStrategies,
    setLibraryFilter,
    mineFilters,
    setMineFilters,
    patchSearchParams,
    mineFilterTimeframes,
    mineFilterOrigins,
    mineFilterInstruments,
    instrumentSymbol,
    runTimeframe,
    instrumentTop,
    topStrategyIds,
    instrumentSymbolById,
    libraryFocusStrategyId,
    libraryFocusPreset,
    cloneOpen,
    setCloneOpen,
    newStrategyName,
    setNewStrategyName,
    newStrategyPreset,
    setNewStrategyPreset,
    createStrategyMutation,
    setStrategyType,
    setRunSource,
    setSavedStrategyId,
    setResultFocus,
    setAssistantStatus,
    openFinalistChecklist,
    proposeFinalistSupervisedSlot,
    proposeFinalistMutation,
    savedStrategyId,
    setLibraryFocusStrategyId,
    runs,
    zonePrefs,
    selectedId,
    selectRun,
  } = chrome;

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
            onReset={resetAssistantRail}
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
