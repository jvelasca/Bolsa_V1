/**
 * Panel Operativa (Trading) — Recomendación (Pulso+TOP) / Info (por activo).
 *
 * Manual/SEMI/AUTO = cuenta entera → barra de estado / Cuentas (no aquí).
 * Supervisión Lab lista Estudio = banner Estudio.
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { useWorkspaceStore } from '@/stores/workspace-store';
import { instrumentTopBacktestsHref } from '@/features/backtests/instrument-strategy-top-panel';
import {
  finalistsStabilityWarnTitle,
  formatFinalistsStabilityBadge,
  readLabEvidenceFromCoachFacts,
} from '@/features/backtests/finalists-stability-summary';
import { diaDVerifyHref, VERIFY_DIA_D_CTA } from '@/features/platform/product-universe';
import {
  STRATEGY_ADOPTION_LABELS,
  getAdoptionState,
  type StrategyAdoptionState,
} from '@/features/platform/strategy-adoption';
import { MandateTimelinePanel } from '@/features/trading/mandate-timeline-panel';
import {
  demoBookAllowsEnqueueConfirm,
  demoBookRequiresEstudioMembership,
} from '@/features/trading/demo-book-prefs';
import { useDemoBookPrefs } from '@/features/trading/use-demo-book-prefs';
import { proposeInstrumentSupervised } from '@/features/trading/propose-instrument-supervised';
import { TradingOperativaSection } from '@/features/trading/trading-operativa-section';
import { useEstudioMembershipStore } from '@/stores/estudio-membership-store';
import {
  OperativaPulseBlock,
  OperativaPulseSummary,
} from '@/features/trading/operativa-pulse';
import { OperativaDictamenBlock } from '@/features/trading/operativa-dictamen';
import { OperativaOutcomesBlock } from '@/features/trading/operativa-outcomes';
import { useInstrumentDailyOpinions } from '@/features/trading/use-instrument-daily-opinions';
import {
  computeIndiceOperativo,
  rankIndiceOperativo,
  type OperativaScoreRow,
} from '@/features/trading/operativa-index';
import { useInstrumentsHubScores } from '@/features/instruments/use-instruments-hub-scores';
import { getDiaDExperimentTop1 } from '@/features/backtests/dia-d-experiment-top';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { effectiveDiaD, isDiaDInPast, todayIsoDate } from '@/features/backtests/backtest-period';
import { loadBacktestRunContext } from '@/features/backtests/backtest-run-context';
import { useDiaDTradingSessionStore } from '@/stores/dia-d-trading-session-store';
import { useAlertsStore } from '@/stores/alerts-store';
import {
  openHelpAiPlatform,
  useSupervisedF3QueueStore,
} from '@/stores/supervised-f3-queue-store';
import { cn } from '@/lib/utils';
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import type { InstrumentDailyOpinionHintV1 } from '@bolsa/shared';
import {
  getMandateStoreSnapshot,
  listOpenMandateTenures,
  subscribeMandateStore,
  summarizeMandateChurn,
} from '@/features/platform/operating-mandate';
import { ensureMandateHydrated } from '@/features/platform/operating-mandate-sync';

function formatAdoption(state: StrategyAdoptionState): string {
  return STRATEGY_ADOPTION_LABELS[state];
}

export function TradingOperativaPanel({ className }: { className?: string }) {
  const navigate = useNavigate();
  const enterSession = useDiaDTradingSessionStore((s) => s.enterSession);
  const charts = useWorkspaceStore((s) => s.workspace.charts);
  const activeChartId = useWorkspaceStore((s) => s.workspace.activeChartId);
  const active = charts.find((c) => c.id === activeChartId) ?? charts[0];
  const instrumentId = active?.instrumentId ?? null;
  const symbol = active?.label ?? '—';
  const timeframe = (active?.timeframe as string) || '1d';
  const { effectiveAccountId } = useActiveAccount();
  const bookPrefs = useDemoBookPrefs();
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enqueueSupervised = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActiveSupervised = useSupervisedF3QueueStore((s) => s.setActive);
  const confirmQueueCount = useSupervisedF3QueueStore((s) => s.items.length);
  const mandateRev = useSyncExternalStore(
    subscribeMandateStore,
    getMandateStoreSnapshot,
    () => 0,
  );
  const diaD = loadBacktestRunContext().diaD;
  const canVerify = isDiaDInPast(diaD);

  const studyEntries = useEstudioMembershipStore((s) => s.members);
  const studyContains = useEstudioMembershipStore((s) => s.contains);
  const upsertStudyMembers = useEstudioMembershipStore((s) => s.upsertMembers);
  const studyIds = useMemo(
    () => studyEntries.map((entry) => entry.instrumentId),
    [studyEntries],
  );
  const inEstudio = instrumentId ? studyContains(instrumentId) : false;
  const requiresEstudio = demoBookRequiresEstudioMembership(bookPrefs.mode);
  const canEnqueueConfirm = demoBookAllowsEnqueueConfirm(bookPrefs.mode);

  const portfolioQuery = useQuery({
    queryKey: ['portfolio', 'operativa'],
    queryFn: api.getPortfolio,
    staleTime: 30_000,
  });
  const positionOpen = useMemo(() => {
    if (!instrumentId) return false;
    const positions = portfolioQuery.data?.data.positions ?? [];
    return positions.some(
      (p) => p.instrumentId === instrumentId && Math.abs(Number(p.quantity ?? 0)) > 0,
    );
  }, [instrumentId, portfolioQuery.data]);

  const { faByInstrument, taByInstrument, scoresLoading } = useInstrumentsHubScores(studyIds);

  const scoreRows: OperativaScoreRow[] = useMemo(
    () =>
      studyIds.map((id) => {
        const ta = taByInstrument.get(id);
        const fa = faByInstrument.get(id);
        return {
          instrumentId: id,
          io: computeIndiceOperativo({
            compositeDisplay100: ta?.compositeDisplay100,
            distress: fa?.distress,
          }),
          ta: ta?.technicalDisplay100 ?? null,
          fa: fa?.scoreDisplay100 ?? null,
          distress: fa?.distress,
        };
      }),
    [studyIds, taByInstrument, faByInstrument],
  );

  const rankResult = useMemo(
    () => (instrumentId ? rankIndiceOperativo(scoreRows, instrumentId) : null),
    [scoreRows, instrumentId],
  );

  const opinionHints: InstrumentDailyOpinionHintV1[] = useMemo(() => {
    if (!instrumentId) return [];
    const fa = faByInstrument.get(instrumentId);
    const ta = taByInstrument.get(instrumentId);
    const row = scoreRows.find((r) => r.instrumentId === instrumentId);
    return [
      {
        instrumentId,
        ioScore: row?.io ?? null,
        faScore: fa?.scoreDisplay100 ?? null,
        taScore: ta?.technicalDisplay100 ?? null,
        distress: Boolean(fa?.distress),
        positionOpen,
        allowTrading: true,
        hasEodBar: true,
      },
    ];
  }, [instrumentId, faByInstrument, taByInstrument, scoreRows, positionOpen]);

  const opinionsQuery = useInstrumentDailyOpinions(
    instrumentId ? [instrumentId] : [],
    opinionHints,
    { enabled: Boolean(instrumentId) && !scoresLoading },
  );
  const activeOpinion = opinionsQuery.data?.[0];

  useEffect(() => {
    if (!effectiveAccountId) return;
    void ensureMandateHydrated(effectiveAccountId);
  }, [effectiveAccountId]);

  const openTenures = useMemo(
    () => listOpenMandateTenures(effectiveAccountId),
    [effectiveAccountId, mandateRev],
  );
  const churn = useMemo(
    () => summarizeMandateChurn({ accountId: effectiveAccountId }),
    [effectiveAccountId, mandateRev],
  );

  const topQuery = useQuery({
    queryKey: ['instrument-strategy-top', instrumentId, timeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId!, timeframe),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
    retry: false,
  });

  const top = topQuery.data?.data ?? null;
  const slot1 = top?.slots?.slice().sort((a, b) => a.rank - b.rank)[0] ?? null;

  const proposeMutation = useMutation({
    mutationFn: async () => {
      if (!instrumentId) throw new Error('Sin instrumento');
      if (!effectiveAccountId) throw new Error('Sin cuenta DEMO activa');
      const topSlot =
        topQuery.data?.data?.slots?.slice().sort((a, b) => a.rank - b.rank)[0] ?? null;
      return proposeInstrumentSupervised({
        instrumentId,
        symbol,
        accountId: effectiveAccountId,
        source: 'operativa',
        strategyDefinitionId: topSlot?.strategyDefinitionId ?? null,
        strategyLabel: topSlot?.label ?? symbol,
      });
    },
    onSuccess: (payload) => {
      const id = enqueueSupervised(payload, {
        symbol: payload.symbol ?? symbol,
        origin: 'operativa',
      });
      setActiveSupervised(id);
      pushToast(`Operativa · ${payload.symbol ?? symbol}: ${payload.action} → Confirm`);
      openHelpAiPlatform({ panel: 'supervised-f3' });
    },
    onError: (e: Error) => {
      pushToast(`Operativa · ${symbol}: ${e.message}`);
    },
  });

  const labEvidence = readLabEvidenceFromCoachFacts(
    top?.coachFacts as Record<string, unknown> | null | undefined,
  );
  const stabilityBadge = formatFinalistsStabilityBadge(labEvidence);
  const stabilityWarn = finalistsStabilityWarnTitle(labEvidence);
  const adoption = instrumentId
    ? getAdoptionState(instrumentId, effectiveAccountId)
    : 'none';

  if (!instrumentId) {
    return (
      <div
        className={cn(
          'flex h-full min-h-0 flex-col gap-2 overflow-y-auto p-2 text-[11px] text-muted-foreground',
          className,
        )}
        data-testid="trading-operativa-panel-empty"
      >
        <p className="font-medium text-foreground">Sin valor activo</p>
        <p>Abre un instrumento en el gráfico para ver recomendación, info y configuración.</p>
      </div>
    );
  }

  function startVerify() {
    if (!instrumentId) return;
    const asOf = effectiveDiaD(diaD);
    const exp1 = isDiaDInPast(diaD)
      ? getDiaDExperimentTop1(instrumentId, timeframe, asOf)
      : null;
    const strategyDefinitionId =
      exp1?.strategyDefinitionId ?? slot1?.strategyDefinitionId ?? null;
    if (!strategyDefinitionId) return;
    enterSession({
      instrumentId,
      symbol,
      strategyDefinitionId,
      strategyLabel: exp1?.label ?? slot1?.label ?? 'Finalista',
      rank: exp1?.rank ?? slot1?.rank ?? 1,
      diaD: asOf,
      endDate: todayIsoDate(),
      mode: 'auto',
    });
    navigate(diaDVerifyHref(instrumentId));
  }

  const pulseSummary = (
    <OperativaPulseSummary
      io={rankResult?.io ?? null}
      rank={rankResult?.rank ?? null}
      total={rankResult?.total ?? studyIds.length}
    />
  );

  return (
    <div
      className={cn('flex h-full min-h-0 flex-col gap-2 overflow-hidden p-2 text-[11px]', className)}
      data-testid="trading-operativa-panel"
      aria-label={`Operativa · ${symbol}`}
    >
      <p className="shrink-0 px-0.5 text-[10px] font-medium text-muted-foreground">
        {symbol} · {timeframe}
        {positionOpen ? ' · en cartera' : ''}
      </p>

      {requiresEstudio && !inEstudio ? (
        <div
          className="shrink-0 rounded-md border border-amber-600/40 bg-amber-500/10 px-2 py-1.5 text-[10px]"
          data-testid="operativa-fuera-estudio"
        >
          <p className="font-medium text-amber-950 dark:text-amber-50">
            Fuera de Estudio — {bookPrefs.mode.toUpperCase()} exige membresía
          </p>
          <button
            type="button"
            className="mt-1 rounded border border-amber-700/40 bg-background/60 px-1.5 py-0.5 font-medium text-foreground hover:bg-accent"
            onClick={() => {
              if (!instrumentId) return;
              void (async () => {
                const { addToEstudioMembership } = await import(
                  '@/features/trading/estudio-membership'
                );
                const { added, ids } = await addToEstudioMembership([
                  {
                    id: instrumentId,
                    symbol,
                    yahooSymbol: symbol,
                    name: symbol,
                    exchange: '—',
                    country: '—',
                    currency: 'EUR',
                    sector: null,
                    isActive: true,
                    meta: { barCount: 0, lastSync: null, lastClose: null, changePct: null },
                  },
                ]);
                if (added <= 0) return;
                upsertStudyMembers([{ instrumentId, symbol, name: symbol }]);
                pushToast(`${symbol} → Estudio · actualizando…`);
                const { runEstudioInstrumentsUpdate } = await import(
                  '@/features/trading/estudio-instruments-update'
                );
                await runEstudioInstrumentsUpdate({
                  instrumentIds: ids,
                  rediscover: false,
                  phaseLabel: 'Alta Estudio',
                  symbolOf: () => symbol,
                });
                pushToast(`${symbol} → Estudio · datos al día`);
              })();
            }}
          >
            Añadir a Estudio
          </button>
        </div>
      ) : null}

      <TradingOperativaSection
        sectionId="recommendation"
        title="Recomendación"
        summary={pulseSummary}
      >
        <OperativaPulseBlock
          io={rankResult?.io ?? null}
          ta={rankResult?.ta ?? null}
          fa={rankResult?.fa ?? null}
          rank={rankResult?.rank ?? null}
          total={rankResult?.total ?? studyIds.length}
          loading={scoresLoading}
        />

        <OperativaDictamenBlock
          opinion={activeOpinion}
          loading={opinionsQuery.isLoading || scoresLoading}
        />

        {topQuery.isLoading ? (
          <p className="text-muted-foreground">Cargando TOP…</p>
        ) : slot1 ? (
          <div className="rounded-md border border-border/70 bg-muted/20 px-2 py-1.5">
            <p className="font-medium text-foreground">
              TOP #{slot1.rank} {slot1.label}
            </p>
            <p className="text-muted-foreground">
              {slot1.source}
              {slot1.totalReturnPct != null
                ? ` · ret ${slot1.totalReturnPct.toFixed(1)}%`
                : ''}
            </p>
            {stabilityBadge ? (
              <p
                className="mt-0.5 text-[10px] text-muted-foreground"
                title={stabilityWarn ?? undefined}
                data-testid="operativa-stability"
              >
                {stabilityBadge}
              </p>
            ) : null}
          </div>
        ) : (
          <p className="text-muted-foreground">Sin Finalistas TOP aún.</p>
        )}

        <p className="text-muted-foreground">
          Adopción:{' '}
          <span className="font-medium text-foreground">{formatAdoption(adoption)}</span>
        </p>

        <MandateTimelinePanel
          instrumentId={instrumentId}
          accountId={effectiveAccountId}
          compact
        />

        <div className="flex flex-col gap-1">
          <button
            type="button"
            data-testid="operativa-proponer-f3"
            className="rounded-md border border-emerald-700/35 bg-emerald-500/10 px-2 py-1 text-left font-medium text-emerald-950 hover:bg-emerald-500/20 disabled:opacity-50 dark:text-emerald-50"
            disabled={
              proposeMutation.isPending ||
              !effectiveAccountId ||
              (requiresEstudio && !inEstudio) ||
              !canEnqueueConfirm
            }
            title={
              !canEnqueueConfirm
                ? 'Cambia a SEMI en Configuración para Proponer F3'
                : requiresEstudio && !inEstudio
                  ? 'Añade el valor a Estudio primero'
                  : 'Propose → cola Confirm (Camino C)'
            }
            onClick={() => proposeMutation.mutate()}
          >
            {proposeMutation.isPending
              ? 'Proponiendo…'
              : !canEnqueueConfirm
                ? 'Proponer F3 (pasa a SEMI)'
                : 'Proponer F3 → Confirm'}
          </button>
          <button
            type="button"
            data-testid="operativa-cola-confirm"
            className="rounded-md border border-border px-2 py-1 text-left font-medium text-foreground hover:bg-accent"
            onClick={() => openHelpAiPlatform({ panel: 'supervised-f3' })}
          >
            Cola Confirm{confirmQueueCount > 0 ? ` (${confirmQueueCount})` : ''}
          </button>
          <Link
            to={instrumentTopBacktestsHref(instrumentId, timeframe)}
            className="rounded-md border border-sky-600/30 bg-sky-500/10 px-2 py-1 font-medium text-sky-950 hover:bg-sky-500/20 dark:text-sky-50"
          >
            Abrir estudio (LAB)
          </Link>
          {canVerify &&
          (slot1?.strategyDefinitionId ||
            (instrumentId &&
              getDiaDExperimentTop1(instrumentId, timeframe, effectiveDiaD(diaD))
                ?.strategyDefinitionId)) ? (
            <button
              type="button"
              className="rounded-md border border-amber-600/30 bg-amber-500/10 px-2 py-1 text-left font-medium text-amber-950 hover:bg-amber-500/20 dark:text-amber-50"
              onClick={startVerify}
            >
              {VERIFY_DIA_D_CTA}
            </button>
          ) : null}
        </div>
      </TradingOperativaSection>

      <TradingOperativaSection
        sectionId="info"
        title="Info"
        summary={
          <span className="text-[10px] text-muted-foreground">
            Activas {churn.openCount}
            {confirmQueueCount > 0 ? ` · Confirm ${confirmQueueCount}` : ''}
          </span>
        }
      >
        <div data-testid="operativa-mandate-review" className="space-y-2">
          <div className="space-y-1 rounded-md border border-border/60 bg-muted/20 px-2 py-1.5">
            <p className="font-semibold text-foreground">
              Estrategia activa{' '}
              <span className="font-normal text-muted-foreground">(mandato)</span>
            </p>
            <p className="text-[10px] leading-snug text-muted-foreground">
              Un <span className="font-medium text-foreground/90">mandato</span> es el
              plan que estás siguiendo en un valor con esta cuenta: qué estrategia
              usas ahora. No es una orden de compra/venta; es el compromiso vigente
              hasta que lo cambies o lo cierres.
            </p>
            <p className="text-[10px] text-muted-foreground">
              En esta cuenta:{' '}
              <span className="font-medium text-foreground">
                {churn.openCount} activa{churn.openCount === 1 ? '' : 's'}
              </span>
              {churn.closedCount > 0
                ? ` · ${churn.closedCount} cerrada${churn.closedCount === 1 ? '' : 's'}`
                : ''}
            </p>
            {openTenures.length > 0 ? (
              <ul className="space-y-0.5 text-[10px] text-muted-foreground">
                {openTenures.slice(0, 8).map((t) => (
                  <li key={t.id} className="flex items-center gap-1.5">
                    <span
                      className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500"
                      aria-hidden
                    />
                    <span className="min-w-0 truncate">
                      {t.strategyLabelSnapshot ?? t.instrumentId.slice(0, 8)}
                      <span className="text-foreground/70"> · en vigor</span>
                    </span>
                  </li>
                ))}
                {openTenures.length > 8 ? (
                  <li>+{openTenures.length - 8} más</li>
                ) : null}
              </ul>
            ) : (
              <p className="text-[10px] leading-snug text-muted-foreground">
                Ninguna estrategia activa aún. En SEMI, confirma una propuesta
                (Confirm) o adopta un Finalista del Lab para abrir el mandato.
              </p>
            )}
            <details className="group pt-0.5">
              <summary className="cursor-pointer select-none text-[10px] font-medium text-foreground/90 marker:content-none [&::-webkit-details-marker]:hidden">
                <span className="underline-offset-2 group-open:underline">
                  Más detalle (avanzado)
                </span>
              </summary>
              <div className="mt-1 space-y-1 border-t border-border/40 pt-1 text-[10px] leading-snug text-muted-foreground">
                <p>
                  Técnico: tenure por instrumento×cuenta (ADR-020). Cambiar de
                  estrategia cierra el tenure anterior y abre uno nuevo (churn).
                </p>
                <p>
                  Learning / Outcomes abajo mide si las decisiones Confirm de este
                  valor salieron bien a posteriori — no es el dictamen del día.
                </p>
              </div>
            </details>
          </div>
          <OperativaOutcomesBlock
            instrumentId={instrumentId}
            accountId={effectiveAccountId}
            symbol={symbol}
          />
        </div>
      </TradingOperativaSection>

    </div>
  );
}

/** @deprecated Usar TradingOperativaPanel */
export const TradingCoachRail = TradingOperativaPanel;
