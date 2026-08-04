/**
 * Bloque compacto Dictamen (★ dictamen ≠ ★ TOP).
 */

import {
  INSTRUMENT_DAILY_OPINION_STANCE_LABELS,
  type InstrumentDailyOpinionV1,
} from '@bolsa/shared';
import { cn } from '@/lib/utils';

function starsLabel(n: number): string {
  return `${'★'.repeat(n)}${'☆'.repeat(Math.max(0, 5 - n))}`;
}

function stanceTone(stance: InstrumentDailyOpinionV1['stance']): string {
  switch (stance) {
    case 'buy':
      return 'border-emerald-600/40 bg-emerald-500/10 text-emerald-950 dark:text-emerald-50';
    case 'sell_exit':
    case 'reduce':
      return 'border-rose-600/40 bg-rose-500/10 text-rose-950 dark:text-rose-50';
    case 'no_trade':
    case 'review_strategy':
      return 'border-amber-600/40 bg-amber-500/10 text-amber-950 dark:text-amber-50';
    default:
      return 'border-border/70 bg-muted/30 text-foreground';
  }
}

export function OperativaDictamenBlock({
  opinion,
  loading,
  className,
}: {
  opinion: InstrumentDailyOpinionV1 | null | undefined;
  loading?: boolean;
  className?: string;
}) {
  if (loading) {
    return (
      <p className={cn('text-muted-foreground', className)} data-testid="operativa-dictamen">
        Calculando dictamen…
      </p>
    );
  }
  if (!opinion) {
    return (
      <p className={cn('text-muted-foreground', className)} data-testid="operativa-dictamen">
        Sin dictamen aún.
      </p>
    );
  }
  const label = INSTRUMENT_DAILY_OPINION_STANCE_LABELS[opinion.stance] ?? opinion.stance;
  return (
    <div
      className={cn(
        'rounded-md border px-2 py-1.5',
        stanceTone(opinion.stance),
        className,
      )}
      data-testid="operativa-dictamen"
      title={`Dictamen ★${opinion.dictamenStars} · Estrategia ★${opinion.strategyStars ?? '—'} · ${opinion.reasons.join(', ')}`}
    >
      <p className="font-semibold tracking-tight">
        Dictamen · {label}{' '}
        <span className="tabular-nums font-medium opacity-90">
          {starsLabel(opinion.dictamenStars)}
        </span>
      </p>
      <p className="text-[10px] opacity-80">
        ★ dictamen ≠ ★ TOP
        {opinion.strategyStars != null ? ` (TOP ${opinion.strategyStars})` : ''}
        {opinion.distress ? ' · FA distress' : ''}
      </p>
    </div>
  );
}
