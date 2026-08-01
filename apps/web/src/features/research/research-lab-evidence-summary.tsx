import type { ResearchTrialDto } from '@bolsa/shared';
import { summarizeLabEvidenceFromTrial } from '@/features/research/research-lab-evidence';
import { cn } from '@/lib/utils';

type Props = {
  trial?: ResearchTrialDto | null;
  /** `cell` = table; `panel` = detail strip. */
  variant?: 'cell' | 'panel';
  className?: string;
};

/** Observatory readout of lab OOS/WF/CPCV/PBO/Edge from trial.blocks. */
export function ResearchLabEvidenceSummary({
  trial,
  variant = 'panel',
  className,
}: Props) {
  const summary = summarizeLabEvidenceFromTrial(trial);

  if (variant === 'cell') {
    return (
      <span
        className={cn(
          'tabular-nums',
          summary.hasLab ? 'text-foreground' : 'text-muted-foreground',
          className,
        )}
        title={summary.title}
      >
        {summary.compact}
      </span>
    );
  }

  if (!summary.hasLab) return null;

  return (
    <div
      className={cn(
        'rounded-md border border-border/70 bg-muted/30 px-2.5 py-2 text-[11px] text-muted-foreground',
        className,
      )}
      title={summary.title}
    >
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        Validación lab
      </p>
      <p className="mt-0.5 text-foreground">{summary.compact}</p>
      <p className="mt-0.5">Desde blocks del trial · no es gate de producción.</p>
    </div>
  );
}
