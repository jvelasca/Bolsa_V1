/**
 * Progress strip for Lab optimize jobs.
 * Compact mode = zona del tablero (visible sin scroll).
 */

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export type OptimizeProgressPhase =
  | 'pending'
  | 'processing'
  | 'running'
  | 'completed'
  | 'failed';

type Props = {
  phase: OptimizeProgressPhase;
  trialTotal: number;
  trialDone?: number | null;
  bestScore?: number | null;
  scoreHistory?: number[];
  /** Cabecera más corta para columnas Lab. */
  compact?: boolean;
  /** Motor / familia para copy vivo (optuna, h0…). */
  engineHint?: string | null;
  className?: string;
};

const ACTIVITY_STEPS: Record<'pending' | 'busy', string[]> = {
  pending: [
    'Job en cola del worker…',
    'Esperando hueco en el laboratorio…',
    'Preparando espacio de búsqueda…',
  ],
  busy: [
    'Explorando combinaciones de parámetros…',
    'Evaluando score vs ancla…',
    'Comprobando tramo hold-out / OOS…',
    'Descartando candidatos flojos…',
    'Afinando el Mejor del lote…',
  ],
};

function phaseLabel(phase: OptimizeProgressPhase): string {
  switch (phase) {
    case 'pending':
      return 'En cola';
    case 'processing':
    case 'running':
      return 'Analizando';
    case 'completed':
      return 'Listo';
    case 'failed':
      return 'Falló';
    default:
      return 'Lab';
  }
}

function useRotatingStep(
  active: boolean,
  steps: string[],
  intervalMs = 2200,
): string {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    if (!active || steps.length === 0) return;
    setIdx(0);
    const id = window.setInterval(() => {
      setIdx((i) => (i + 1) % steps.length);
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [active, steps, intervalMs]);
  return steps[idx] ?? steps[0] ?? '';
}

/** Attractive progress strip: bar + soft sparkline while an optimize job runs. */
export function BacktestOptimizeProgress({
  phase,
  trialTotal,
  trialDone = null,
  bestScore = null,
  scoreHistory = [],
  compact = false,
  engineHint = null,
  className,
}: Props) {
  const busy = phase === 'processing' || phase === 'running';
  const waiting = phase === 'pending';
  const live = busy || waiting;
  const steps = waiting ? ACTIVITY_STEPS.pending : ACTIVITY_STEPS.busy;
  const activity = useRotatingStep(live, steps);

  const knownDone = trialDone != null && trialDone >= 0;
  const pct =
    phase === 'completed'
      ? 100
      : phase === 'failed'
        ? 0
        : phase === 'pending'
          ? 8
          : knownDone && trialTotal > 0
            ? Math.min(96, Math.round((trialDone / trialTotal) * 100))
            : null;

  const history =
    scoreHistory.length > 0
      ? scoreHistory
      : [0.35, 0.42, 0.38, 0.55, 0.48, 0.62, 0.58, 0.7, 0.66, 0.78];

  const min = Math.min(...history);
  const max = Math.max(...history);
  const span = Math.max(1e-6, max - min);
  const points = history
    .map((value, index) => {
      const x = (index / Math.max(1, history.length - 1)) * 100;
      const y = 100 - ((value - min) / span) * 78 - 8;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border border-sky-500/35 bg-gradient-to-br from-sky-500/15 via-card/90 to-emerald-500/10 shadow-sm',
        live && 'ring-1 ring-sky-400/30',
        compact ? 'p-2.5' : 'p-3',
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy={live}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p
          className={cn(
            'flex items-center gap-1.5 font-semibold uppercase tracking-[0.12em] text-sky-200',
            compact ? 'text-[10px]' : 'text-xs',
          )}
        >
          {live && <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-300" aria-hidden />}
          {phaseLabel(phase)}
          {engineHint ? (
            <span className="normal-case tracking-normal text-sky-200/70">· {engineHint}</span>
          ) : null}
        </p>
        <p className={cn('tabular-nums text-muted-foreground', compact ? 'text-[10px]' : 'text-[11px]')}>
          {knownDone
            ? `${trialDone} / ${trialTotal} trials`
            : phase === 'pending'
              ? `Cola · ~${trialTotal} trials`
              : `~${trialTotal} trials`}
          {bestScore != null && Number.isFinite(bestScore) && (
            <span className="ml-2 text-emerald-300">mejor {bestScore.toFixed(2)}</span>
          )}
          {pct != null && phase !== 'failed' && (
            <span className="ml-2 text-sky-300">{pct}%</span>
          )}
        </p>
      </div>

      {live && (
        <p
          key={activity}
          className={cn(
            'mt-1.5 text-foreground/90 transition-opacity duration-300',
            compact ? 'text-[11px] leading-snug' : 'text-xs',
          )}
        >
          {activity}
        </p>
      )}

      <div className={cn('relative overflow-hidden rounded-full bg-muted/60', compact ? 'mt-2 h-1.5' : 'mt-2 h-2')}>
        {pct != null ? (
          <div
            className="h-full rounded-full bg-gradient-to-r from-sky-400 to-emerald-400 transition-[width] duration-500"
            style={{ width: `${pct}%` }}
          />
        ) : (
          <div className="absolute inset-y-0 w-1/3 animate-[optimize-shimmer_1.4s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-transparent via-sky-400/90 to-transparent" />
        )}
      </div>

      {!compact && (
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="mt-3 h-16 w-full overflow-visible"
          aria-hidden
        >
          <defs>
            <linearGradient id="opt-progress-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgb(56 189 248)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="rgb(52 211 153)" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <polyline
            fill="none"
            stroke="rgba(56,189,248,0.85)"
            strokeWidth="2"
            points={points}
            vectorEffect="non-scaling-stroke"
          />
          <polygon fill="url(#opt-progress-fill)" points={`0,100 ${points} 100,100`} />
        </svg>
      )}

      <style>{`
        @keyframes optimize-shimmer {
          0% { transform: translateX(-120%); }
          100% { transform: translateX(320%); }
        }
      `}</style>
    </div>
  );
}
