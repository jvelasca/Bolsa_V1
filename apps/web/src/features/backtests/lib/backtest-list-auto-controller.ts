/**
 * Controlador Lista AUTO extraído de `BacktestsPage` — campaña, supervisión, frescura.
 *
 * Extraído de `backtests-page.tsx` (Track B B7) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 *
 * Mezcla factory (funciones, como B6) y hook de efectos (como B5).
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
import type { QueryClient } from "@tanstack/react-query";
import type {
  ChartTimeframe,
  InstrumentListDetailDto,
  InstrumentWithMetaDto,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { useListAutoActivityStore } from "@/stores/list-auto-activity-store";
import {
  emptyAssistantProgress,
  type AssistantSessionProgress,
} from "@/features/backtests/backtest-assistant-completion";
import {
  saveAssistantPrefs,
  type AssistantPrefs,
} from "@/features/backtests/backtest-assistant-prefs";
import type { AssistantStepId } from "@/features/backtests/backtest-assistant-steps";
import { mergeUniverseTargetIds } from "@/features/backtests/backtest-coach-lote";
import {
  buildFinalistsFreshnessStamp,
  buildFinalistsInputFingerprint,
  formatFreshnessAge,
  freshnessSkipDenialLabel,
  instrumentLastBarDate,
  mergeFreshnessIntoCoachFacts,
  readFinalistsFreshness,
  readLocalFreshnessFingerprint,
  shouldSkipFinalistsSearch,
  writeLocalFreshnessFingerprint,
} from "@/features/backtests/backtest-finalists-freshness";
import {
  LIST_AUTO_BATCH_SIZE,
  LIST_AUTO_HARD_MAX,
  confirmListAutoOverCap,
  createListAutoCampaign,
  filterListAutoIdsWithoutFinalists,
  listAutoBatchCount,
  listAutoDoneStatus,
  listAutoPausedStatus,
  listAutoProgressLabel,
  pauseListAutoCampaign,
  resumeListAutoCampaign,
  shouldStartListAuto,
  stopListAutoCampaign,
  type FullCycleSettleReason,
  type ListAutoCampaign,
} from "@/features/backtests/backtest-list-auto";
import {
  captureListAutoBeforeTop,
  createListAutoBoard,
  enrichListAutoBoardLabels,
  listAutoTopFingerprint,
  markListAutoBoardAborted,
  markListAutoBoardDone,
  markListAutoBoardPaused,
  markListAutoBoardRunning,
  type ListAutoBoardState,
} from "@/features/backtests/backtest-list-auto-board";
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
} from "@/features/backtests/backtest-list-auto-persist";
import {
  effectiveDiaD,
  resolveBacktestWindow,
  type PeriodPreset,
} from "@/features/backtests/backtest-period";
import {
  STRATEGY_MATRIX_MAX_SELECTED,
  exploreBatteryRowIds,
  type StrategyMatrixRow,
} from "@/features/backtests/backtest-strategy-matrix";
import type {
  HubTab,
  ResultFocus,
  UniverseMode,
} from "@/features/backtests/backtests-page.constants";
import {
  buildProfilePolicyFingerprintSegment,
  type CoachProfilePolicy,
} from "@/features/backtests/coach-profile-policy";
import {
  LIST_AUTO_SOFT_PAUSE_EVENT,
  LIST_AUTO_SOFT_RESUME_EVENT,
} from "@/features/trading/estudio-update-control";
import {
  clearPendingEstudioLaneTick,
  takePendingEstudioLaneTick,
} from "@/features/trading/estudio-supervision";

export type ListAutoUiState = {
  index: number;
  total: number;
  symbol: string;
};

export type ListAutoStartOverrides = {
  forceRescan?: boolean;
  skipConfirm?: boolean;
  instrumentIds?: string[] | null;
};

export type BacktestListAutoControllerCtx = {
  queryClient: QueryClient;
  universeMode: UniverseMode;
  listId: string;
  listDetail:
    | Pick<InstrumentListDetailDto, "id" | "name" | "instrumentIds">
    | null
    | undefined;
  instrumentLabels: Record<string, { symbol: string; name: string }>;
  instruments: InstrumentWithMetaDto[];
  listAutoSkipWithFinalists: boolean;
  assistantPrefs: AssistantPrefs;
  runTimeframe: ChartTimeframe;
  listAutoBoard: ListAutoBoardState | null;
  matrixRowsForUi: StrategyMatrixRow[];
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  diaD: string;
  initialCash: string;
  commissionBps: string;
  slippageBps: string;
  coachProfilePolicy: CoachProfilePolicy;

  listAutoRef: MutableRefObject<ListAutoCampaign | null>;
  listAutoStartOverridesRef: MutableRefObject<ListAutoStartOverrides | null>;
  listAutoExcludedIdsRef: MutableRefObject<Set<string>>;
  listAutoPendingStartRef: MutableRefObject<number | null>;
  listAutoFreshnessMemoryRef: MutableRefObject<Map<string, string>>;
  listAutoSettleLockRef: MutableRefObject<number | null>;
  assistantChainRef: MutableRefObject<string>;
  exploreAbortRef: MutableRefObject<AbortController | null>;

  setAssistantStatus: Dispatch<SetStateAction<string | null>>;
  setListAutoBoard: Dispatch<SetStateAction<ListAutoBoardState | null>>;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  setListAutoUi: Dispatch<SetStateAction<ListAutoUiState | null>>;
  setFullCycleActive: Dispatch<SetStateAction<boolean>>;
  setAssistantProgress: Dispatch<SetStateAction<AssistantSessionProgress>>;
  setAwaitingAck: Dispatch<SetStateAction<boolean>>;
  setAwaitingAckStage: Dispatch<SetStateAction<"coach1" | "revalidate" | null>>;
  setLabImprovedThisCycle: Dispatch<SetStateAction<number>>;
  setSemifinalShortcutArmed: Dispatch<SetStateAction<boolean>>;
  setLabOpenedThisRun: Dispatch<SetStateAction<boolean>>;
  setListAutoStartToken: Dispatch<SetStateAction<number>>;
  setExploreRunning: Dispatch<SetStateAction<boolean>>;

  selectInstrument: (
    id: string,
    opts?: { forceClear?: boolean; preserveListAutoFocus?: boolean },
  ) => void;
};

export type BacktestListAutoController = {
  startListAutoCampaign: () => Promise<boolean>;
  symbolForInstrument: (id: string) => string;
  queueListAutoTicker: (index: number) => void;
  persistListAutoPauseNow: (
    campaign: ListAutoCampaign,
    board: ListAutoBoardState,
  ) => void;
  clearPersistedListAutoPause: () => void;
  pauseListAuto: () => void;
  resumeListAuto: () => void;
  stopListAuto: () => void;
  forceListAutoRescanRemaining: () => void;
  abortListAutoCampaign: (opts?: { keepContinue?: boolean }) => void;
  currentFinalistsInputFingerprint: (forInstrumentId: string) => string;
  rememberListAutoFreshness: (
    forInstrumentId: string,
    fingerprint: string,
    opts?: { lab?: boolean },
  ) => Promise<void>;
};

export function createBacktestListAutoController(
  ctx: BacktestListAutoControllerCtx,
): BacktestListAutoController {
  const {
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
  } = ctx;

  function symbolForInstrument(id: string): string {
    return (
      instrumentLabels[id]?.symbol ??
      instruments.find((i) => i.id === id)?.symbol ??
      id.slice(0, 8)
    );
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
      setResultFocus("list_auto");
      return;
    }

    let nextIndex = index;
    while (
      nextIndex < campaign.instrumentIds.length &&
      listAutoExcludedIdsRef.current.has(campaign.instrumentIds[nextIndex]!)
    ) {
      nextIndex += 1;
    }
    if (nextIndex !== index) {
      queueListAutoTicker(nextIndex);
      return;
    }

    const id = campaign.instrumentIds[index]!;
    campaign.index = index;
    const symbol = symbolForInstrument(id);
    void import("@/features/trading/estudio-process-status").then((m) => {
      m.emitEstudioProcessRunning({
        instrumentId: id,
        lane: m.laneFromListAutoMode(campaign.forceRescan),
      });
    });
    setListAutoUi({ index, total: campaign.instrumentIds.length, symbol });
    setListAutoBoard((b) => (b ? markListAutoBoardRunning(b, index) : b));
    setAssistantProgress(emptyAssistantProgress());
    setAwaitingAck(false);
    setAwaitingAckStage(null);
    setLabImprovedThisCycle(0);
    setSemifinalShortcutArmed(false);
    setLabOpenedThisRun(false);
    assistantChainRef.current = "";
    setFullCycleActive(true);
    setAssistantStatus(
      `${listAutoProgressLabel({ index, total: campaign.instrumentIds.length, symbol })}: comprobando frescura…`,
    );
    setResultFocus("list_auto");

    listAutoPendingStartRef.current = index;
    // preserveListAutoFocus: no pisar tablero ni abortar; el token fuerza el efecto
    // aunque instrumentId ya fuera este valor (bug: Play no omitía tras reinicio).
    selectInstrument(id, { forceClear: true, preserveListAutoFocus: true });
    setListAutoStartToken((n) => n + 1);
  }

  function pauseListAuto() {
    const campaign = listAutoRef.current;
    if (!campaign || campaign.aborted || campaign.paused) return;
    pauseListAutoCampaign(campaign);
    setListAutoBoard((b) => {
      const next = b ? markListAutoBoardPaused(b, true) : b;
      if (next && !next.rows.some((r) => r.phase === "running")) {
        persistListAutoPauseNow(campaign, next);
      }
      return next;
    });
    setAssistantStatus(
      "Pausa: termina el valor actual y no arranca el siguiente…",
    );
    setResultFocus("list_auto");
  }

  function resumeListAuto() {
    const campaign = listAutoRef.current;
    if (!campaign || campaign.aborted || !campaign.paused) return;
    if (listAutoBoard?.rows.some((r) => r.phase === "running")) {
      setAssistantStatus("Pausa: espera a que termine el valor en curso…");
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
        : "Lista AUTO: Stop.",
    );
    setResultFocus("list_auto");
  }

  function forceListAutoRescanRemaining() {
    const campaign = listAutoRef.current;
    if (!campaign || campaign.aborted) return;
    campaign.forceRescan = true;
    // Olvida memoria de sesión de los que aún no están settled.
    if (listAutoBoard) {
      for (const row of listAutoBoard.rows) {
        if (row.phase === "queued" || row.phase === "running") {
          listAutoFreshnessMemoryRef.current.delete(row.instrumentId);
        }
      }
    }
    setAssistantStatus("CORE-R: reevaluar resto (ignora frescura / Omitido).");
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
        .filter((r) => r.kind === "saved" && r.savedBucket === "optimized")
        .map((r) => r.rowId),
      includeOptimized: assistantPrefs.universe.includeOptimizedStrategies,
      mineRowIds: matrixRowsForUi
        .filter((r) => r.kind === "saved" && r.savedBucket === "mine")
        .map((r) => r.rowId),
      includeMine: assistantPrefs.universe.includeMineStrategies,
      max: STRATEGY_MATRIX_MAX_SELECTED,
    });
    return buildFinalistsInputFingerprint({
      instrumentId: forInstrumentId,
      timeframe: runTimeframe,
      periodPreset,
      dateFrom: customDateFrom,
      dateTo:
        resolveBacktestWindow(periodPreset, customDateFrom, customDateTo, diaD)
          .dateTo ?? customDateTo,
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
        queryKey: ["instrument-strategy-top", forInstrumentId, runTimeframe],
        queryFn: () =>
          api.getInstrumentStrategyTop(forInstrumentId, runTimeframe),
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
        queryKey: ["instrument-strategy-top", forInstrumentId, runTimeframe],
      });
      void queryClient.invalidateQueries({
        queryKey: ["instrument-strategy-tops-batch"],
      });
    } catch {
      // localStorage (si hubo TOP active) + memoria de sesión cubren el skip.
    }
  }

  async function startListAutoCampaign(): Promise<boolean> {
    if (
      !shouldStartListAuto({
        universeMode,
        fullCycleOnPlay: assistantPrefs.fullCycleOnPlay,
        listId,
        instrumentCount: listDetail?.instrumentIds.length ?? 0,
      })
    ) {
      return false;
    }
    if (listAutoRef.current && !listAutoRef.current.aborted) {
      setAssistantStatus("Lista AUTO ya en curso. Usa ↻ para cancelar.");
      return true;
    }
    const overrides = listAutoStartOverridesRef.current;
    listAutoStartOverridesRef.current = null;

    const instrumentIds = listDetail!.instrumentIds;
    const overrideIds = overrides?.instrumentIds?.filter(Boolean) ?? null;

    let queueIds = overrideIds?.length ? overrideIds : instrumentIds;
    // Excluir valores quitados de Estudio durante supervisión.
    if (listAutoExcludedIdsRef.current.size > 0) {
      queueIds = queueIds.filter(
        (id) => !listAutoExcludedIdsRef.current.has(id),
      );
    }
    if (listAutoSkipWithFinalists && !overrideIds?.length) {
      setAssistantStatus("Lista AUTO: filtrando valores sin Finalistas…");
      queueIds = await filterListAutoIdsWithoutFinalists(queueIds, (id) =>
        api.getInstrumentStrategyTop(id, runTimeframe),
      );
      if (queueIds.length === 0) {
        setAssistantStatus(
          "Lista AUTO: todos tienen Finalistas (nada que encolar).",
        );
        return true;
      }
    }
    if (
      !confirmListAutoOverCap(queueIds.length, {
        skipConfirm:
          overrides?.skipConfirm === true ||
          assistantPrefs.listAutoSkipOverCapConfirm,
      })
    ) {
      setAssistantStatus("Lista AUTO cancelada (confirmación tandas).");
      return true;
    }
    const campaign = createListAutoCampaign({
      listId,
      instrumentIds: queueIds,
      forceRescan: Boolean(overrides?.forceRescan),
    });
    if (campaign.instrumentIds.length === 0) {
      setAssistantStatus("La lista no tiene valores.");
      return true;
    }

    // Resolver tickers vía quotes de lista (catálogo global puede no tener SP100 recién importado).
    const labels: Record<string, { symbol: string; name: string }> = {
      ...instrumentLabels,
    };
    const missing = campaign.instrumentIds.filter((id) => !labels[id]?.symbol);
    if (missing.length > 0) {
      setAssistantStatus("Lista AUTO: cargando tickers de la lista…");
      try {
        const res = await api.getListQuotes(listId);
        queryClient.setQueryData(["list-quotes", listId], res);
        for (const q of res.data) {
          labels[q.id] = { symbol: q.symbol, name: q.name };
        }
        void queryClient.invalidateQueries({ queryKey: ["instruments"] });
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
      listAutoFreshnessMemoryRef.current = new Map(
        Object.entries(cont.freshnessMemory),
      );
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
    setResultFocus("list_auto");
    const startSym = resolveSym(campaign.instrumentIds[startIndex]!);
    const n = campaign.instrumentIds.length;
    const batches = listAutoBatchCount(n);
    const tandaHint =
      n > LIST_AUTO_BATCH_SIZE
        ? ` · ${batches} tandas de ~${LIST_AUTO_BATCH_SIZE}`
        : "";
    const hardHint =
      (listDetail!.instrumentIds.length > LIST_AUTO_HARD_MAX ||
        queueIds.length > LIST_AUTO_HARD_MAX) &&
      n === LIST_AUTO_HARD_MAX
        ? ` (tope ${LIST_AUTO_HARD_MAX})`
        : "";
    setAssistantStatus(
      cont
        ? `Lista AUTO: continúa desde #${startIndex + 1} ${startSym} (tras Stop) · ${n} valor(es)${tandaHint}…`
        : `Lista AUTO: ${n} valor(es)${tandaHint}${hardHint}…`,
    );
    queueListAutoTicker(startIndex);
    return true;
  }

  return {
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
  };
}

export type UseBacktestListAutoEffectsParams = {
  listAutoBoard: ListAutoBoardState | null;
  listAutoUi: ListAutoUiState | null;
  assistantStatus: string | null;
  listId: string;
  listDetail:
    | Pick<InstrumentListDetailDto, "id" | "name" | "instrumentIds">
    | null
    | undefined;
  instrumentLabels: Record<string, { symbol: string; name: string }>;
  universeMode: UniverseMode;
  instrumentId: string;
  freshnessContextReady: boolean;
  instruments: InstrumentWithMetaDto[];
  runTimeframe: ChartTimeframe;
  coachProfilePolicy: CoachProfilePolicy;
  assistantPrefs: AssistantPrefs;
  listAutoStartToken: number;
  listAutoRef: MutableRefObject<ListAutoCampaign | null>;
  supervisionStartPendingRef: MutableRefObject<string | null>;
  listAutoStartOverridesRef: MutableRefObject<ListAutoStartOverrides | null>;
  listAutoExcludedIdsRef: MutableRefObject<Set<string>>;
  listAutoPauseRestoredRef: MutableRefObject<boolean>;
  listAutoPendingStartRef: MutableRefObject<number | null>;
  listAutoFreshnessMemoryRef: MutableRefObject<Map<string, string>>;
  setUniverseMode: Dispatch<SetStateAction<UniverseMode>>;
  setListId: Dispatch<SetStateAction<string>>;
  setAssistantPrefs: Dispatch<SetStateAction<AssistantPrefs>>;
  setAssistantStatus: Dispatch<SetStateAction<string | null>>;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  setListAutoStartToken: Dispatch<SetStateAction<number>>;
  setListAutoBoard: Dispatch<SetStateAction<ListAutoBoardState | null>>;
  setListAutoUi: Dispatch<SetStateAction<ListAutoUiState | null>>;
  setTab: (next: HubTab) => void;
  pauseListAuto: () => void;
  resumeListAuto: () => void;
  persistListAutoPauseNow: (
    campaign: ListAutoCampaign,
    board: ListAutoBoardState,
  ) => void;
  startListAutoCampaign: () => Promise<boolean>;
  symbolForInstrument: (id: string) => string;
  currentFinalistsInputFingerprint: (forInstrumentId: string) => string;
  rememberListAutoFreshness: (
    forInstrumentId: string,
    fingerprint: string,
    opts?: { lab?: boolean },
  ) => Promise<void>;
  queryClient: QueryClient;
  executeAssistantStep: (
    step: AssistantStepId,
    opts?: { fullCycle?: boolean },
  ) => void | Promise<void>;
  settleFullCycle: (
    reason: FullCycleSettleReason,
    statusMessage?: string,
  ) => void;
};

export function useBacktestListAutoEffects(
  params: UseBacktestListAutoEffectsParams,
): void {
  const {
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
  } = params;

  /** Publica resumen Lista AUTO → barra Trading / badge nav (y keep-alive). */
  useEffect(() => {
    const board = listAutoBoard;
    const campaignLive = Boolean(
      listAutoRef.current && !listAutoRef.current.aborted,
    );
    const boardLive = Boolean(board && !board.done && !board.aborted);
    const active = campaignLive || boardLive || Boolean(listAutoUi);

    if (!active) {
      const snap = useListAutoActivityStore.getState();
      if (snap.active) {
        const detail = snap.detail ?? "";
        // No borrar Actualizar/alta en curso o en pausa (banner Estudio / keep-alive).
        const estudioUpdateBusy =
          snap.listId === "estudio" &&
          (snap.paused ||
            detail.startsWith("Actualizar") ||
            detail.startsWith("Alta Estudio") ||
            detail.startsWith("Redescubrir") ||
            detail.startsWith("Termina ") ||
            detail.startsWith("Pausa ·"));
        if (!estudioUpdateBusy) {
          snap.clear();
        }
      }
      return;
    }

    const index =
      listAutoUi?.index ??
      board?.rows.findIndex((r) => r.phase === "running") ??
      0;
    const total =
      listAutoUi?.total ||
      board?.rows.length ||
      listAutoRef.current?.instrumentIds.length ||
      0;
    const symbol =
      listAutoUi?.symbol || (index >= 0 && board?.rows[index]?.symbol) || "…";

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
  }, [listAutoBoard, listAutoUi, assistantStatus, listId, listDetail?.name]);

  // Si las quotes llegan después de crear el tablero, corrige columna VALOR.
  useEffect(() => {
    setListAutoBoard((prev) =>
      prev ? enrichListAutoBoardLabels(prev, instrumentLabels) : prev,
    );
  }, [instrumentLabels]);

  // ADR-024: Supervisión ON/OFF + ticks capas media/lenta → Lista AUTO + exclusiones.
  useEffect(() => {
    const armListAutoForList = (listIdTarget: string, status: string) => {
      supervisionStartPendingRef.current = listIdTarget;
      setUniverseMode("list");
      setListId(listIdTarget);
      setAssistantPrefs((prev) => {
        if (prev.fullCycleOnPlay) return prev;
        const next = { ...prev, fullCycleOnPlay: true };
        saveAssistantPrefs(next);
        return next;
      });
      setAssistantStatus(status);
      setResultFocus("list_auto");
      // Fuerza el efecto de arranque aunque ya estemos en la misma lista.
      setListAutoStartToken((n) => n + 1);
    };

    const onSupervision = (ev: Event) => {
      const detail = (ev as CustomEvent<{ enabled: boolean; listId: string }>)
        .detail;
      if (!detail) return;
      if (detail.enabled) {
        listAutoExcludedIdsRef.current.clear();
        listAutoStartOverridesRef.current = {
          forceRescan: false,
          skipConfirm: true,
          instrumentIds: null,
        };
        armListAutoForList(
          detail.listId,
          `Supervisión ON · frescura inicial («${detail.listId}»)…`,
        );
      } else {
        supervisionStartPendingRef.current = null;
        listAutoStartOverridesRef.current = null;
        const campaign = listAutoRef.current;
        if (campaign && !campaign.aborted && !campaign.paused) {
          pauseListAutoCampaign(campaign);
          setListAutoBoard((b) => (b ? markListAutoBoardPaused(b, true) : b));
          setAssistantStatus("Supervisión OFF · Lista AUTO en pausa.");
        }
      }
    };

    const handleLaneTickDetail = (detail: {
      listId: string;
      lane: "freshness" | "rediscover";
      forceRescan: boolean;
      skipConfirm: boolean;
      instrumentIds: string[] | null;
    }) => {
      clearPendingEstudioLaneTick();
      if (!detail?.listId) return;
      if (listAutoRef.current && !listAutoRef.current.aborted) {
        setAssistantStatus(
          `Supervisión · tick ${detail.lane} diferido (campaña en curso).`,
        );
        return;
      }
      listAutoStartOverridesRef.current = {
        forceRescan: detail.forceRescan,
        skipConfirm: detail.skipConfirm,
        instrumentIds: detail.instrumentIds,
      };
      const label =
        detail.lane === "rediscover"
          ? `Supervisión · rediscubrimiento (${detail.instrumentIds?.length ?? 0} valores)…`
          : `Supervisión · frescura Lab («${detail.listId}»)…`;
      armListAutoForList(detail.listId, label);
    };

    const onLaneTick = (ev: Event) => {
      const detail = (
        ev as CustomEvent<{
          listId: string;
          lane: "freshness" | "rediscover";
          forceRescan: boolean;
          skipConfirm: boolean;
          instrumentIds: string[] | null;
        }>
      ).detail;
      if (!detail) return;
      handleLaneTickDetail(detail);
    };

    const onUnsubscribe = (ev: Event) => {
      const ids =
        (ev as CustomEvent<{ instrumentIds: string[] }>).detail
          ?.instrumentIds ?? [];
      for (const id of ids) listAutoExcludedIdsRef.current.add(id);
      const campaign = listAutoRef.current;
      if (!campaign || campaign.aborted) return;
      const cur = campaign.instrumentIds[campaign.index];
      if (cur && ids.includes(cur) && !campaign.paused) {
        setAssistantStatus("Estudio: valor quitado · se omite en la campaña.");
      }
    };
    window.addEventListener("bolsa-estudio-supervision-changed", onSupervision);
    window.addEventListener("bolsa-estudio-lane-tick", onLaneTick);
    window.addEventListener("bolsa-estudio-unsubscribe", onUnsubscribe);
    // Si Actualizar/alta emitió el tick antes de montar keep-alive, drenarlo ahora.
    const pending = takePendingEstudioLaneTick();
    if (pending) handleLaneTickDetail(pending);
    return () => {
      window.removeEventListener(
        "bolsa-estudio-supervision-changed",
        onSupervision,
      );
      window.removeEventListener("bolsa-estudio-lane-tick", onLaneTick);
      window.removeEventListener("bolsa-estudio-unsubscribe", onUnsubscribe);
    };
  }, []);

  useEffect(() => {
    const pending = supervisionStartPendingRef.current;
    if (!pending) return;
    if (universeMode !== "list" || listId !== pending) return;
    if (!listDetail?.instrumentIds?.length || listDetail.id !== pending) return;
    if (listAutoRef.current && !listAutoRef.current.aborted) {
      supervisionStartPendingRef.current = null;
      return;
    }
    supervisionStartPendingRef.current = null;
    void startListAutoCampaign();
    // startListAutoCampaign cierra sobre estado actual; deps acotadas a list ready.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- arranque puntual Supervisión / lane ticks
  }, [
    universeMode,
    listId,
    listDetail?.id,
    listDetail?.instrumentIds?.length,
    listAutoStartToken,
  ]);

  // Banner Estudio (Trading): pausa/reanuda suave de Lista AUTO sin estar en /backtests.
  useEffect(() => {
    const onPause = () => pauseListAuto();
    const onResume = () => resumeListAuto();
    window.addEventListener(LIST_AUTO_SOFT_PAUSE_EVENT, onPause);
    window.addEventListener(LIST_AUTO_SOFT_RESUME_EVENT, onResume);
    return () => {
      window.removeEventListener(LIST_AUTO_SOFT_PAUSE_EVENT, onPause);
      window.removeEventListener(LIST_AUTO_SOFT_RESUME_EVENT, onResume);
    };
  });

  // Restaurar Lista AUTO en pausa tras reinicio de la app
  useEffect(() => {
    if (listAutoPauseRestoredRef.current) return;
    listAutoPauseRestoredRef.current = true;
    const snap = loadListAutoPausedSnapshot();
    if (!snap) return;
    const campaign = campaignFromPausedSnapshot(snap);
    listAutoRef.current = campaign;
    setUniverseMode("list");
    setListId(campaign.listId);
    setListAutoBoard(snap.board);
    const row = snap.board.rows[campaign.index];
    const symbol =
      row?.symbol ?? campaign.instrumentIds[campaign.index]?.slice(0, 8) ?? "…";
    setListAutoUi({
      index: campaign.index,
      total: campaign.instrumentIds.length,
      symbol,
    });
    if (snap.freshnessMemory) {
      listAutoFreshnessMemoryRef.current = new Map(
        Object.entries(snap.freshnessMemory),
      );
    }
    setTab("run");
    setResultFocus("list_auto");
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
    if (listAutoBoard.rows.some((r) => r.phase === "running")) return;
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
          queryKey: ["instrument-strategy-top", expectedId, runTimeframe],
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
          memoryFingerprint:
            listAutoFreshnessMemoryRef.current.get(expectedId) ?? null,
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
          let next = captureListAutoBeforeTop(
            b,
            pending,
            listAutoTopFingerprint(top),
          );
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
            skip.reason === "local_fresh"
              ? local?.lastSearchAt
              : (stored?.lastSearchAt ?? local?.lastSearchAt ?? top?.updatedAt);
          const why =
            skip.reason === "session_fresh"
              ? "ya analizado en esta sesión"
              : skip.reason === "local_fresh"
                ? "huella local igual"
                : skip.reason === "bar_hysteresis"
                  ? "barra reciente (histéresis)"
                  : skip.reason === "adopt_existing_top"
                    ? "Finalistas active adoptados"
                    : "datos igual";
          settleFullCycle(
            "skip_fresh",
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
        void executeAssistantStep("universe", { fullCycle: true });
      } catch (err) {
        if (cancelled) return;
        if (listAutoPendingStartRef.current !== pending) return;
        const live = listAutoRef.current;
        if (!live || live.aborted) return;

        // Sin TOP legible no podemos saber si hay Finalistas → no Omitido a ciegas (v1.2).
        listAutoPendingStartRef.current = null;
        const msg = err instanceof Error ? err.message : "error TOP";
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
          "skip_lab",
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
}
