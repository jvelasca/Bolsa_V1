/**
 * Monitor Finalistas — tablero de estado (read-only).
 *
 * Montado en Ayuda → Backtesting y en el hub Probar (`embedded`).
 * Une TOP + DEMO/paper + cola F3 vía `strategy-monitor.ts` (soft cap 40).
 * CORE-R v1–v1.13: informe Lista AUTO + PnL live DEMO → cola humana;
 * Narrar cola; cron shell (Estudio canónica ADR-024); Adoptar mandato SEMI;
 * chip barra; toast Abrir Monitor; **Hecho todos**.
 * Enlaces: Finalistas · Checklist (`openAnalysis=1`) · Supervisado F3.
 *
 * Precondición de auto-paper D. **No** ejecuta, despliega ni unifica A/B/C.
 *
 * @see PAPER_PATH_MONITOR
 * @see BACKTESTING_CORE_R_GUIDE
 * @see docs/engineering/operativa-test-plan-2026-07-31.md
 * @see docs/engineering/research-lifecycle.md § Monitor Finalistas MVP
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueries, useQuery } from '@tanstack/react-query';
import {
  ESTUDIO_LIST_NAME,
  resolveEstudioListId,
  type InstrumentStrategyTopV1,
} from '@bolsa/shared';
import { formatPaperLabEvidence } from '@/features/accounts/paper-lab-evidence';
import {
  buildStrategyMonitorRow,
  sliceMonitorInstruments,
  STRATEGY_MONITOR_MAX,
  strategyMonitorChecklistHref,
  type StrategyMonitorInstrument,
} from '@/features/backtests/strategy-monitor';
import {
  STRATEGY_ADOPTION_LABELS,
  getAdoptionState,
} from '@/features/platform/strategy-adoption';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import {
  adoptMandateFromCoreR,
  canAdoptCoreRMandate,
  coreRAdoptDenyMessage,
} from '@/features/backtests/core-r-adopt-mandate';
import {
  buildCoreRPaperPnlReviewRow,
  coreRAccountReturnPct,
  coreRNeedsAction,
  coreRPaperPnlDegradation,
  coreRVerdictLabel,
  listCoreRActionRows,
  readCoreRReport,
  readCoreRVerdictForInstrument,
  type CoreRPaperPnlSnap,
  type CoreRReportRow,
} from '@/features/backtests/core-r-judgment';
import {
  CORE_R_SCHEDULER_EVENT,
  CORE_R_SCHEDULER_INTERVAL_PRESETS,
  clampCoreRSchedulerInterval,
  loadCoreRSchedulerPrefs,
  resolveCoreRSchedulerListId,
  saveCoreRSchedulerPrefs,
  type CoreRSchedulerPrefs,
  type CoreRSchedulerTickDetail,
} from '@/features/backtests/core-r-scheduler';
import { runCoreRSchedulerTick } from '@/features/backtests/core-r-scheduler-tick';
import { instrumentTopBacktestsHref } from '@/features/backtests/instrument-strategy-top-panel';
import { PAPER_PATH_MONITOR } from '@/features/settings/paper-paths-copy';
import { useDemoBookPrefs } from '@/features/trading/use-demo-book-prefs';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  primaryCoreRAction,
  useCoreRReviewQueueStore,
  type CoreRReviewQueueItem,
} from '@/stores/core-r-review-queue-store';
import {
  openHelpAiPlatform,
  useSupervisedF3QueueStore,
} from '@/stores/supervised-f3-queue-store';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button, buttonVariants } from '@/components/ui/button';

function formatCoreRReturnPct(pct: number): string {
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

function snapFromAccountSummary(opts: {
  accountId: string;
  initialDeposit: number;
  totalEquity: number;
  totalUnrealizedPnl: number;
}): CoreRPaperPnlSnap | null {
  const returnPct = coreRAccountReturnPct(opts.initialDeposit, opts.totalEquity);
  if (returnPct == null) return null;
  return {
    accountId: opts.accountId,
    returnPct,
    totalUnrealizedPnl: opts.totalUnrealizedPnl,
    totalEquity: opts.totalEquity,
    initialDeposit: opts.initialDeposit,
  };
}

export type StrategyMonitorPanelProps = {
  className?: string;
  /** Prefill desde Universo modo Lista del hub. */
  initialListId?: string;
  /**
   * Variante hub Probar: mismo panel, aviso más corto.
   * Ayuda usa el default (copy completa).
   */
  embedded?: boolean;
};

