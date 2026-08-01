/**
 * Miniresumen scores FA + TA en la barra general del workspace.
 * Clic → Backtesting Análisis fundamental / técnico del valor activo.
 * Si no hay FA, dispara búsqueda Yahoo e informa del estado.
 */

import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useEnsureInstrumentFundamentals } from '@/features/instruments/use-ensure-instrument-fundamentals';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

type Props = {
  instrumentId: string;
  className?: string;
};

function tone(score100: number | null): string {
  if (score100 == null) return 'text-muted-foreground';
  if (score100 >= 70) return 'text-emerald-700 dark:text-emerald-300';
  if (score100 >= 45) return 'text-amber-800 dark:text-amber-200';
  return 'text-destructive';
}

/** Pierna Composite ∈ [-1,+1] → display 0..100. */
function legToDisplay100(score: number | null | undefined): number | null {
  if (score == null || !Number.isFinite(score)) return null;
  return Math.round(Math.max(0, Math.min(100, (score + 1) * 50)));
}

function ScoreChip({
  label,
  score100,
  to,
  title,
  busy,
}: {
  label: string;
  score100: number | null;
  to: string;
  title: string;
  busy?: boolean;
}) {
  return (
    <Link
      to={to}
      title={title}
      className={cn(
        'inline-flex h-[1.375rem] shrink-0 items-center gap-1 rounded border border-border/70 bg-background/60 px-1.5 text-[10px] font-medium hover:border-primary/40 hover:bg-accent',
        tone(score100),
        busy && 'opacity-80',
      )}
    >
      <span className="text-muted-foreground">{label}</span>
      {busy ? (
        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" aria-hidden />
      ) : (
        <span className="tabular-nums">{score100 != null ? score100 : '—'}</span>
      )}
    </Link>
  );
}

export function ChartAnalysisScoreButtons({ instrumentId, className }: Props) {
  const {
    card,
    status,
    statusLabel,
    isRefreshing,
  } = useEnsureInstrumentFundamentals(instrumentId);

  const compositeQuery = useQuery({
    queryKey: ['instrument-composite', instrumentId, 'swing', 'neutral'],
    queryFn: () =>
      api.getInstrumentComposite(instrumentId, { horizon: 'swing', regime: 'neutral' }),
    enabled: Boolean(instrumentId) && status === 'ready',
    staleTime: 60_000,
  });

  const fundScore = card?.scoreDisplay100 ?? null;
  const techLeg = compositeQuery.data?.data?.legs?.find((l) => l.key === 'technical');
  const techScore = legToDisplay100(techLeg?.score ?? null);
  const faBusy = status === 'loading' || status === 'refreshing';

  const base = `/backtests?instrumentId=${encodeURIComponent(instrumentId)}`;

  const faTitle =
    status === 'refreshing' || status === 'loading'
      ? statusLabel
      : status === 'empty' || status === 'error'
        ? statusLabel
        : 'Análisis fundamental (Score_FUND) → Backtesting';

  return (
    <div
      className={cn('flex shrink-0 flex-col items-end gap-0.5', className)}
      role="group"
      aria-label="Scores análisis técnico y fundamental"
    >
      <div className="flex items-center gap-1">
        <ScoreChip
          label="TA"
          score100={techScore}
          to={`${base}&focus=detail`}
          title={
            techLeg?.method
              ? `Análisis técnico (${techLeg.method}) → Backtesting`
              : 'Análisis técnico → Backtesting'
          }
        />
        <ScoreChip
          label="FA"
          score100={faBusy ? null : fundScore}
          to={`${base}&focus=fundamental`}
          title={faTitle}
          busy={faBusy}
        />
      </div>
      {(status === 'refreshing' || status === 'empty' || status === 'error') && statusLabel ? (
        <p
          className={cn(
            'max-w-[14rem] truncate text-[9px] leading-tight',
            status === 'error' ? 'text-destructive' : 'text-muted-foreground',
          )}
          title={statusLabel}
        >
          {isRefreshing ? 'Actualizando FA…' : status === 'empty' ? 'FA sin datos' : status === 'error' ? 'FA error' : statusLabel}
        </p>
      ) : null}
    </div>
  );
}
