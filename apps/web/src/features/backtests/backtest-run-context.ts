/**
 * Contexto de ejecución Backtests (periodo/costes/TF/DÍA D) — localStorage.
 * Debe sobrevivir reinicio: entra en la huella de frescura Lista AUTO.
 */

import type { ChartTimeframe } from "@bolsa/shared";

import { DEFAULT_BACKTEST_COSTS } from "@/features/backtests/lib/backtest-cost-defaults";

export const BACKTEST_RUN_CONTEXT_KEY = "bolsa-backtest-run-context-v1";

/**
 * Versión del contrato de costes guardado. ``1`` (implícita) usaba 0/0 bps heredado:
 * un contexto sin marca con 0/0 se migra a los defaults de campaña UNA vez, porque ese
 * 0 no fue una elección explícita sino el default anterior. Un 0 con marca ``2`` se
 * respeta como análisis de sensibilidad deliberado.
 */
const COSTS_VERSION = 2;

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
  costsVersion?: number;
};

export function defaultBacktestRunContext(): BacktestRunContext {
  return {
    periodPreset: "all",
    customDateFrom: "",
    customDateTo: "",
    diaD: "",
    initialCash: "10000",
    commissionBps: String(DEFAULT_BACKTEST_COSTS.commissionBps),
    slippageBps: String(DEFAULT_BACKTEST_COSTS.slippageBps),
    timeframe: "1d",
    costsVersion: COSTS_VERSION,
  };
}

export function loadBacktestRunContext(): BacktestRunContext {
  const fallback = defaultBacktestRunContext();
  if (typeof localStorage === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(BACKTEST_RUN_CONTEXT_KEY);
    if (!raw) return fallback;
    const o = JSON.parse(raw) as Partial<BacktestRunContext>;
    const legacyCosts = o.costsVersion !== COSTS_VERSION;
    return {
      periodPreset:
        typeof o.periodPreset === "string" && o.periodPreset
          ? o.periodPreset
          : fallback.periodPreset,
      customDateFrom:
        typeof o.customDateFrom === "string" ? o.customDateFrom : "",
      customDateTo: typeof o.customDateTo === "string" ? o.customDateTo : "",
      diaD: typeof o.diaD === "string" ? o.diaD : "",
      initialCash:
        typeof o.initialCash === "string" && o.initialCash
          ? o.initialCash
          : fallback.initialCash,
      commissionBps:
        typeof o.commissionBps === "string" &&
        !(legacyCosts && o.commissionBps === "0")
          ? o.commissionBps
          : fallback.commissionBps,
      slippageBps:
        typeof o.slippageBps === "string" &&
        !(legacyCosts && o.slippageBps === "0")
          ? o.slippageBps
          : fallback.slippageBps,
      timeframe:
        typeof o.timeframe === "string" && o.timeframe
          ? o.timeframe
          : fallback.timeframe,
      costsVersion: COSTS_VERSION,
    };
  } catch {
    return fallback;
  }
}

export function saveBacktestRunContext(ctx: BacktestRunContext): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(
      BACKTEST_RUN_CONTEXT_KEY,
      JSON.stringify({ ...ctx, costsVersion: COSTS_VERSION }),
    );
  } catch {
    // ignore
  }
}
