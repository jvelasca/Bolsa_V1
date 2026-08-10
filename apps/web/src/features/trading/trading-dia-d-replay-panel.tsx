/**
 * Panel Trading MODO DÍA D — Auto D→hoy + película + Semi/Manual gate + informe.
 *
 * - Película + informe lateral colapsable/redimensionable; abajo equity + operaciones.
 * - Evidence: band heurística + Narrar IA + **Guardar** (archivo local ± Fase 2).
 * - Archivo v0.10: lista / preview / export·import JSON / quitar (mismo símbolo).
 * - Gate Semi/Manual: accept-only rewrite (`dia-d-gate-equity.ts`).
 *
 * Sandbox ≠ DEMO live. Salir DÍA D no escribe el ledger DEMO.
 *
 * @see BACKTESTING_DIA_D_GUIDE
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md
 * @see docs/engineering/operativa-test-plan-2026-07-31.md
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import type {
  BacktestEquityPointDto,
  BacktestRunDetailDto,
  BacktestTradeDto,
} from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { BacktestMovieHud } from '@/features/backtests/backtest-movie-hud';
import { BacktestReplayChart } from '@/features/backtests/backtest-replay-chart';
import { BacktestEquityChart } from '@/features/backtests/backtest-equity-chart';
import { equityCurveFromDetail } from '@/features/backtests/backtest-export';
import { computeMovieTradeStats } from '@/features/backtests/backtest-movie-stats';
import { useBacktestHudPrefs } from '@/features/backtests/use-backtest-hud-prefs';
import { loadBacktestRunContext } from '@/features/backtests/backtest-run-context';
import { formatDateDdMmYyyy } from '@/features/backtests/backtest-date-format';
import { pxToPct } from '@/features/backtests/backtest-split-layout';
import {
  computeGatedSessionMetrics,
  detailWithGatedFills,
} from '@/features/trading/dia-d-gate-equity';
import {
  buildDiaDSessionEvidence,
  DIA_D_EVIDENCE_BAND_LABELS,
  type DiaDSessionEvidenceV1,
} from '@/features/trading/dia-d-session-evidence';
import { DiaDReconciliationPanel } from '@/features/trading/dia-d-reconciliation-panel';
import { DiaDTradesPanel } from '@/features/trading/dia-d-trades-panel';
import { DiaDPendingTradeBanner } from '@/features/trading/dia-d-pending-trade-banner';
import { DiaDSessionReportPanel } from '@/features/trading/dia-d-session-report-panel';
import {
  buildCounterfactualOos,
  buildDiaDReconciliation,
  resolveDiaDIdentity,
} from '@/features/backtests/dia-d-reconciliation';
import { getDiaDExperimentTop1 } from '@/features/backtests/dia-d-experiment-top';
import {
  dayKey as verifyDayKey,
  portfolioJustBeforeDiaD,
  sliceDetailFromDiaD,
  tradesOnOrAfterDiaD,
  verifyApiDateFrom,
} from '@/features/trading/dia-d-verify-continuity';
import {
  downloadDiaDEvidenceJson,
  formatDiaDArchiveRowLabel,
  parseDiaDEvidenceImportText,
} from '@/features/trading/dia-d-evidence-archive-io';
import {
  clampEquityWidthPct,
  clampMovieHeightPct,
  clampReportWidthPct,
  loadDiaDVerifyLayout,
  saveDiaDVerifyLayout,
  type DiaDVerifyLayoutPrefs,
} from '@/features/trading/dia-d-verify-layout';
import {
  DIA_D_MODE_LABELS,
  useDiaDTradingSessionStore,
} from '@/stores/dia-d-trading-session-store';
import { useDiaDEvidenceArchiveStore } from '@/stores/dia-d-evidence-archive-store';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PanelResizeHandle } from '@/components/layout/panel-resize-handle';
import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { useMediaQuery } from '@/lib/use-media-query';
import { cn } from '@/lib/utils';

function equityAtOrBefore(
  curve: BacktestEquityPointDto[],
  timestamp: string | null,
): BacktestEquityPointDto | null {
  if (!timestamp || curve.length === 0) return null;
  for (let i = curve.length - 1; i >= 0; i -= 1) {
    const point = curve[i]!;
    if (point.timestamp <= timestamp) return point;
  }
  return curve[0] ?? null;
}

function dayKey(timestamp: string): string {
  return verifyDayKey(timestamp);
}

/** Si se rechaza un buy, el sell del mismo round-trip deja de ser propuesta. */
function companionSellAfterBuy(
  trades: BacktestTradeDto[],
  buyId: string,
): BacktestTradeDto | null {
  const idx = trades.findIndex((t) => t.id === buyId);
  if (idx < 0 || trades[idx]?.type !== 'buy') return null;
  for (let i = idx + 1; i < trades.length; i += 1) {
    const t = trades[i]!;
    if (t.type === 'sell') return t;
    if (t.type === 'buy') return null;
  }
  return null;
}

