import { Loader2, SlidersHorizontal } from 'lucide-react';
import { BacktestFutureStars } from '@/features/backtests/backtest-future-stars';
import type { OptimizeProgressPhase } from '@/features/backtests/backtest-optimize-progress';
import type { OptimizeSeed } from '@/features/backtests/backtest-optimize-seed';
import { OPTIMIZE_CRITERION_LABEL } from '@/features/backtests/backtest-optimize-space';
import {
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface OptimizeCardHeaderProps {
  compact: boolean;
  seed: OptimizeSeed | null;
  zoneRank?: 1 | 2 | 3;
  zoneStars?: number;
  zoneStarsCapped?: boolean;
  showLiveProgress: boolean;
  progressPhase: OptimizeProgressPhase | null;
  /** Pista de memoria Lab (CORE B v0.1). */
  adoptionHint: string | null;
  /** Hold-out OOS activo → se refleja en la descripción. */
  oosEnabled: boolean;
}

/**
 * Cabecera del panel de optimización (Diseño B, data-only): título, ranking de
 * zona, estrella Coach, badge de progreso y pista de memoria Lab. La lógica de
 * estado/progreso permanece en el orquestador `backtest-optimize-panel.tsx`.
 */
export function OptimizeCardHeader({
  compact,
  seed,
  zoneRank,
  zoneStars,
  zoneStarsCapped,
  showLiveProgress,
  progressPhase,
  adoptionHint,
  oosEnabled,
}: OptimizeCardHeaderProps) {
  return (
    <CardHeader className={cn('pb-2', compact && 'px-3 pt-3')}>
      <CardTitle
        className={cn(
          'flex flex-wrap items-center gap-2',
          compact ? 'text-sm' : 'text-base',
        )}
        title="Experimento de mejora: define el espacio de búsqueda, elige método(s) y compara contra tu operativa original."
      >
        {zoneRank != null ? (
          <span
            className={cn(
              'inline-flex h-6 min-w-6 items-center justify-center rounded-md px-1.5 text-xs font-semibold',
              zoneRank === 1
                ? 'bg-amber-500/20 text-amber-900 dark:text-amber-100'
                : 'bg-muted text-muted-foreground',
            )}
          >
            #{zoneRank}
          </span>
        ) : (
          <SlidersHorizontal className="h-4 w-4 text-primary" />
        )}
        <span className="min-w-0 flex-1 truncate">
          {compact ? (seed?.strategyLabel ?? 'Zona Lab') : 'Laboratorio de optimización'}
        </span>
        {showLiveProgress && (
          <span className="inline-flex items-center gap-1 rounded-md border border-sky-500/40 bg-sky-500/15 px-1.5 py-0.5 text-[10px] font-medium text-sky-100">
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
            {progressPhase === 'pending' ? 'En cola' : 'Analizando'}
          </span>
        )}
        {zoneStars != null && zoneStars > 0 ? (
          <BacktestFutureStars
            stars={zoneStars}
            capped={zoneStarsCapped}
            size="sm"
            titlePrefix={zoneRank != null ? `Coach #${zoneRank}` : undefined}
          />
        ) : null}
      </CardTitle>
      {!compact && (
        <CardDescription
          title={`${OPTIMIZE_CRITERION_LABEL}. Opcional: reserva un tramo final (OOS) para comprobar si el mejor candidato aguanta fuera de la ventana de búsqueda.`}
        >
          Elige qué variables probar y compara con tu prueba origen
          {oosEnabled ? ' · con comprobación al final' : ''}
        </CardDescription>
      )}
      {compact && seed && (
        <CardDescription className="text-[11px]">
          {showLiveProgress
            ? progressPhase === 'pending'
              ? 'Job en cola · el worker lo tomará en breve'
              : 'Optimizando parámetros · progreso en vivo arriba'
            : 'Inicial vs Mejor · config editable en esta zona · prioriza OOS / tramo reciente'}
        </CardDescription>
      )}
      {adoptionHint ? (
        <p
          className="mt-1 rounded-md border border-border/70 bg-muted/25 px-2 py-1 text-[10px] text-muted-foreground"
          title="Memoria Lab (CORE B v0.1). Guía el espacio (más ancho si meseta, más estrecho si pico); no cambia el ranking del Mejor."
        >
          {adoptionHint}
          {' · '}
          espacio guiado si misma familia.
        </p>
      ) : null}
    </CardHeader>
  );
}