export function StrategyMonitorPanel({
  className,
  initialListId,
  embedded = false,
}: StrategyMonitorPanelProps) {
  const { effectiveAccountId } = useActiveAccount();
  const bookPrefs = useDemoBookPrefs();
  const [listId, setListId] = useState(initialListId ?? '');
  const [timeframe] = useState('1d');
  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const setActive = useSupervisedF3QueueStore((s) => s.setActive);
  const syncCoreR = useCoreRReviewQueueStore((s) => s.syncFromReport);
  const dismissCoreR = useCoreRReviewQueueStore((s) => s.dismiss);
  const dismissOpenCoreR = useCoreRReviewQueueStore((s) => s.dismissOpen);
  const coreRItems = useCoreRReviewQueueStore((s) => s.items);
  const [coreRSyncMsg, setCoreRSyncMsg] = useState<string | null>(null);
  const [schedPrefs, setSchedPrefs] = useState<CoreRSchedulerPrefs>(() =>
    loadCoreRSchedulerPrefs(),
  );
  const [coreRNarrative, setCoreRNarrative] = useState<{
    engine: string;
    paragraphs: string[];
    band?: string;
    disclaimer?: string;
  } | null>(null);
  const [coreRNarrating, setCoreRNarrating] = useState(false);

  useEffect(() => {
    if (initialListId) setListId(initialListId);
  }, [initialListId]);

  const listsQuery = useQuery({
    queryKey: ['lists'],
    queryFn: () => api.getLists(),
    staleTime: 60_000,
  });
  const lists = listsQuery.data?.data ?? [];
  const estudioListId = useMemo(() => resolveEstudioListId(lists), [lists]);

  const effectiveListId = listId || lists[0]?.id || '';

  const listDetailQuery = useQuery({
    queryKey: ['list', effectiveListId],
    queryFn: () => api.getList(effectiveListId),
    enabled: Boolean(effectiveListId),
    staleTime: 60_000,
  });

  const instrumentsQuery = useQuery({
    queryKey: ['instruments'],
    queryFn: () => api.getInstruments(),
    staleTime: 60_000,
  });

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    // Misma forma que useActiveAccount: array plano (no { data }).
    queryFn: async () => (await api.getAccounts()).data,
    staleTime: 30_000,
  });

  const monitorInstruments = useMemo((): StrategyMonitorInstrument[] => {
    const ids = listDetailQuery.data?.data?.instrumentIds ?? [];
    const byId = new Map(
      (instrumentsQuery.data?.data ?? []).map((i) => [i.id, i] as const),
    );
    const rows = ids.map((id) => {
      const inst = byId.get(id);
      return {
        id,
        symbol: inst?.symbol ?? id.slice(0, 8),
        name: inst?.name,
      };
    });
    return sliceMonitorInstruments(rows);
  }, [listDetailQuery.data?.data?.instrumentIds, instrumentsQuery.data?.data]);

  const monitorIdsKey = useMemo(
    () => monitorInstruments.map((i) => i.id).join(','),
    [monitorInstruments],
  );

  const topsBatchQuery = useQuery({
    queryKey: ['instrument-strategy-tops-batch', 'monitor', timeframe, monitorIdsKey],
    queryFn: () =>
      api.queryInstrumentStrategyTops({
        instrumentIds: monitorInstruments.map((i) => i.id),
        timeframe,
      }),
    enabled: monitorInstruments.length > 0,
    staleTime: 30_000,
    retry: false,
  });

  const accounts = Array.isArray(accountsQuery.data) ? accountsQuery.data : [];
  const topByInstrumentId = useMemo(() => {
    const map = new Map<string, InstrumentStrategyTopV1>();
    for (const top of topsBatchQuery.data?.data ?? []) {
      map.set(top.instrumentId, top);
    }
    return map;
  }, [topsBatchQuery.data?.data]);
  const rows = useMemo(() => {
    return monitorInstruments.map((inst) =>
      buildStrategyMonitorRow({
        instrument: inst,
        timeframe,
        top: topByInstrumentId.get(inst.id) ?? null,
        accounts,
        queue: queueItems,
      }),
    );
  }, [monitorInstruments, topByInstrumentId, accounts, queueItems, timeframe]);

  const paperAccountIds = useMemo(() => {
    const ids: string[] = [];
    const seen = new Set<string>();
    for (const r of rows) {
      const id = r.paperAccount?.id;
      if (!id || seen.has(id)) continue;
      seen.add(id);
      ids.push(id);
    }
    return ids;
  }, [rows]);

  const summaryQueries = useQueries({
    queries: paperAccountIds.map((id) => ({
      queryKey: ['account-summary', id],
      queryFn: async () => (await api.getAccountSummary(id)).data,
      enabled: Boolean(id),
      staleTime: 30_000,
      retry: false,
    })),
  });

  const pnlByAccountId = useMemo(() => {
    const map = new Map<string, CoreRPaperPnlSnap>();
    paperAccountIds.forEach((id, i) => {
      const summary = summaryQueries[i]?.data;
      if (!summary) return;
      const snap = snapFromAccountSummary({
        accountId: id,
        initialDeposit: summary.account.initialDeposit,
        totalEquity: summary.totalEquity,
        totalUnrealizedPnl: summary.totalUnrealizedPnl,
      });
      if (snap) map.set(id, snap);
    });
    return map;
  }, [paperAccountIds, summaryQueries]);

  const withTop = rows.filter((r) => r.top && r.top.slots.length > 0);
  const withoutTop = rows.length - withTop.length;
  const loadingTops = topsBatchQuery.isLoading || topsBatchQuery.isFetching;
  const listCount = listDetailQuery.data?.data?.instrumentIds.length ?? 0;
  const listLoaded = Boolean(effectiveListId) && !listDetailQuery.isLoading;
  const listEmpty = listLoaded && listCount === 0;

  const coreRReport = effectiveListId ? readCoreRReport(effectiveListId) : null;
  const coreRAttentionInReport = listCoreRActionRows(coreRReport).length;
  const coreROpen = useMemo(
    () =>
      coreRItems.filter(
        (i) => i.listId === effectiveListId && i.status === 'open',
      ),
    [coreRItems, effectiveListId],
  );

  const buildPnlExtraRows = useCallback((): CoreRReportRow[] => {
    const extras: CoreRReportRow[] = [];
    for (const row of withTop) {
      const acc = row.paperAccount;
      if (!acc) continue;
      const pnl = pnlByAccountId.get(acc.id);
      if (!pnl) continue;
      const extra = buildCoreRPaperPnlReviewRow({
        instrumentId: row.instrumentId,
        symbol: row.symbol,
        timeframe: row.timeframe,
        pnl,
        slot1RunId: row.slot1RunId,
      });
      if (extra) extras.push(extra);
    }
    return extras;
  }, [withTop, pnlByAccountId]);

  const onSyncCoreRQueue = useCallback(() => {
    if (!effectiveListId) return;
    const report = readCoreRReport(effectiveListId);
    const extras = buildPnlExtraRows();
    const n = syncCoreR(effectiveListId, report, extras);
    const open = useCoreRReviewQueueStore.getState().openCount(effectiveListId);
    const reportActions = listCoreRActionRows(report).length;
    if (!report && extras.length === 0) {
      setCoreRSyncMsg(
        'Sin informe CORE-R ni PnL a revisar. Termina Lista AUTO o vincula DEMO al TOP.',
      );
    } else if (reportActions === 0 && extras.length === 0) {
      setCoreRSyncMsg('Nada a revisar (informe OK · PnL DEMO ≥ −5%).');
    } else if (n === 0) {
      setCoreRSyncMsg(`Cola al día · ${open} abiertas.`);
    } else {
      const pnlNote = extras.length > 0 ? ` · ${extras.length} por PnL` : '';
      setCoreRSyncMsg(`+${n} en cola · ${open} abiertas${pnlNote}.`);
    }
  }, [effectiveListId, buildPnlExtraRows, syncCoreR]);

  useEffect(() => {
    // Listen shell ticks (scope=shell) to refresh copy; Monitor-only ticks if scope=monitor.
    const onShellTick = (ev: Event) => {
      const detail = (ev as CustomEvent<CoreRSchedulerTickDetail>).detail;
      if (!detail || detail.listId !== effectiveListId) return;
      setSchedPrefs(loadCoreRSchedulerPrefs());
      if (detail.added > 0) {
        const open = useCoreRReviewQueueStore.getState().openCount(effectiveListId);
        setCoreRSyncMsg(`Auto shell · +${detail.added} · ${open} abiertas.`);
      }
    };
    window.addEventListener(CORE_R_SCHEDULER_EVENT, onShellTick);
    return () => window.removeEventListener(CORE_R_SCHEDULER_EVENT, onShellTick);
  }, [effectiveListId]);

  useEffect(() => {
    if (!schedPrefs.enabled || !effectiveListId) return;
    if (schedPrefs.scope !== 'monitor') return;
    const runIfDue = () => {
      void runCoreRSchedulerTick({ scopeFilter: 'monitor' }).then((res) => {
        setSchedPrefs(loadCoreRSchedulerPrefs());
        if (res && !res.skipped && res.added > 0) {
          const open = useCoreRReviewQueueStore.getState().openCount(effectiveListId);
          setCoreRSyncMsg(`Auto · +${res.added} · ${open} abiertas.`);
        }
      });
    };
    runIfDue();
    const id = window.setInterval(runIfDue, 60_000);
    return () => window.clearInterval(id);
  }, [schedPrefs.enabled, schedPrefs.scope, effectiveListId]);

  const onToggleScheduler = (enabled: boolean) => {
    const prev = loadCoreRSchedulerPrefs();
    const boundListId = enabled
      ? resolveCoreRSchedulerListId({
          estudioListId,
          monitorListId: effectiveListId || null,
          previousListId: prev.listId,
        })
      : prev.listId;
    const next: CoreRSchedulerPrefs = {
      ...prev,
      enabled,
      listId: boundListId,
      scope: 'shell',
    };
    saveCoreRSchedulerPrefs(next);
    setSchedPrefs(next);
    if (enabled && boundListId && boundListId !== effectiveListId) {
      setListId(boundListId);
      setCoreRSyncMsg(
        estudioListId && boundListId === estudioListId
          ? `Auto-sync · lista «${ESTUDIO_LIST_NAME}».`
          : `Auto-sync · lista fijada.`,
      );
    }
  };

  const onSchedulerIntervalChange = (minutes: number) => {
    const next: CoreRSchedulerPrefs = {
      ...loadCoreRSchedulerPrefs(),
      intervalMinutes: clampCoreRSchedulerInterval(minutes),
    };
    saveCoreRSchedulerPrefs(next);
    setSchedPrefs(next);
  };

  const onAdoptCoreRMandate = async (item: CoreRReviewQueueItem) => {
    if (!effectiveAccountId) {
      setCoreRSyncMsg(coreRAdoptDenyMessage('no_account'));
      return;
    }
    let top = topByInstrumentId.get(item.instrumentId) ?? null;
    if (!top) {
      try {
        const res = await api.getInstrumentStrategyTop(
          item.instrumentId,
          item.timeframe || timeframe,
        );
        top = res.data ?? null;
      } catch {
        setCoreRSyncMsg(coreRAdoptDenyMessage('no_slot'));
        return;
      }
    }
    const res = adoptMandateFromCoreR({
      instrumentId: item.instrumentId,
      accountId: effectiveAccountId,
      verdict: item.verdict,
      timeframe: item.timeframe || timeframe,
      top,
      mode: bookPrefs.mode,
    });
    if (!res.ok) {
      setCoreRSyncMsg(coreRAdoptDenyMessage(res.reason));
      return;
    }
    dismissCoreR(item.id);
    setCoreRSyncMsg(
      `Mandato adoptado · ${item.symbol} · ${res.slot.label} (SEMI · CORE-R).`,
    );
  };

  const onNarrateCoreRQueue = async () => {
    if (!effectiveListId || coreROpen.length === 0) return;
    setCoreRNarrating(true);
    setCoreRNarrative(null);
    try {
      const res = await api.explainCoreRReviewEvidence({
        listId: effectiveListId,
        timeframe,
        rows: coreROpen.map((i) => ({
          instrumentId: i.instrumentId,
          symbol: i.symbol,
          verdict: i.verdict,
          reason: i.reason,
        })),
      });
      const data = res.data;
      setCoreRNarrative({
        engine: data.engine,
        paragraphs: data.payload.paragraphs ?? [],
        band: data.payload.band,
        disclaimer: data.payload.disclaimer,
      });
    } catch (err) {
      setCoreRSyncMsg(
        `Narración falló: ${err instanceof Error ? err.message : 'error'}`,
      );
    } finally {
      setCoreRNarrating(false);
    }
  };

  return (
    <Card
      className={cn(embedded && 'border-border/70 shadow-none', className)}
      id={embedded ? 'strategy-monitor-hub' : 'strategy-monitor-panel'}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{PAPER_PATH_MONITOR.shortTitle}</CardTitle>
        <CardDescription>{PAPER_PATH_MONITOR.blurb}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p
          className={cn(
            'rounded-md border px-3 py-2 text-[11px] leading-snug text-muted-foreground',
            embedded
              ? 'border-border/60 bg-muted/20'
              : 'border-amber-500/30 bg-amber-500/5',
          )}
        >
          {embedded
            ? 'Solo lectura · no despliega ni ejecuta. Checklist = paper (A); F3 = Supervisado (C). CORE-R propone; no cambia mandato hasta aceptar.'
            : PAPER_PATH_MONITOR.warnLine}
        </p>

        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Lista a monitorizar
          <select
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            value={effectiveListId}
            onChange={(e) => setListId(e.target.value)}
            disabled={listsQuery.isLoading || lists.length === 0}
          >
            {lists.length === 0 ? (
              <option value="">Sin listas</option>
            ) : (
              lists.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                  {typeof l.itemCount === 'number' ? ` (${l.itemCount})` : ''}
                </option>
              ))
            )}
          </select>
        </label>

        {listCount > STRATEGY_MONITOR_MAX ? (
          <p className="text-[11px] text-muted-foreground">
            Mostrando los primeros {STRATEGY_MONITOR_MAX} de {listCount}.
          </p>
        ) : null}

        {effectiveListId ? (
          <div className="space-y-2 rounded-md border border-border/60 bg-muted/15 px-2.5 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] font-medium text-foreground">
                Cola CORE-R
                {coreROpen.length > 0 ? (
                  <span className="ml-1 text-muted-foreground">
                    · {coreROpen.length} abierta
                    {coreROpen.length === 1 ? '' : 's'}
                  </span>
                ) : null}
              </p>
              <div className="flex flex-wrap gap-1.5">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  onClick={onSyncCoreRQueue}
                  title="Informe Lista AUTO + PnL DEMO ≤ −5%"
                >
                  Encolar revisiones
                  {coreRAttentionInReport > 0
                    ? ` (${coreRAttentionInReport})`
                    : ''}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-[11px]"
                  disabled={coreROpen.length === 0 || coreRNarrating}
                  onClick={() => void onNarrateCoreRQueue()}
                  title="Narrar cola (heurística; LLM si hay Ollama)"
                >
                  {coreRNarrating ? 'Narrando…' : 'Narrar cola'}
                </Button>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="rounded border-border"
                  checked={schedPrefs.enabled}
                  onChange={(e) => onToggleScheduler(e.target.checked)}
                />
                Auto-sync app abierta
              </label>
              <label className="flex items-center gap-1">
                cada
                <select
                  className="rounded border border-border bg-background px-1 py-0.5 text-[10px] text-foreground"
                  value={schedPrefs.intervalMinutes}
                  onChange={(e) =>
                    onSchedulerIntervalChange(Number(e.target.value))
                  }
                  title="Cadencia del cron shell CORE-R"
                >
                  {!CORE_R_SCHEDULER_INTERVAL_PRESETS.includes(
                    schedPrefs.intervalMinutes as (typeof CORE_R_SCHEDULER_INTERVAL_PRESETS)[number],
                  ) ? (
                    <option value={schedPrefs.intervalMinutes}>
                      {schedPrefs.intervalMinutes} min
                    </option>
                  ) : null}
                  {CORE_R_SCHEDULER_INTERVAL_PRESETS.map((m) => (
                    <option key={m} value={m}>
                      {m >= 1440 ? '24 h' : `${m} min`}
                    </option>
                  ))}
                </select>
              </label>
              <span>
                {schedPrefs.listId
                  ? estudioListId && schedPrefs.listId === estudioListId
                    ? `· ${ESTUDIO_LIST_NAME}`
                    : '· lista fijada'
                  : null}
                {!estudioListId ? (
                  <span
                    className="ml-1 text-muted-foreground/80"
                    title={`La lista API «${ESTUDIO_LIST_NAME}» se crea al cargar Listas.`}
                  >
                    (sin {ESTUDIO_LIST_NAME})
                  </span>
                ) : null}
              </span>
              {schedPrefs.lastTickAt ? (
                <span title={schedPrefs.lastTickAt}>
                  · último{' '}
                  {new Date(schedPrefs.lastTickAt).toLocaleString('es-ES', {
                    dateStyle: 'short',
                    timeStyle: 'short',
                  })}
                </span>
              ) : null}
            </div>
            {coreRSyncMsg ? (
              <p className="text-[10px] text-muted-foreground">{coreRSyncMsg}</p>
            ) : (
              <p className="text-[10px] text-muted-foreground">
                Encola juicios Lista AUTO y degradación PnL DEMO (−5% Lab /
                −10% cambio). Prefiere «{ESTUDIO_LIST_NAME}» al activar. No
                ejecuta ni pisa TOP.
              </p>
            )}
            {coreRNarrative && coreRNarrative.paragraphs.length > 0 ? (
              <div className="space-y-1 rounded border border-border/50 bg-background/40 px-2 py-1.5">
                <p className="text-[10px] text-muted-foreground">
                  Narración · {coreRNarrative.engine}
                  {coreRNarrative.band ? ` · ${coreRNarrative.band}` : ''}
                </p>
                {coreRNarrative.paragraphs.map((p, i) => (
                  <p key={i} className="text-[11px] leading-snug text-foreground/90">
                    {p}
                  </p>
                ))}
                {coreRNarrative.disclaimer ? (
                  <p className="text-[9px] text-muted-foreground">
                    {coreRNarrative.disclaimer}
                  </p>
                ) : null}
              </div>
            ) : null}
            {coreROpen.length > 0 ? (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[10px] text-muted-foreground">
                    Cola · {coreROpen.length} abierta
                    {coreROpen.length === 1 ? '' : 's'}
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-6 text-[10px]"
                    title="Marcar todas las abiertas de esta lista como Hecho"
                    onClick={() => {
                      if (!effectiveListId) return;
                      const n = dismissOpenCoreR(effectiveListId);
                      if (n > 0) {
                        setCoreRSyncMsg(
                          `${n} marcada${n === 1 ? '' : 's'} Hecho (lista)`,
                        );
                      }
                    }}
                  >
                    Hecho todos
                  </Button>
                </div>
              <ul className="max-h-36 space-y-1.5 overflow-y-auto">
                {coreROpen.map((item) => {
                  const primary = primaryCoreRAction(item.actions);
                  const top = topByInstrumentId.get(item.instrumentId) ?? null;
                  const showAdopt = canAdoptCoreRMandate({
                    verdict: item.verdict,
                    mode: bookPrefs.mode,
                    accountId: effectiveAccountId,
                    top,
                  });
                  return (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-1.5 rounded border border-border/50 bg-background/50 px-2 py-1.5"
                    >
                      <div className="min-w-0">
                        <p className="text-[11px] font-medium text-foreground">
                          {item.symbol}{' '}
                          <span className="font-normal text-amber-200/90">
                            {coreRVerdictLabel(item.verdict)}
                          </span>
                        </p>
                        <p
                          className="truncate text-[10px] text-muted-foreground"
                          title={item.reason}
                        >
                          {item.reason}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {showAdopt ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="default"
                            className="h-6 text-[10px]"
                            title="Aceptar propuesta CORE-R · abre mandato TRADING (SEMI)"
                            onClick={() => void onAdoptCoreRMandate(item)}
                          >
                            Adoptar
                          </Button>
                        ) : null}
                        {primary?.href ? (
                          <Link
                            to={primary.href}
                            className={cn(
                              buttonVariants({ variant: 'outline', size: 'sm' }),
                              'h-6 text-[10px]',
                            )}
                          >
                            {primary.label}
                          </Link>
                        ) : null}
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-6 text-[10px]"
                          onClick={() => dismissCoreR(item.id)}
                        >
                          Hecho
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
              </div>
            ) : null}
          </div>
        ) : null}

        {listsQuery.isLoading ? (
          <p className="text-xs text-muted-foreground">Cargando listas…</p>
        ) : lists.length === 0 ? (
          <div className="rounded-md border border-dashed border-border/80 px-3 py-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">No hay listas de watchlist</p>
            <p className="mt-1">
              Crea una en Watchlist (p. ej. IBEX) y vuelve aquí para ver TOP / paper / Proponer por
              valor.
            </p>
          </div>
        ) : !effectiveListId ? (
          <p className="text-xs text-muted-foreground">Elige una lista arriba.</p>
        ) : listDetailQuery.isError ? (
          <p className="text-xs text-destructive">No se pudo cargar la lista. Reintenta en un momento.</p>
        ) : listEmpty ? (
          <div className="rounded-md border border-dashed border-border/80 px-3 py-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Lista vacía</p>
            <p className="mt-1">Añade valores en Watchlist o elige otra lista.</p>
          </div>
        ) : loadingTops && withTop.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Cargando TOP de {monitorInstruments.length} valor(es)…
          </p>
        ) : withTop.length === 0 ? (
          <div className="rounded-md border border-dashed border-border/80 px-3 py-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Sin Finalistas en esta lista</p>
            <p className="mt-1">
              Ningún valor tiene TOP guardado ({monitorInstruments.length} en cola). En Probar:
              Universo → Play (ciclo ON) → Lab → Coach² → Finalistas. O modo Lista + Play = Lista
              AUTO.
            </p>
          </div>
        ) : (
          <>
            {withoutTop > 0 ? (
              <p className="text-[11px] text-muted-foreground">
                {withTop.length} con TOP · {withoutTop} sin TOP (ocultos).
              </p>
            ) : null}
            <ul className={cn('space-y-2 overflow-y-auto', embedded ? 'max-h-56' : 'max-h-72')}>
              {withTop.map((row) => {
                const reeval = readCoreRVerdictForInstrument(
                  effectiveListId,
                  row.instrumentId,
                );
                const showReeval = coreRNeedsAction(reeval?.verdict);
                const pnl = row.paperAccount
                  ? pnlByAccountId.get(row.paperAccount.id)
                  : undefined;
                const pnlHit = pnl ? coreRPaperPnlDegradation(pnl) : null;
                return (
                <li
                  key={row.instrumentId}
                  className="rounded-md border border-border/70 bg-background/60 px-2.5 py-2"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-foreground">
                        {row.symbol}
                        {row.name ? (
                          <span className="ml-1.5 text-[11px] font-normal text-muted-foreground">
                            {row.name}
                          </span>
                        ) : null}
                        {showReeval && reeval ? (
                          <span
                            className="ml-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-1 py-0.5 text-[10px] font-medium text-amber-200"
                            title={reeval.reason}
                          >
                            CORE-R · {coreRVerdictLabel(reeval.verdict)}
                          </span>
                        ) : null}
                        {pnlHit ? (
                          <span
                            className="ml-1.5 rounded border border-rose-500/40 bg-rose-500/10 px-1 py-0.5 text-[10px] font-medium text-rose-200"
                            title={pnlHit.reason}
                          >
                            PnL · {coreRVerdictLabel(pnlHit.level)}
                          </span>
                        ) : null}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {row.topStatus ?? '—'} · {row.evidenceLevel ?? '—'} · TF {row.timeframe}
                        {row.slot1Label
                          ? ` · #1 ${row.slot1Label}${row.slot1Stars ? ` ★${row.slot1Stars}` : ''}`
                          : ''}
                        {' · '}
                        Adopción:{' '}
                        {STRATEGY_ADOPTION_LABELS[
                          getAdoptionState(row.instrumentId, effectiveAccountId)
                        ]}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        Demo/paper:{' '}
                        {row.paperAccount
                          ? `${row.paperAccount.name} · ${formatPaperLabEvidence(row.paperAccount.labEvidence ?? null)}`
                          : 'sin cuenta · Checklist si hay run'}
                        {pnl ? (
                          <>
                            {' · '}
                            <span
                              className={cn(
                                pnl.returnPct < 0
                                  ? 'text-rose-300/90'
                                  : pnl.returnPct > 0
                                    ? 'text-emerald-300/90'
                                    : undefined,
                              )}
                              title={`Equity ${pnl.totalEquity.toFixed(0)} · depósito ${pnl.initialDeposit.toFixed(0)} · uPnL ${pnl.totalUnrealizedPnl.toFixed(0)}`}
                            >
                              retorno {formatCoreRReturnPct(pnl.returnPct)}
                            </span>
                          </>
                        ) : null}
                        {' · '}
                        Proponer:{' '}
                        {row.lastPropose
                          ? `${row.lastPropose.payload.action} (${new Date(row.lastPropose.enqueuedAt).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' })})`
                          : 'aún no (Camino C desde Finalistas)'}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      <Link
                        to={instrumentTopBacktestsHref(row.instrumentId, row.timeframe)}
                        className={cn(
                          buttonVariants({ variant: 'outline', size: 'sm' }),
                          'h-7 text-[11px]',
                        )}
                      >
                        Finalistas
                      </Link>
                      {row.slot1RunId ? (
                        <Link
                          to={strategyMonitorChecklistHref(
                            row.instrumentId,
                            row.slot1RunId,
                            row.timeframe,
                          )}
                          className={cn(
                            buttonVariants({ variant: 'outline', size: 'sm' }),
                            'h-7 text-[11px]',
                          )}
                          title="Abre Detalle con checklist paper (Camino A)"
                        >
                          Checklist
                        </Link>
                      ) : null}
                      {row.lastPropose ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-7 text-[11px]"
                          onClick={() => {
                            setActive(row.lastPropose!.id);
                            openHelpAiPlatform({ panel: 'supervised-f3' });
                          }}
                        >
                          F3
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </li>
                );
              })}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
