/**
 * Métricas de cartera — separación semántica P&L R vs Open Risk vs Stress.
 */

import type { RiskTolerance } from "./investor-profile.js";

export type PortfolioPositionRiskInput = {
  avgCost: number;
  quantity: number;
  lastPrice?: number | null;
  marketValue?: number | null;
  sector?: string | null;
  operational?: {
    direction?: string | null;
    currentStop?: number | null;
    unrealizedR?: number | null;
  } | null;
  study?: {
    stop?: number | null;
    riskAmount?: number | null;
    initialRiskR?: number | null;
  } | null;
};

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/** P&L no realizado agregado en R (suma unrealizedR). */
export function sumPortfolioUnrealizedR(
  positions: ReadonlyArray<{
    operational?: { unrealizedR?: number | null } | null;
  }>,
): number | null {
  let sum = 0;
  let any = false;
  for (const p of positions) {
    const r = p.operational?.unrealizedR;
    if (r != null && Number.isFinite(r)) {
      sum += r;
      any = true;
    }
  }
  return any ? round2(sum) : null;
}

/** R en riesgo si el stop actual se ejecuta (por posición). */
export function computePositionOpenRiskR(
  position: PortfolioPositionRiskInput,
): number | null {
  const entry = position.avgCost;
  const stop =
    position.operational?.currentStop ?? position.study?.stop ?? null;
  if (!finite(entry) || !finite(stop) || position.quantity <= 0) return null;

  const direction = (position.operational?.direction ?? "long").toLowerCase();
  const isShort = direction === "short";
  const riskPerUnit = isShort ? stop - entry : entry - stop;
  if (riskPerUnit <= 0) return 0;

  const lossAtStop = riskPerUnit * position.quantity;
  const riskAmount = position.study?.riskAmount;
  if (finite(riskAmount) && riskAmount > 0) {
    return round2(lossAtStop / riskAmount);
  }

  return 1;
}

/** Riesgo abierto agregado — suma de R si todos los stops se ejecutan. */
export function sumPortfolioOpenRiskR(
  positions: ReadonlyArray<PortfolioPositionRiskInput>,
): number | null {
  let sum = 0;
  let any = false;
  for (const p of positions) {
    const r = computePositionOpenRiskR(p);
    if (r != null) {
      sum += r;
      any = true;
    }
  }
  return any ? round2(sum) : null;
}

/** Stub — stress risk (correlación / escenario) pendiente de dominio completo. */
export function sumPortfolioStressRiskR(
  _positions: ReadonlyArray<PortfolioPositionRiskInput>,
): number | null {
  return null;
}

/** Límite de riesgo cartera en R — desde perfil/mandato, no hardcoded en UI. */
export function portfolioRiskLimitR(input?: {
  riskTolerance?: RiskTolerance | string | null;
  maxAcceptableLossPct?: number | null;
}): number {
  const tolerance = input?.riskTolerance;
  if (tolerance === "low") return 3;
  if (tolerance === "high") return 8;
  if (tolerance === "moderate") return 5;
  if (finite(input?.maxAcceptableLossPct) && input.maxAcceptableLossPct > 0) {
    return round2(Math.min(10, Math.max(2, input.maxAcceptableLossPct / 2)));
  }
  return 5;
}

export type PortfolioRiskSnapshotV1 = {
  portfolioPnLR: number | null;
  portfolioOpenRiskR: number | null;
  portfolioStressRiskR: number | null;
  portfolioRiskLimitR: number;
};

/** Peso de cada sector sobre equity (0–100). */
export function computeSectorExposurePct(
  positions: ReadonlyArray<{
    marketValue?: number | null;
    sector?: string | null;
  }>,
  equity: number | null,
): Record<string, number> {
  if (equity == null || equity <= 0) return {};
  const out: Record<string, number> = {};
  for (const p of positions) {
    const mv = p.marketValue;
    if (mv == null || mv <= 0) continue;
    const sector = p.sector?.trim() || "Unknown";
    out[sector] =
      Math.round(((out[sector] ?? 0) + (mv / equity) * 100) * 10) / 10;
  }
  return out;
}

export function buildPortfolioRiskSnapshot(input: {
  positions: ReadonlyArray<PortfolioPositionRiskInput>;
  riskTolerance?: RiskTolerance | string | null;
  maxAcceptableLossPct?: number | null;
}): PortfolioRiskSnapshotV1 {
  return {
    portfolioPnLR: sumPortfolioUnrealizedR(input.positions),
    portfolioOpenRiskR: sumPortfolioOpenRiskR(input.positions),
    portfolioStressRiskR: sumPortfolioStressRiskR(input.positions),
    portfolioRiskLimitR: portfolioRiskLimitR({
      riskTolerance: input.riskTolerance,
      maxAcceptableLossPct: input.maxAcceptableLossPct,
    }),
  };
}
