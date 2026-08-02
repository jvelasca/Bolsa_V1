/**
 * Rail Coach en Trading — TOP / frescura / puente LAB (ADR-019 U3).
 * Lectura + deep-links; no escribe DEMO ni reescribe TOP.
 */

import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { FlaskConical } from 'lucide-react';
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
import { getDiaDExperimentTop1 } from '@/features/backtests/dia-d-experiment-top';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { effectiveDiaD, isDiaDInPast, todayIsoDate } from '@/features/backtests/backtest-period';
import { loadBacktestRunContext } from '@/features/backtests/backtest-run-context';
import { useDiaDTradingSessionStore } from '@/stores/dia-d-trading-session-store';
import { cn } from '@/lib/utils';
import { useSyncExternalStore } from 'react';
import {
  getMandateStoreSnapshot,
  subscribeMandateStore,
} from '@/features/platform/operating-mandate';

function formatAdoption(state: StrategyAdoptionState): string {
  return STRATEGY_ADOPTION_LABELS[state];
}

export function TradingCoachRail({ className }: { className?: string }) {
  const navigate = useNavigate();
  const enterSession = useDiaDTradingSessionStore((s) => s.enterSession);
  const charts = useWorkspaceStore((s) => s.workspace.charts);
  const activeChartId = useWorkspaceStore((s) => s.workspace.activeChartId);
  const active = charts.find((c) => c.id === activeChartId) ?? charts[0];
  const instrumentId = active?.instrumentId ?? null;
  const symbol = active?.label ?? '—';
  const timeframe = (active?.timeframe as string) || '1d';
  const { effectiveAccountId } = useActiveAccount();
  useSyncExternalStore(subscribeMandateStore, getMandateStoreSnapshot, () => 0);
  const diaD = loadBacktestRunContext().diaD;
  const canVerify = isDiaDInPast(diaD);

  const topQuery = useQuery({
    queryKey: ['instrument-strategy-top', instrumentId, timeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId!, timeframe),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
    retry: false,
  });

  const top = topQuery.data?.data ?? null;
  const slot1 = top?.slots?.slice().sort((a, b) => a.rank - b.rank)[0] ?? null;
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
      <aside
        className={cn(
          'flex w-[200px] shrink-0 flex-col border-l border-border bg-muted/15 p-2 text-[11px] text-muted-foreground',
          className,
        )}
        data-testid="trading-coach-rail-empty"
      >
        <p className="font-semibold text-foreground">Coach</p>
        <p className="mt-1">Abre un valor en el gráfico para ver TOP y estudio LAB.</p>
      </aside>
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

  return (
    <aside
      className={cn(
        'flex w-[220px] shrink-0 flex-col gap-2 overflow-y-auto border-l border-border bg-muted/15 p-2 text-[11px]',
        className,
      )}
      data-testid="trading-coach-rail"
      aria-label="Coach del instrumento"
    >
      <div className="flex items-center gap-1.5">
        <FlaskConical className="h-3.5 w-3.5 text-sky-700 dark:text-sky-300" aria-hidden />
        <p className="font-semibold text-foreground">Coach · {symbol}</p>
      </div>

      {topQuery.isLoading ? (
        <p className="text-muted-foreground">Cargando TOP…</p>
      ) : slot1 ? (
        <div className="rounded-md border border-border/70 bg-background/70 px-2 py-1.5">
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
              data-testid="coach-rail-stability"
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
    </aside>
  );
}
