/**
 * Hero de zona Lab: veredicto en 2 segundos + badge de qué se corrió.
 */

import { cn } from '@/lib/utils';

export type LabZoneVerdictProps = {
  improved: boolean;
  rankedByOos: boolean;
  beforeParams: string;
  afterParams: string;
  deltaScore?: number | null;
  deltaOosScore?: number | null;
  deltaReturnPct?: number | null;
  deltaDrawdownPct?: number | null;
  engine?: string | null;
  trialsDone?: number | null;
  trialsTotal?: number | null;
  oosPct?: number | null;
  walkForwardFolds?: number | null;
  cpcvPaths?: number | null;
  className?: string;
};

function signDelta(n: number, digits = 2): string {
  const t = n.toFixed(digits);
  return n > 0 ? `+${t}` : t;
}

export function LabZoneVerdictHero({
  improved,
  rankedByOos,
  beforeParams,
  afterParams,
  deltaScore,
  deltaOosScore,
  deltaReturnPct,
  deltaDrawdownPct,
  engine,
  trialsDone,
  trialsTotal,
  oosPct,
  walkForwardFolds,
  cpcvPaths,
  className,
}: LabZoneVerdictProps) {
  const scoreDelta = rankedByOos ? deltaOosScore : deltaScore;
  const scoreLabel = rankedByOos ? 'OOS' : 'IS';

  const runBits: string[] = [];
  if (engine) runBits.push(engine);
  if (trialsDone != null || trialsTotal != null) {
    runBits.push(
      trialsTotal != null
        ? `${trialsDone ?? trialsTotal}/${trialsTotal} trials`
        : `${trialsDone} trials`,
    );
  }
  if (cpcvPaths != null && cpcvPaths > 0) runBits.push(`CPCV×${cpcvPaths}`);
  else if (walkForwardFolds != null && walkForwardFolds > 0) {
    runBits.push(`WF ${walkForwardFolds} folds`);
  } else if (oosPct != null && oosPct > 0) {
    runBits.push(`hold-out ${(oosPct * 100).toFixed(0)}%`);
  }

  return (
    <div
      className={cn(
        'space-y-2 rounded-lg border px-3 py-2.5',
        improved
          ? 'border-emerald-500/45 bg-emerald-500/10'
          : 'border-amber-500/45 bg-amber-500/10',
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            'inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
            improved
              ? 'bg-emerald-500/25 text-emerald-950 dark:text-emerald-50'
              : 'bg-amber-500/25 text-amber-950 dark:text-amber-50',
          )}
        >
          {improved ? 'Mejoró' : 'Sin mejora clara'}
        </span>
        {scoreDelta != null && Number.isFinite(scoreDelta) && (
          <span className="text-sm font-semibold tabular-nums text-foreground">
            {scoreLabel} {signDelta(scoreDelta)}
          </span>
        )}
        {deltaReturnPct != null && Number.isFinite(deltaReturnPct) && (
          <span className="text-[11px] tabular-nums text-muted-foreground">
            ret {signDelta(deltaReturnPct, 1)} pp
            {deltaDrawdownPct != null && Number.isFinite(deltaDrawdownPct)
              ? ` · DD ${signDelta(deltaDrawdownPct, 1)} pp${
                  deltaDrawdownPct < 0 ? ' (mejor)' : deltaDrawdownPct > 0 ? ' (peor)' : ''
                }`
              : ''}
          </span>
        )}
      </div>

      <p className="text-xs leading-snug text-foreground">
        <span className="text-muted-foreground">Params</span>{' '}
        <span className="font-medium">{beforeParams}</span>
        <span className="mx-1 text-muted-foreground" aria-hidden>
          →
        </span>
        <span className="font-semibold">{afterParams}</span>
      </p>

      {runBits.length > 0 && (
        <p
          className="text-[10px] text-muted-foreground"
          title="Qué se ejecutó en esta zona (enqueue Coach→Lab o Play manual)"
        >
          Corrió: {runBits.join(' · ')}
        </p>
      )}
    </div>
  );
}

/** Compact line for board header when only metrics known. */
export function formatLabRunBadge(opts: {
  engine?: string | null;
  trialsTotal?: number | null;
  oosPct?: number | null;
}): string {
  const parts: string[] = [];
  if (opts.engine) parts.push(opts.engine);
  if (opts.trialsTotal != null) parts.push(`${opts.trialsTotal} trials`);
  if (opts.oosPct != null && opts.oosPct > 0) {
    parts.push(`OOS ${(opts.oosPct * 100).toFixed(0)}%`);
  }
  return parts.join(' · ') || 'Lab';
}