export function TradingDiaDReplayPanel() {
  const session = useDiaDTradingSessionStore((s) => s.session);
  const setAutoRunId = useDiaDTradingSessionStore((s) => s.setAutoRunId);
  const setFullBleedMovie = useDiaDTradingSessionStore((s) => s.setFullBleedMovie);
  const addGateDecision = useDiaDTradingSessionStore((s) => s.addGateDecision);
  const clearGateDecisions = useDiaDTradingSessionStore((s) => s.clearGateDecisions);
  const hudPrefs = useBacktestHudPrefs();

  const [replayCursor, setReplayCursor] = useState<string | null>(null);
  const [replayBarIndex, setReplayBarIndex] = useState(0);
  const [replayBarTotal, setReplayBarTotal] = useState(0);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [replayAtEnd, setReplayAtEnd] = useState(false);
  const [pendingTrade, setPendingTrade] = useState<BacktestTradeDto | null>(null);
  const [resumeNonce, setResumeNonce] = useState(0);
  const [layout, setLayout] = useState<DiaDVerifyLayoutPrefs>(() => loadDiaDVerifyLayout());
  const [focusTimestamp, setFocusTimestamp] = useState<string | null>(null);
  const [iaNarrative, setIaNarrative] = useState<DiaDSessionEvidenceV1['paragraphs'] | null>(
    null,
  );
  const [iaEngine, setIaEngine] = useState<string | null>(null);
  const [previewArchiveId, setPreviewArchiveId] = useState<string | null>(null);
  const [archiveImportMsg, setArchiveImportMsg] = useState<string | null>(null);
  const archiveFileRef = useRef<HTMLInputElement>(null);
  const movieRowRef = useRef<HTMLDivElement>(null);
  const bottomRowRef = useRef<HTMLDivElement>(null);
  const pendingReportW = useRef(layout.reportWidthPct);
  const pendingMovieH = useRef(layout.movieHeightPct);
  const pendingEquityW = useRef(layout.equityWidthPct);
  const isWide = useMediaQuery('(min-width: 900px)');
  const isWideBottom = useMediaQuery('(min-width: 720px)');

  const persistLayout = useCallback((patch: Partial<DiaDVerifyLayoutPrefs>) => {
    setLayout((prev) => {
      const next = { ...prev, ...patch };
      saveDiaDVerifyLayout(next);
      return next;
    });
  }, []);

  const reportOpen = layout.reportOpen;
  const setReportOpen = useCallback(
    (updater: boolean | ((v: boolean) => boolean)) => {
      setLayout((prev) => {
        const nextOpen = typeof updater === 'function' ? updater(prev.reportOpen) : updater;
        const next = { ...prev, reportOpen: nextOpen };
        saveDiaDVerifyLayout(next);
        return next;
      });
    },
    [],
  );

  const runCtx = loadBacktestRunContext();

  const detailQuery = useQuery({
    queryKey: ['dia-d-auto-run', session?.autoRunId],
    queryFn: () => api.getBacktest(session!.autoRunId!),
    enabled: Boolean(session?.autoRunId),
    staleTime: 60_000,
  });

  const rawAutoDetail: BacktestRunDetailDto | null = detailQuery.data?.data ?? null;

  const runMutation = useMutation({
    mutationFn: async () => {
      if (!session) throw new Error('Sin sesión DÍA D');
      // Lookback antes de D: indicadores + posición continua (evita 0 ops en frío).
      return api.runBacktest({
        instrumentId: session.instrumentId,
        strategyDefinitionId: session.strategyDefinitionId,
        dateFrom: verifyApiDateFrom(session.diaD),
        dateTo: session.endDate,
        limit: 10_000,
        timeframe: String(runCtx.timeframe || '1d'),
        initialCash: Number(runCtx.initialCash) || 10_000,
        commissionBps: Number(runCtx.commissionBps) || 0,
        slippageBps: Number(runCtx.slippageBps) || 0,
      });
    },
    onSuccess: (res) => {
      clearGateDecisions();
      setPendingTrade(null);
      setIaNarrative(null);
      setIaEngine(null);
      setAutoRunId(res.data.id);
    },
  });

  useEffect(() => {
    if (!session) return;
    if (session.autoRunId) return;
    if (runMutation.isPending) return;
    runMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    session?.instrumentId,
    session?.strategyDefinitionId,
    session?.diaD,
    session?.endDate,
    session?.autoRunId,
  ]);

  /** Sesiones cacheadas pre-fix (dateFrom=D en frío) → re-lanzar con lookback. */
  useEffect(() => {
    if (!session?.autoRunId || !rawAutoDetail) return;
    if (runMutation.isPending) return;
    const runFrom = dayKey(rawAutoDetail.firstDate);
    const d = dayKey(session.diaD);
    if (runFrom >= d) {
      setAutoRunId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.autoRunId, session?.diaD, rawAutoDetail?.id, rawAutoDetail?.firstDate]);

  const ohlcvQuery = useQuery({
    queryKey: [
      'dia-d-replay-ohlcv',
      session?.instrumentId,
      rawAutoDetail?.barCount,
      rawAutoDetail?.timeframe ?? runCtx.timeframe,
    ],
    queryFn: () =>
      api.getOhlcv(
        session!.instrumentId,
        Math.min(10_000, Math.max(500, (rawAutoDetail?.barCount ?? 400) + 200)),
        String(rawAutoDetail?.timeframe ?? runCtx.timeframe ?? '1d'),
      ),
    enabled: Boolean(session?.instrumentId && rawAutoDetail),
    staleTime: 60_000,
  });

  const bars = useMemo(() => ohlcvQuery.data?.data ?? [], [ohlcvQuery.data?.data]);

  /** Barras lookback→fin del run (para portfolio@D). */
  const fullRunBars = useMemo(() => {
    if (!rawAutoDetail || bars.length === 0) return bars;
    const from = dayKey(rawAutoDetail.firstDate);
    const to = dayKey(rawAutoDetail.lastDate);
    const inWindow = bars.filter((bar) => {
      const day = dayKey(bar.timestamp);
      return day >= from && day <= to;
    });
    return inWindow.length > 0 ? inWindow : bars;
  }, [rawAutoDetail, bars]);

  /** Ventana de película / métricas: D→hoy. */
  const runBars = useMemo(() => {
    if (!session) return fullRunBars;
    const d = dayKey(session.diaD);
    return fullRunBars.filter((bar) => dayKey(bar.timestamp) >= d);
  }, [fullRunBars, session]);

  /** Auto recortado a D→hoy con carry de posición. */
  const autoDetail: BacktestRunDetailDto | null = useMemo(() => {
    if (!rawAutoDetail || !session) return null;
    return sliceDetailFromDiaD(rawAutoDetail, session.diaD, fullRunBars);
  }, [rawAutoDetail, session, fullRunBars]);

  const carryAtD = useMemo(() => {
    if (!rawAutoDetail || !session) return { cash: 0, shares: 0, equity: 0 };
    const d = dayKey(session.diaD);
    const mark = fullRunBars.find((b) => dayKey(b.timestamp) >= d);
    return portfolioJustBeforeDiaD(
      rawAutoDetail.initialCash,
      rawAutoDetail.trades,
      session.diaD,
      mark?.close ?? null,
    );
  }, [rawAutoDetail, session, fullRunBars]);

  const gatePolicy = session?.mode === 'auto' ? 'auto' : 'gated';

  const gatedMetrics = useMemo(() => {
    if (!rawAutoDetail || !session || !autoDetail) return null;
    const oosTrades = tradesOnOrAfterDiaD(rawAutoDetail.trades, session.diaD);
    return computeGatedSessionMetrics({
      initialCash: carryAtD.cash,
      initialShares: carryAtD.shares,
      bars: runBars,
      autoTrades: oosTrades,
      decisions: session.gateDecisions,
      policy: gatePolicy,
    });
  }, [rawAutoDetail, session, autoDetail, carryAtD, runBars, gatePolicy]);

  const detail = useMemo(() => {
    if (!autoDetail) return null;
    if (!gatedMetrics || session?.mode === 'auto') {
      return {
        ...autoDetail,
        equityCurve:
          autoDetail.equityCurve && autoDetail.equityCurve.length > 0
            ? autoDetail.equityCurve
            : equityCurveFromDetail(autoDetail),
      };
    }
    return detailWithGatedFills(autoDetail, gatedMetrics);
  }, [autoDetail, gatedMetrics, session?.mode]);

  const equityCurve = useMemo(() => (detail ? equityCurveFromDetail(detail) : []), [detail]);

  const liveEquityPoint = useMemo(
    () => equityAtOrBefore(equityCurve, replayCursor),
    [equityCurve, replayCursor],
  );
  const liveEquity = liveEquityPoint?.equity;
  const liveReturnPct =
    liveEquity != null && detail
      ? ((liveEquity - detail.initialCash) / detail.initialCash) * 100
      : null;

  const movieStats = useMemo(
    () => (detail ? computeMovieTradeStats(detail.trades, replayCursor) : null),
    [detail, replayCursor],
  );

  const markPrice = useMemo(() => {
    if (!replayCursor || bars.length === 0) return null;
    const bar =
      bars.find((b) => b.timestamp === replayCursor) ??
      bars.find((b) => b.timestamp <= replayCursor);
    return bar?.close ?? null;
  }, [bars, replayCursor]);

  const pauseTrades = useMemo(() => {
    if (!autoDetail || !session) return [];
    const decided = new Set(session.gateDecisions.map((d) => d.tradeId));
    return autoDetail.trades.filter((t) => !decided.has(t.id));
  }, [autoDetail, session]);

  const sessionEvidence = useMemo(() => {
    if (!session || !autoDetail || !detail) return null;
    const ok = session.gateDecisions.filter((d) => d.action === 'accept').length;
    const ko = session.gateDecisions.filter((d) => d.action === 'reject').length;
    return buildDiaDSessionEvidence({
      mode: session.mode,
      symbol: session.symbol,
      strategyLabel: session.strategyLabel,
      diaD: session.diaD,
      endDate: session.endDate,
      initialCash: autoDetail.initialCash,
      auto: {
        totalReturnPct: autoDetail.totalReturnPct,
        maxDrawdownPct: autoDetail.maxDrawdownPct,
        tradeCount: autoDetail.tradeCount,
        finalEquity: autoDetail.finalEquity,
      },
      gated: {
        totalReturnPct: detail.totalReturnPct,
        maxDrawdownPct: detail.maxDrawdownPct,
        tradeCount: detail.tradeCount,
        finalEquity: detail.finalEquity,
      },
      gate: { accepted: ok, rejected: ko },
    });
  }, [session, autoDetail, detail]);

  const productionTopQuery = useQuery({
    queryKey: [
      'instrument-strategy-top',
      session?.instrumentId,
      String(runCtx.timeframe || '1d'),
    ],
    queryFn: () =>
      api.getInstrumentStrategyTop(
        session!.instrumentId,
        String(runCtx.timeframe || '1d'),
      ),
    enabled: Boolean(session?.instrumentId),
    staleTime: 30_000,
    retry: false,
  });

  const prod1 = useMemo(() => {
    const slots = productionTopQuery.data?.data?.slots ?? [];
    return [...slots].sort((a, b) => a.rank - b.rank)[0] ?? null;
  }, [productionTopQuery.data?.data?.slots]);

  const sameAsExperiment =
    Boolean(session?.strategyDefinitionId) &&
    Boolean(prod1?.strategyDefinitionId) &&
    session!.strategyDefinitionId === prod1!.strategyDefinitionId;

  /** Contrafactual F-hoy#1 en la misma ventana (lookback → end), slice a D. */
  const counterfactualQuery = useQuery({
    queryKey: [
      'dia-d-counterfactual',
      session?.instrumentId,
      prod1?.strategyDefinitionId,
      session?.diaD,
      session?.endDate,
    ],
    queryFn: async () => {
      const res = await api.runBacktest({
        instrumentId: session!.instrumentId,
        strategyDefinitionId: prod1!.strategyDefinitionId!,
        dateFrom: verifyApiDateFrom(session!.diaD),
        dateTo: session!.endDate,
        limit: 10_000,
        timeframe: String(runCtx.timeframe || '1d'),
        initialCash: Number(runCtx.initialCash) || 10_000,
        commissionBps: Number(runCtx.commissionBps) || 0,
        slippageBps: Number(runCtx.slippageBps) || 0,
      });
      return res.data;
    },
    enabled: Boolean(
      session &&
        sessionEvidence &&
        prod1?.strategyDefinitionId &&
        !sameAsExperiment,
    ),
    staleTime: 120_000,
    retry: 1,
  });

  const counterfactualSliced = useMemo(() => {
    if (!session || !counterfactualQuery.data) return null;
    return sliceDetailFromDiaD(counterfactualQuery.data, session.diaD, bars);
  }, [counterfactualQuery.data, session, bars]);

  const reconciliation = useMemo(() => {
    if (!session || !sessionEvidence) return null;
    const tf = String(runCtx.timeframe || '1d');
    const expSlot = getDiaDExperimentTop1(session.instrumentId, tf, session.diaD);
    const identity = resolveDiaDIdentity(
      {
        strategyDefinitionId: session.strategyDefinitionId,
        label: session.strategyLabel,
        strategyType: expSlot?.strategyType ?? null,
      },
      prod1
        ? {
            strategyDefinitionId: prod1.strategyDefinitionId ?? null,
            label: prod1.label,
            strategyType: prod1.strategyType ?? null,
          }
        : null,
    );
    const expRet = detail?.totalReturnPct ?? autoDetail?.totalReturnPct ?? null;
    let counterfactual = null as ReturnType<typeof buildCounterfactualOos> | null;
    if (!prod1) {
      counterfactual = buildCounterfactualOos({
        experimentReturnPct: expRet,
        productionReturnPct: null,
        identity: 'unknown',
        status: 'unavailable',
        note: 'Sin F-hoy#1',
      });
    } else if (sameAsExperiment) {
      counterfactual = buildCounterfactualOos({
        experimentReturnPct: expRet,
        productionReturnPct: expRet,
        productionTradeCount: detail?.tradeCount ?? autoDetail?.tradeCount ?? null,
        productionMaxDrawdownPct: detail?.maxDrawdownPct ?? autoDetail?.maxDrawdownPct ?? null,
        identity: 'same_id',
      });
    } else if (counterfactualQuery.isError) {
      counterfactual = buildCounterfactualOos({
        experimentReturnPct: expRet,
        productionReturnPct: null,
        identity,
        status: 'error',
        note: 'No se pudo simular F-hoy#1',
      });
    } else if (counterfactualSliced) {
      counterfactual = buildCounterfactualOos({
        experimentReturnPct: expRet,
        productionReturnPct: counterfactualSliced.totalReturnPct,
        productionTradeCount: counterfactualSliced.tradeCount,
        productionMaxDrawdownPct: counterfactualSliced.maxDrawdownPct,
        identity,
        status: 'ready',
      });
    } else {
      counterfactual = buildCounterfactualOos({
        experimentReturnPct: expRet,
        productionReturnPct: null,
        identity,
        status: 'pending',
        note: 'Simulando F-hoy#1…',
      });
    }

    return buildDiaDReconciliation({
      experimentSlot: {
        strategyDefinitionId: session.strategyDefinitionId,
        label: session.strategyLabel,
        strategyType: expSlot?.strategyType ?? null,
      },
      productionSlot: prod1
        ? {
            strategyDefinitionId: prod1.strategyDefinitionId ?? null,
            label: prod1.label,
            strategyType: prod1.strategyType ?? null,
          }
        : null,
      evidenceBand: sessionEvidence.band,
      oosReturnPct: expRet,
      counterfactual,
    });
  }, [
    session,
    sessionEvidence,
    prod1,
    sameAsExperiment,
    detail?.totalReturnPct,
    detail?.tradeCount,
    detail?.maxDrawdownPct,
    autoDetail?.totalReturnPct,
    autoDetail?.tradeCount,
    autoDetail?.maxDrawdownPct,
    counterfactualQuery.isError,
    counterfactualSliced,
    runCtx.timeframe,
  ]);

  useEffect(() => {
    setIaNarrative(null);
    setIaEngine(null);
  }, [session?.mode, session?.gateDecisions, detail?.tradeCount, detail?.totalReturnPct]);

  const evidenceMutation = useMutation({
    mutationFn: async () => {
      if (!session || !autoDetail || !detail) throw new Error('Sin datos de sesión');
      const ok = session.gateDecisions.filter((d) => d.action === 'accept').length;
      const ko = session.gateDecisions.filter((d) => d.action === 'reject').length;
      return api.explainDiaDSessionEvidence({
        mode: session.mode,
        symbol: session.symbol,
        strategyLabel: session.strategyLabel,
        diaD: session.diaD,
        endDate: session.endDate,
        initialCash: autoDetail.initialCash,
        auto: {
          totalReturnPct: autoDetail.totalReturnPct,
          maxDrawdownPct: autoDetail.maxDrawdownPct,
          tradeCount: autoDetail.tradeCount,
          finalEquity: autoDetail.finalEquity,
        },
        gated: {
          totalReturnPct: detail.totalReturnPct,
          maxDrawdownPct: detail.maxDrawdownPct,
          tradeCount: detail.tradeCount,
          finalEquity: detail.finalEquity,
        },
        gate: { accepted: ok, rejected: ko },
      });
    },
    onSuccess: (res) => {
      const paras = res.data.payload.paragraphs;
      if (Array.isArray(paras) && paras.length >= 3) {
        setIaNarrative([paras[0]!, paras[1]!, paras[2]!]);
      }
      setIaEngine(res.data.engine);
    },
  });

  const saveEvidenceMutation = useMutation({
    mutationFn: async () => {
      if (!session || !sessionEvidence) throw new Error('Sin Evidence de sesión');
      const engine = iaEngine ?? 'heuristic';
      const evidencePayload: DiaDSessionEvidenceV1 = iaNarrative
        ? { ...sessionEvidence, paragraphs: iaNarrative }
        : sessionEvidence;
      let researchEvidenceId: string | null = null;
      let apiOk = false;
      try {
        const res = await api.persistDiaDSessionEvidence({
          instrumentId: session.instrumentId,
          symbol: session.symbol,
          mode: session.mode,
          strategyLabel: session.strategyLabel,
          diaD: session.diaD,
          endDate: session.endDate,
          engine,
          evidence: evidencePayload as unknown as Record<string, unknown>,
        });
        researchEvidenceId = res.data.id;
        apiOk = true;
      } catch {
        // Archivo local siempre; Fase 2 opcional si API no tiene la ruta.
      }
      const archived = useDiaDEvidenceArchiveStore.getState().save({
        instrumentId: session.instrumentId,
        symbol: session.symbol,
        strategyLabel: session.strategyLabel,
        mode: session.mode,
        diaD: session.diaD,
        endDate: session.endDate,
        researchEvidenceId,
        engine,
        evidence: evidencePayload,
        narrativeParagraphs: iaNarrative,
      });
      return { archived, apiOk };
    },
  });

  const archiveItems = useDiaDEvidenceArchiveStore((s) => s.items);
  const removeArchive = useDiaDEvidenceArchiveStore((s) => s.remove);
  const saveArchive = useDiaDEvidenceArchiveStore((s) => s.save);
  const archivedForSymbol = useMemo(
    () =>
      session
        ? archiveItems.filter((i) => i.instrumentId === session.instrumentId)
        : [],
    [archiveItems, session],
  );
  const previewArchive = useMemo(
    () => archivedForSymbol.find((i) => i.id === previewArchiveId) ?? null,
    [archivedForSymbol, previewArchiveId],
  );

  const importArchiveFile = useCallback(
    async (file: File | null) => {
      if (!file || !session) return;
      setArchiveImportMsg(null);
      try {
        const text = await file.text();
        const parsed = parseDiaDEvidenceImportText(text);
        if (!parsed.ok) {
          setArchiveImportMsg(parsed.error);
          return;
        }
        if (parsed.item.instrumentId !== session.instrumentId) {
          setArchiveImportMsg(
            `JSON de ${parsed.item.symbol} ≠ sesión ${session.symbol}`,
          );
          return;
        }
        const saved = saveArchive({
          ...parsed.item,
          // Nueva entrada local; dedupe por ventana/mode si coincide.
          id: undefined,
          savedAt: new Date().toISOString(),
        });
        setPreviewArchiveId(saved.id);
        setArchiveImportMsg(`Importado · ${formatDiaDArchiveRowLabel(saved)}`);
      } catch (err) {
        setArchiveImportMsg(err instanceof Error ? err.message : 'Import falló');
      } finally {
        if (archiveFileRef.current) archiveFileRef.current.value = '';
      }
    },
    [saveArchive, session],
  );

  const handleReplayCursorChange = useCallback(
    (
      ts: string | null,
      meta: { playing: boolean; atEnd: boolean; barIndex: number; barTotal: number },
    ) => {
      setReplayCursor(ts);
      setReplayPlaying(meta.playing);
      setReplayAtEnd(meta.atEnd);
      setReplayBarIndex(meta.barIndex);
      setReplayBarTotal(meta.barTotal);
    },
    [],
  );

  const decideGate = useCallback(
    (action: 'accept' | 'reject') => {
      if (!pendingTrade || !autoDetail) return;
      addGateDecision({
        tradeId: pendingTrade.id,
        timestamp: pendingTrade.timestamp,
        side: pendingTrade.type,
        price: pendingTrade.price,
        action,
      });
      if (action === 'reject' && pendingTrade.type === 'buy') {
        const sell = companionSellAfterBuy(autoDetail.trades, pendingTrade.id);
        if (sell) {
          addGateDecision({
            tradeId: sell.id,
            timestamp: sell.timestamp,
            side: sell.type,
            price: sell.price,
            action: 'reject',
          });
        }
      }
      setPendingTrade(null);
      setResumeNonce((n) => n + 1);
    },
    [addGateDecision, pendingTrade, autoDetail],
  );

  if (!session) return null;

  const busy = runMutation.isPending || (Boolean(session.autoRunId) && detailQuery.isLoading);
  const err =
    runMutation.error instanceof ApiError
      ? runMutation.error.message
      : runMutation.error instanceof Error
        ? runMutation.error.message
        : detailQuery.error instanceof Error
          ? detailQuery.error.message
          : null;

  const accepted = session.gateDecisions.filter((d) => d.action === 'accept').length;
  const rejected = session.gateDecisions.filter((d) => d.action === 'reject').length;
  const pauseOnTrade = session.mode === 'semi' || session.mode === 'manual';
  const report = detail ?? autoDetail;
  const fullBleed = Boolean(session.fullBleedMovie);

  const sessionReportBody = report ? (
    <>
            <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 tabular-nums">
              <dt className="text-muted-foreground">Modo</dt>
              <dd>{DIA_D_MODE_LABELS[session.mode]}</dd>
              <dt className="text-muted-foreground">DÍA D</dt>
              <dd>
                {session.diaD} → {session.endDate}
              </dd>
              <dt className="text-muted-foreground">Retorno</dt>
              <dd>{formatPct(report.totalReturnPct)}</dd>
              <dt className="text-muted-foreground">Max DD</dt>
              <dd>{formatPct(report.maxDrawdownPct)}</dd>
              <dt className="text-muted-foreground">Ops gate</dt>
              <dd>
                {report.tradeCount}
                {autoDetail && session.mode !== 'auto'
                  ? ` / Auto ${autoDetail.tradeCount}`
                  : null}
              </dd>
              <dt className="text-muted-foreground">Capital</dt>
              <dd>
                {formatPrice(report.initialCash)} → {formatPrice(report.finalEquity)}
              </dd>
              <dt className="text-muted-foreground">Semi OK/KO</dt>
              <dd>
                {accepted}/{rejected}
              </dd>
            </dl>
            <p className="leading-snug text-muted-foreground">
              {session.mode === 'auto'
                ? 'Equity = trayectoria Auto (#1 congelada).'
                : 'Equity reescrita con fills Aceptar; Rechazar no ejecuta (buy rechazado anula su sell).'}
            </p>
            {sessionEvidence ? (
              <div className="space-y-1.5 border-t border-border/50 pt-1.5">
                <div className="flex flex-wrap items-center gap-1">
                  <span className="font-semibold text-foreground">Evidence</span>
                  <span
                    className={cn(
                      'rounded px-1 py-0.5 text-[9px] font-medium',
                      sessionEvidence.band === 'favorable' &&
                        'bg-emerald-500/15 text-emerald-800 dark:text-emerald-200',
                      sessionEvidence.band === 'adverse' && 'bg-destructive/15 text-destructive',
                      sessionEvidence.band === 'mixed' &&
                        'bg-amber-500/15 text-amber-900 dark:text-amber-100',
                      sessionEvidence.band === 'incomplete' && 'bg-muted text-muted-foreground',
                    )}
                  >
                    {DIA_D_EVIDENCE_BAND_LABELS[sessionEvidence.band]}
                  </span>
                  <span className="text-muted-foreground">{sessionEvidence.confidence}</span>
                </div>
                {reconciliation ? (
                  <DiaDReconciliationPanel
                    result={reconciliation}
                    instrumentId={session.instrumentId}
                    timeframe={String(runCtx.timeframe || '1d')}
                  />
                ) : null}
                <ul className="space-y-1 leading-snug text-foreground/90">
                  {(iaNarrative ?? sessionEvidence.paragraphs).map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
                {sessionEvidence.warnings.length > 0 ? (
                  <ul className="space-y-0.5 text-amber-800 dark:text-amber-200">
                    {sessionEvidence.warnings.map((w) => (
                      <li key={w}>⚠ {w}</li>
                    ))}
                  </ul>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-6 w-full px-2 text-[10px]"
                  disabled={evidenceMutation.isPending}
                  onClick={() => evidenceMutation.mutate()}
                >
                  {evidenceMutation.isPending ? 'Narrando…' : 'Narrar con IA'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-6 w-full px-2 text-[10px]"
                  disabled={saveEvidenceMutation.isPending}
                  onClick={() => saveEvidenceMutation.mutate()}
                  title="Archivo local + Fase 2 research_evidence (si API up)"
                >
                  {saveEvidenceMutation.isPending ? 'Guardando…' : 'Guardar Evidence'}
                </Button>
                {saveEvidenceMutation.isSuccess ? (
                  <p className="text-[9px] text-muted-foreground">
                    Guardado
                    {saveEvidenceMutation.data.apiOk
                      ? ` · Fase 2 ${saveEvidenceMutation.data.archived.researchEvidenceId?.slice(0, 8)}…`
                      : ' · solo archivo local (reinicia API para Fase 2)'}
                  </p>
                ) : null}
                {iaEngine ? (
                  <p className="text-[9px] text-muted-foreground">Motor: {iaEngine}</p>
                ) : null}
                {evidenceMutation.isError ? (
                  <p className="text-destructive" role="alert">
                    {evidenceMutation.error instanceof Error
                      ? evidenceMutation.error.message
                      : 'No se pudo narrar'}
                  </p>
                ) : null}
                <div className="space-y-1 border-t border-border/40 pt-1.5">
                  <div className="flex items-center gap-1">
                    <p className="min-w-0 flex-1 text-[9px] font-medium text-foreground">
                      Archivo ({archivedForSymbol.length})
                    </p>
                    <input
                      ref={archiveFileRef}
                      type="file"
                      accept="application/json,.json"
                      className="hidden"
                      onChange={(e) =>
                        void importArchiveFile(e.target.files?.[0] ?? null)
                      }
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-5 shrink-0 px-1.5 text-[9px]"
                      title="Importar JSON exportado (mismo valor)"
                      onClick={() => archiveFileRef.current?.click()}
                    >
                      Importar
                    </Button>
                  </div>
                  {archiveImportMsg ? (
                    <p className="text-[9px] text-muted-foreground" role="status">
                      {archiveImportMsg}
                    </p>
                  ) : null}
                  {archivedForSymbol.length > 0 ? (
                    <ul className="max-h-24 space-y-0.5 overflow-auto">
                      {archivedForSymbol.map((item) => {
                        const active = item.id === previewArchiveId;
                        return (
                          <li key={item.id} className="flex items-center gap-0.5">
                            <button
                              type="button"
                              className={cn(
                                'min-w-0 flex-1 truncate rounded px-1 py-0.5 text-left text-[9px] hover:bg-accent',
                                active && 'bg-accent font-medium text-foreground',
                              )}
                              title="Ver párrafos guardados"
                              onClick={() =>
                                setPreviewArchiveId((cur) =>
                                  cur === item.id ? null : item.id,
                                )
                              }
                            >
                              {formatDiaDArchiveRowLabel(item)}
                              {item.researchEvidenceId ? ' · F2' : ''}
                            </button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-5 shrink-0 px-1 text-[9px]"
                              title="Exportar JSON"
                              onClick={() => downloadDiaDEvidenceJson(item)}
                            >
                              JSON
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-5 shrink-0 px-1 text-[9px] text-muted-foreground"
                              title="Quitar del archivo local"
                              onClick={() => {
                                if (previewArchiveId === item.id) setPreviewArchiveId(null);
                                removeArchive(item.id);
                              }}
                            >
                              ×
                            </Button>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="text-[9px] text-muted-foreground">
                      Vacío · Guardar o Importar JSON de este valor.
                    </p>
                  )}
                  {previewArchive ? (
                    <div className="space-y-0.5 rounded border border-border/50 bg-muted/20 px-1.5 py-1 text-[9px] leading-snug text-muted-foreground">
                      <p className="font-medium text-foreground">
                        Preview ·{' '}
                        {DIA_D_EVIDENCE_BAND_LABELS[previewArchive.evidence.band]}
                        {previewArchive.researchEvidenceId
                          ? ` · Fase 2 ${previewArchive.researchEvidenceId.slice(0, 8)}…`
                          : ' · solo local'}
                      </p>
                      {(
                        previewArchive.narrativeParagraphs ??
                        previewArchive.evidence.paragraphs
                      ).map((p, idx) => (
                        <p key={`${previewArchive.id}-p${idx}`}>{p}</p>
                      ))}
                    </div>
                  ) : null}
                </div>
                <p className="text-[9px] leading-snug text-muted-foreground">
                  {sessionEvidence.disclaimer}
                </p>
              </div>
            ) : null}
            {session.gateDecisions.length > 0 ? (
              <ul className="space-y-1 border-t border-border/50 pt-1.5">
                {session.gateDecisions
                  .slice()
                  .reverse()
                  .map((d) => (
                    <li
                      key={d.tradeId}
                      className={cn(
                        'rounded px-1 py-0.5',
                        d.action === 'reject' ? 'bg-destructive/10' : 'bg-emerald-500/10',
                      )}
                    >
                      {d.action === 'accept' ? 'OK' : 'KO'} {d.side}{' '}
                      {formatDateDdMmYyyy(d.timestamp)} · {formatPrice(d.price)}
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">
                {session.mode === 'auto' ? 'Modo Auto: sin gate.' : 'Sin decisiones aún.'}
              </p>
            )}
    </>
  ) : null;

  const reportPanelProps = {
    body: sessionReportBody,
    reportOpen,
    onOpenChange: setReportOpen,
    reportWidthPct: layout.reportWidthPct,
    onResizeDrag: (dx: number) => {
      const row = movieRowRef.current;
      if (!row) return;
      const next = clampReportWidthPct(
        pendingReportW.current - pxToPct(dx, row.clientWidth),
      );
      pendingReportW.current = next;
      setLayout((prev) => ({ ...prev, reportWidthPct: next }));
    },
    onResizeDragEnd: () => persistLayout({ reportWidthPct: pendingReportW.current }),
  };

  return (
    <div
      className="flex min-h-0 flex-1 flex-col border-b border-border/70 bg-card"
      data-testid={fullBleed ? 'dia-d-replay-full-bleed' : 'dia-d-replay-embedded'}
    >
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-border/50 px-3 py-1.5 text-[11px]">
        <span className="font-semibold text-foreground">Película D→hoy</span>
        <span className="text-muted-foreground">
          {session.symbol} · #{session.rank} {session.strategyLabel} · {session.diaD} →{' '}
          {session.endDate} · {DIA_D_MODE_LABELS[session.mode]}
        </span>
        {report ? (
          <span className="tabular-nums text-muted-foreground">
            Ret. {formatPct(report.totalReturnPct)} · DD {formatPct(report.maxDrawdownPct)} ·{' '}
            {report.tradeCount} ops · fin {formatPrice(report.finalEquity)}
            {session.mode !== 'auto' && autoDetail ? (
              <span className="text-muted-foreground/80">
                {' '}
                (Auto {formatPct(autoDetail.totalReturnPct)})
              </span>
            ) : null}
          </span>
        ) : null}
        {session.mode === 'manual' ? (
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            Manual: ▶ / pasos · pausa en señales → Aceptar/Rechazar (reescribe equity)
          </span>
        ) : null}
        {session.mode === 'semi' ? (
          <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-900 dark:text-amber-100">
            Semi: pausa en señales · Aceptar/Rechazar reescribe fills y equity
          </span>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-6 gap-1 px-2 text-[10px]"
          onClick={() => setReportOpen((v) => !v)}
          title={reportOpen ? 'Colapsar informe' : 'Mostrar informe'}
          aria-expanded={reportOpen}
          aria-controls="dia-d-session-report-panel"
        >
          {reportOpen ? (
            <PanelRightClose className="size-3.5" aria-hidden />
          ) : (
            <PanelRightOpen className="size-3.5" aria-hidden />
          )}
          {reportOpen ? 'Colapsar informe' : 'Informe'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-6 px-2 text-[10px]"
          onClick={() => setFullBleedMovie(!fullBleed)}
          title={fullBleed ? 'Salir pantalla completa' : 'Pantalla completa'}
        >
          {fullBleed ? '⛶ Salir' : '⛶ Completa'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="ml-auto h-6 px-2 text-[10px]"
          disabled={busy}
          onClick={() => {
            setAutoRunId(null);
            runMutation.reset();
          }}
        >
          Re-ejecutar
        </Button>
      </div>

      <DiaDPendingTradeBanner
        pendingTrade={pendingTrade}
        mode={session.mode}
        onAccept={() => decideGate('accept')}
        onReject={() => decideGate('reject')}
      />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div
          ref={movieRowRef}
          className={cn('flex min-h-[180px] overflow-hidden', isWide ? 'flex-row' : 'flex-col')}
          style={{ flex: `0 0 ${layout.movieHeightPct}%` }}
        >
          <div className="min-h-0 min-w-0 flex-1 overflow-hidden p-2">
            {busy ? <p className="text-[11px] text-muted-foreground">Simulando Auto D→hoy…</p> : null}
            {err ? (
              <p className="text-[11px] text-destructive" role="alert">
                {err}
              </p>
            ) : null}
            {!busy && !err && detail && bars.length > 0 ? (
              <BacktestReplayChart
                key={detail.id}
                detail={detail}
                bars={bars}
                initialShowAll={false}
                height="fill"
                pauseOnTrade={pauseOnTrade}
                pauseTrades={pauseTrades}
                resumeNonce={resumeNonce}
                onPausedAtTrade={(trade) => setPendingTrade(trade)}
                onReplayCursorChange={handleReplayCursorChange}
                cursorFavorites={hudPrefs.prefs.cursorFavorites}
                onToggleCursorFavorite={hudPrefs.toggleCursorFavorite}
                cursorPanelPos={hudPrefs.prefs.cursorPanelPos}
                onCursorPanelPosChange={hudPrefs.setCursorPanelPos}
                movieHud={
                  movieStats ? (
                    <BacktestMovieHud
                      inline
                      cursorTimestamp={replayCursor}
                      barIndex={replayBarIndex}
                      barTotal={replayBarTotal || detail.barCount}
                      playing={replayPlaying}
                      atEnd={replayAtEnd}
                      balance={
                        liveEquity ??
                        (replayAtEnd || replayCursor == null ? detail.finalEquity : detail.initialCash)
                      }
                      returnPct={
                        liveReturnPct ??
                        (replayAtEnd || replayCursor == null ? detail.totalReturnPct : 0)
                      }
                      stats={movieStats}
                      totalOps={detail.tradeCount}
                      markPrice={markPrice}
                      favorites={hudPrefs.prefs.temporalFavorites}
                      onToggleFavorite={hudPrefs.toggleTemporalFavorite}
                    />
                  ) : null
                }
              />
            ) : null}
            {!busy && !err && detail && bars.length === 0 && !ohlcvQuery.isLoading ? (
              <p className="text-[11px] text-muted-foreground">Sin barras OHLCV para la película.</p>
            ) : null}
          </div>

          {isWide && report ? (
            <DiaDSessionReportPanel variant="desktop" {...reportPanelProps} />
          ) : null}
        </div>

        {!isWide && report ? (
          <DiaDSessionReportPanel variant="mobile" {...reportPanelProps} />
        ) : null}

        <PanelResizeHandle
          label="Redimensionar película y evolución del dinero"
          orientation="horizontal"
          onDrag={(dy) => {
            const shell = movieRowRef.current?.parentElement;
            if (!shell) return;
            const next = clampMovieHeightPct(pendingMovieH.current + pxToPct(dy, shell.clientHeight));
            pendingMovieH.current = next;
            setLayout((prev) => ({ ...prev, movieHeightPct: next }));
          }}
          onDragEnd={() => persistLayout({ movieHeightPct: pendingMovieH.current })}
        />

        <div
          ref={bottomRowRef}
          className={cn('flex min-h-[160px] overflow-hidden border-t border-border/50', isWideBottom ? 'flex-row' : 'flex-col')}
          style={{ flex: '1 1 auto' }}
        >
          <section
            className="flex min-h-0 min-w-0 flex-col gap-1 overflow-hidden p-2"
            style={
              isWideBottom
                ? { width: `${layout.equityWidthPct}%` }
                : { height: `${Math.max(35, Math.min(65, layout.equityWidthPct))}%` }
            }
          >
            <h3 className="shrink-0 text-[11px] font-medium text-foreground">Evolución del dinero</h3>
            {equityCurve.length > 0 && detail ? (
              <div className="min-h-0 flex-1">
                <BacktestEquityChart
                  points={equityCurve}
                  trades={detail.trades}
                  initialCash={detail.initialCash}
                  focusTimestamp={focusTimestamp}
                  untilTimestamp={replayCursor}
                  height="fill"
                />
              </div>
            ) : (
              <p className="text-[11px] text-muted-foreground">Sin curva de patrimonio.</p>
            )}
          </section>

          <PanelResizeHandle
            label="Redimensionar patrimonio y operaciones"
            orientation={isWideBottom ? 'vertical' : 'horizontal'}
            onDrag={(delta) => {
              const row = bottomRowRef.current;
              if (!row) return;
              const size = isWideBottom ? row.clientWidth : row.clientHeight;
              const next = clampEquityWidthPct(pendingEquityW.current + pxToPct(delta, size));
              pendingEquityW.current = next;
              setLayout((prev) => ({ ...prev, equityWidthPct: next }));
            }}
            onDragEnd={() => persistLayout({ equityWidthPct: pendingEquityW.current })}
            className={isWideBottom ? 'mx-0.5' : undefined}
          />

          <DiaDTradesPanel
            detail={detail}
            replayCursor={replayCursor}
            focusTimestamp={focusTimestamp}
            onFocusTimestamp={setFocusTimestamp}
          />
        </div>
      </div>
    </div>
  );
}
