/**
 * Quorum visible A / A2 / B / C + «por qué #1» (F4).
 */

import type { CoachQuorumSnapshot } from '@/features/backtests/coach-dual-audit';
import { cn } from '@/lib/utils';

type Props = {
  quorum: CoachQuorumSnapshot;
  className?: string;
};

export function CoachQuorumBar({ quorum, className }: Props) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex flex-wrap items-center gap-1">
        {quorum.chips.map((chip) => (
          <span
            key={chip.id}
            title={chip.detail}
            className={cn(
              'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px]',
              chip.tone === 'ok' && 'border-emerald-500/35 bg-emerald-500/10 text-emerald-200',
              chip.tone === 'warn' && 'border-amber-500/40 bg-amber-500/10 text-amber-100',
              chip.tone === 'muted' && 'border-border/70 bg-muted/30 text-muted-foreground',
            )}
          >
            <span className="font-semibold">{chip.label}</span>
            <span className="max-w-[9rem] truncate opacity-90">{chip.detail}</span>
          </span>
        ))}
        <span
          className={cn(
            'rounded-md border px-1.5 py-0.5 text-[10px]',
            quorum.agree
              ? 'border-emerald-500/30 text-emerald-200/90'
              : 'border-border text-muted-foreground',
          )}
          title="A≈A2, B challenge OK y C no vetó el crowning"
        >
          {quorum.agree ? 'Quorum OK' : 'Quorum abierto'}
        </span>
      </div>
      <p className="text-[10px] leading-snug text-muted-foreground">
        <span className="font-medium text-foreground/80">Por qué #1: </span>
        {quorum.whyTop1}
      </p>
    </div>
  );
}
