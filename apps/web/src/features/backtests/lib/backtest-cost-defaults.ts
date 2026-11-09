/**
 * Costes de negociación por defecto del Lab (bps).
 *
 * Fuente única en el frontend: los MISMOS valores que ``CampaignCosts`` en
 * ``packages/py/application/.../campaign_manifest.py`` (10/5/2). Un backtest «a 0 bps»
 * era un techo optimista: el motor mide ~12,7 bps por lado en el replay. Un ``0``
 * explícito sigue siendo válido para análisis de sensibilidad; el silencio, no.
 */

export const DEFAULT_BACKTEST_COSTS = {
  commissionBps: 10,
  slippageBps: 5,
  spreadBps: 2,
} as const;

/** bps declarados en un campo de texto, o el default cuando el campo está vacío. */
export function resolveCostBpsText(value: string, fallback: number): number {
  const trimmed = value.trim();
  if (trimmed === "") return fallback;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

/**
 * bps declarados para un payload: ``undefined`` si el campo está vacío (deja que el
 * backend aplique su default de campaña), un número —incluido ``0``— si se declaró.
 */
export function optionalCostBps(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

/** Etiqueta corta usada por el resumen del wizard («10/5 bps»). */
export function formatCostBpsSummary(
  commissionBps: string,
  slippageBps: string,
): string {
  const commission = resolveCostBpsText(
    commissionBps,
    DEFAULT_BACKTEST_COSTS.commissionBps,
  );
  const slippage = resolveCostBpsText(
    slippageBps,
    DEFAULT_BACKTEST_COSTS.slippageBps,
  );
  return `${commission}/${slippage} bps`;
}
