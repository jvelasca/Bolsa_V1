/**
 * Zona derecha de la barra Trading: hilos de la app (velas + backtesting + CORE-R).
 *
 * CORE-R v1.5: chip si hay cola abierta → Ayuda · Monitor (no auto-paper).
 * Importante: no filtrar arrays en el selector zustand (rompe Object.is → loop).
 */

import { FlaskConical, RefreshCw } from 'lucide-react';
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  formatCoreROpenSymbolsKey,
  formatCoreRStatusChip,
  formatCoreRStatusTitle,
  openHelpBacktesting,
} from '@/features/backtests/core-r-status';
import { TradingBackgroundStatus } from '@/features/trading/trading-background-status';
import { useCoreRReviewQueueStore } from '@/stores/core-r-review-queue-store';
import { useListAutoActivityStore } from '@/stores/list-auto-activity-store';
import { cn } from '@/lib/utils';

export function TradingAppThreads() {
  const listAutoSummary = useListAutoActivityStore((s) => s.summary);
  const listAutoActive = useListAutoActivityStore((s) => s.active);
  const listAutoPaused = useListAutoActivityStore((s) => s.paused);
  const listAutoDetail = useListAutoActivityStore((s) => s.detail);
  /** Primitivos estables — evita Maximum update depth con filter() en selector. */
  const coreROpenCount = useCoreRReviewQueueStore((s) => s.openCount());
  const coreRSymbolsKey = useCoreRReviewQueueStore((s) =>
    formatCoreROpenSymbolsKey(s.items),
  );
  const coreRChip = useMemo(
    () => formatCoreRStatusChip(coreROpenCount),
    [coreROpenCount],
  );
  const coreRTitle = useMemo(
    () =>
      formatCoreRStatusTitle(
        coreROpenCount,
        coreRSymbolsKey ? coreRSymbolsKey.split('\u0001') : [],
      ),
    [coreROpenCount, coreRSymbolsKey],
  );

  return (
    <div className="ml-auto flex min-w-0 shrink-0 items-center gap-1">
      <span className="hidden shrink-0 uppercase tracking-wide text-muted-foreground/60 sm:inline">
        Hilos
      </span>
      <TradingBackgroundStatus />
      {coreRChip ? (
        <button
          type="button"
          onClick={() => openHelpBacktesting({ panel: 'monitor' })}
          className="flex shrink-0 items-center gap-1 rounded px-1 py-0.5 font-medium text-amber-900 hover:bg-accent dark:text-amber-200"
          title={coreRTitle}
        >
          <RefreshCw className="h-3 w-3 shrink-0 opacity-80" aria-hidden />
          <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" aria-hidden />
          <span className="tabular-nums">{coreRChip}</span>
        </button>
      ) : null}
      {listAutoActive && listAutoSummary ? (
        <Link
          to="/backtests?tab=run&focus=list_auto"
          className={cn(
            'flex min-w-0 max-w-[min(16rem,36vw)] shrink items-center gap-1 truncate rounded px-1 py-0.5 font-medium text-foreground hover:bg-accent',
            listAutoPaused
              ? 'text-amber-800 dark:text-amber-200'
              : 'text-violet-800 dark:text-violet-200',
          )}
          title={
            listAutoDetail
              ? `${listAutoSummary}\n${listAutoDetail}\nClic → tablero Lista AUTO`
              : `${listAutoSummary}\nClic → tablero Lista AUTO`
          }
        >
          <FlaskConical className="h-3 w-3 shrink-0 opacity-80" aria-hidden />
          <span
            className={cn(
              'inline-block h-1.5 w-1.5 shrink-0 rounded-full',
              listAutoPaused ? 'bg-amber-500' : 'animate-pulse bg-violet-500',
            )}
            aria-hidden
          />
          <span className="truncate tabular-nums">{listAutoSummary}</span>
        </Link>
      ) : null}
    </div>
  );
}
