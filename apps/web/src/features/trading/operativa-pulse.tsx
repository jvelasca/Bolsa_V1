/**
 * Bloque visual Índice Operativo + gauges TA/FA + ranking «El n de N en estudio».
 * Se muestra en Operativa → Recomendación (detalle) y resumen en cabecera colapsada.
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import { cn } from '@/lib/utils';
import {
  estudioRankProgressPct,
  formatEstudioRankLabel,
} from '@/features/trading/operativa-index';

function scoreTone(score: number | null): string {
  if (score == null) return 'text-muted-foreground';
  if (score >= 70) return 'text-emerald-700 dark:text-emerald-300';
  if (score >= 45) return 'text-amber-800 dark:text-amber-200';
  return 'text-destructive';
}

function Gauge({
  label,
  value,
  emphasize,
}: {
  label: string;
  value: number | null;
  emphasize?: boolean;
}) {
  const pct = value ?? 0;
  const r = 18;
  const c = 2 * Math.PI * r;
  const dash = value == null ? 0 : (pct / 100) * c;
  return (
    <div
      className={cn('flex flex-col items-center gap-0.5', emphasize && 'scale-105')}
      title={`${label}: ${value ?? '—'}`}
    >
      <svg width="48" height="48" viewBox="0 0 48 48" className="shrink-0" aria-hidden>
        <circle
          cx="24"
          cy="24"
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          className="text-muted/40"
        />
        <circle
          cx="24"
          cy="24"
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          transform="rotate(-90 24 24)"
          className={scoreTone(value)}
        />
        <text
          x="24"
          y="26"
          textAnchor="middle"
          className={cn('fill-current text-[11px] font-semibold tabular-nums', scoreTone(value))}
          style={{ fontSize: 11 }}
        >
          {value ?? '—'}
        </text>
      </svg>
      <span
        className={cn(
          'text-[9px] font-semibold uppercase tracking-wide text-muted-foreground',
          emphasize && 'text-foreground',
        )}
      >
        {label}
      </span>
    </div>
  );
}

export function OperativaPulseBlock({
  io,
  ta,
  fa,
  rank,
  total,
  loading,
  className,
}: {
  io: number | null;
  ta: number | null;
  fa: number | null;
  rank: number | null;
  total: number;
  loading?: boolean;
  className?: string;
}) {
  const progress =
    rank != null && total > 0 ? estudioRankProgressPct(rank, total) : 0;
  const rankLabel =
    rank != null && total > 0 ? formatEstudioRankLabel(rank, total) : 'Sin ranking en estudio';

  return (
    <div
      className={cn('space-y-2', className)}
      data-testid="operativa-pulse"
      aria-label="Índice operativo"
    >
      <div className="flex items-end justify-around gap-1 px-1">
        <Gauge label="IO" value={loading ? null : io} emphasize />
        <Gauge label="TA" value={loading ? null : ta} />
        <Gauge label="FA" value={loading ? null : fa} />
      </div>
      <div className="space-y-1">
        <p className="text-center text-[11px] font-medium text-foreground" data-testid="operativa-rank-label">
          {loading ? 'Calculando ranking…' : rankLabel}
        </p>
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          title={rankLabel}
          role="meter"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full bg-emerald-500/80 transition-[width]"
            style={{ width: `${loading ? 0 : progress}%` }}
          />
        </div>
        <p className="text-center text-[9px] text-muted-foreground">
          Índice Operativo · posición entre valores en estudio
        </p>
      </div>
    </div>
  );
}

/** Resumen compacto para cabecera colapsada. */
export function OperativaPulseSummary({
  io,
  rank,
  total,
}: {
  io: number | null;
  rank: number | null;
  total: number;
}) {
  if (rank == null || total <= 0) {
    return (
      <span className={cn('tabular-nums', scoreTone(io))}>
        IO {io ?? '—'}
      </span>
    );
  }
  return (
    <span className="truncate text-[10px] text-muted-foreground">
      <span className={cn('font-semibold tabular-nums', scoreTone(io))}>IO {io ?? '—'}</span>
      {' · '}
      {rank}/{total}
    </span>
  );
}
