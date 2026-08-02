/**
 * Panel reconciliación DÍA D (ADR-021) — F-D vs F-hoy + OOS.
 */

import { Link } from 'react-router-dom';
import {
  DIA_D_RECONCILIATION_LABELS,
  type DiaDReconciliationResult,
} from '@/features/backtests/dia-d-reconciliation';
import { instrumentTopBacktestsHref } from '@/features/backtests/instrument-strategy-top-panel';
import { cn } from '@/lib/utils';

export function DiaDReconciliationPanel({
  result,
  instrumentId,
  timeframe = '1d',
  className,
}: {
  result: DiaDReconciliationResult;
  instrumentId?: string | null;
  timeframe?: string;
  className?: string;
}) {
  const tone =
    result.code === 'SAME_CONFIRMED'
      ? 'border-emerald-600/40 bg-emerald-500/10'
      : result.code === 'SAME_FAILED' || result.code === 'DRIFT_WORSE'
        ? 'border-rose-600/40 bg-rose-500/10'
        : result.code === 'DRIFT_BETTER'
          ? 'border-amber-600/40 bg-amber-500/10'
          : 'border-border bg-muted/20';

  return (
    <div
      className={cn('space-y-1.5 rounded-md border px-2.5 py-2 text-[11px]', tone, className)}
      data-testid="dia-d-reconciliation"
      role="status"
    >
      <p className="font-semibold text-foreground">Reconciliación DÍA D</p>
      <p className="font-medium text-foreground">{DIA_D_RECONCILIATION_LABELS[result.code]}</p>
      <p className="text-muted-foreground leading-snug">{result.summary}</p>
      <ul className="text-muted-foreground">
        <li>
          F-D #1: <span className="text-foreground">{result.experimentLabel ?? '—'}</span>
          {result.oosReturnPct != null && Number.isFinite(result.oosReturnPct) ? (
            <span>
              {' '}
              · OOS{' '}
              <span className="text-foreground">
                {result.oosReturnPct > 0 ? '+' : ''}
                {result.oosReturnPct.toFixed(1)}%
              </span>
            </span>
          ) : null}
        </li>
        <li>
          F-hoy #1:{' '}
          <span className="text-foreground">{result.productionLabel ?? '— (sin Finalistas operativos)'}</span>
          {result.counterfactual?.status === 'ready' &&
          result.counterfactual.returnPct != null ? (
            <span>
              {' '}
              · OOS{' '}
              <span className="text-foreground">
                {result.counterfactual.returnPct > 0 ? '+' : ''}
                {result.counterfactual.returnPct.toFixed(1)}%
              </span>
              {result.counterfactual.tradeCount != null
                ? ` · ${result.counterfactual.tradeCount} ops`
                : ''}
              {result.counterfactual.deltaReturnPp != null ? (
                <span>
                  {' '}
                  · Δ{' '}
                  <span className="text-foreground">
                    {result.counterfactual.deltaReturnPp > 0 ? '+' : ''}
                    {result.counterfactual.deltaReturnPp.toFixed(1)} pp
                  </span>
                </span>
              ) : null}
            </span>
          ) : result.counterfactual?.status === 'skipped_same' ? (
            <span> · mismo run que F-D</span>
          ) : result.counterfactual?.status === 'pending' ? (
            <span> · contrafactual…</span>
          ) : result.counterfactual?.status === 'error' ? (
            <span className="text-rose-700 dark:text-rose-400">
              {' '}
              · contrafactual error
            </span>
          ) : null}
        </li>
      </ul>
      {(result.code === 'DRIFT_BETTER' || result.code === 'SAME_FAILED') && instrumentId ? (
        <Link
          to={instrumentTopBacktestsHref(instrumentId, timeframe)}
          className="inline-block font-medium text-primary hover:underline"
        >
          Revisar Finalistas operativos
        </Link>
      ) : null}
    </div>
  );
}
