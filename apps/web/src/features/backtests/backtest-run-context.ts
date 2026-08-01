/**
 * Contexto de ejecución Backtests (periodo/costes/TF/DÍA D) — localStorage.
 * Debe sobrevivir reinicio: entra en la huella de frescura Lista AUTO.
 */

import type { ChartTimeframe } from '@bolsa/shared';

export const BACKTEST_RUN_CONTEXT_KEY = 'bolsa-backtest-run-context-v1';

export type BacktestRunContext = {
  periodPreset: string;
  customDateFrom: string;
  customDateTo: string;
  /** Hoy simulado (ISO yyyy-mm-dd). Vacío = hoy real. */
  diaD: string;
  initialCash: string;
  commissionBps: string;
  slippageBps: string;
  timeframe: ChartTimeframe | string;
};

export function defaultBacktestRunContext(): BacktestRunContext {
  return {
    periodPreset: 'all',
    customDateFrom: '',
    customDateTo: '',
    diaD: '',
    initialCash: '10000',
    commissionBps: '0',
    slippageBps: '0',
    timeframe: '1d',
  };
}

export function loadBacktestRunContext(): BacktestRunContext {
  const fallback = defaultBacktestRunContext();
  if (typeof localStorage === 'undefined') return fallback;
  try {
    const raw = localStorage.getItem(BACKTEST_RUN_CONTEXT_KEY);
    if (!raw) return fallback;
    const o = JSON.parse(raw) as Partial<BacktestRunContext>;
    return {
      periodPreset:
        typeof o.periodPreset === 'string' && o.periodPreset
          ? o.periodPreset
          : fallback.periodPreset,
      customDateFrom: typeof o.customDateFrom === 'string' ? o.customDateFrom : '',
      customDateTo: typeof o.customDateTo === 'string' ? o.customDateTo : '',
      diaD: typeof o.diaD === 'string' ? o.diaD : '',
      initialCash:
        typeof o.initialCash === 'string' && o.initialCash
          ? o.initialCash
          : fallback.initialCash,
      commissionBps:
        typeof o.commissionBps === 'string' ? o.commissionBps : fallback.commissionBps,
      slippageBps:
        typeof o.slippageBps === 'string' ? o.slippageBps : fallback.slippageBps,
      timeframe:
        typeof o.timeframe === 'string' && o.timeframe
          ? o.timeframe
          : fallback.timeframe,
    };
  } catch {
    return fallback;
  }
}

export function saveBacktestRunContext(ctx: BacktestRunContext): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(BACKTEST_RUN_CONTEXT_KEY, JSON.stringify(ctx));
  } catch {
    // ignore
  }
}
