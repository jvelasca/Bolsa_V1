/**
 * Portfolio Scenario — simulador read-only de cartera (V1.19).
 */

import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import {
  portfolioRiskLimitR,
  sumPortfolioOpenRiskR,
  type PortfolioPositionRiskInput,
} from "./portfolio-risk-metrics.js";

export type PortfolioScenarioVerdictV1 =
  | "COMPATIBLE"
  | "NO_RECOMENDADA"
  | "INSUFFICIENT_DATA";

export type PortfolioScenarioColumnV1 = {
  capital: number | null;
  investedPct: number | null;
  cashPct: number | null;
  openRiskR: number | null;
  sectorExposurePct: Record<string, number>;
  /** HHI sobre pesos sectoriales (no concentración por posición). */
  sectorConcentration: number | null;
  /** @deprecated Usar sectorConcentration. */
  concentration: number | null;
  mandateFit: "OK" | "WARN" | "VETO" | "—";
  portfolioFit: "OK" | "WARN" | "VETO" | "—";
};

export type PortfolioScenarioV1 = {
  symbol: string;
  current: PortfolioScenarioColumnV1;
  after: PortfolioScenarioColumnV1;
  warnings: string[];
  verdict: PortfolioScenarioVerdictV1;
  verdictReason: string | null;
  riskLimitR: number;
};

export type BuildPortfolioScenarioInput = {
  candidate: MesaCandidateRowV1;
  positions: ReadonlyArray<
    PortfolioPositionRiskInput & { symbol?: string; sector?: string | null }
  >;
  equity?: number | null;
  cash?: number | null;
  riskTolerance?: string | null;
  maxAcceptableLossPct?: number | null;
  maxSectorExposurePct?: number;
  candidateSector?: string | null;
  /** Límite de mandato ya resuelto (snapshot). Si falta, se deriva de riskTolerance. */
  portfolioRiskLimitR?: number | null;
};

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

function sectorExposure(
  positions: ReadonlyArray<{
    marketValue?: number | null;
    sector?: string | null;
  }>,
  equity: number,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const p of positions) {
    const mv = p.marketValue;
    if (mv == null || mv <= 0) continue;
    const sector = p.sector?.trim() || "Unknown";
    out[sector] = round1((out[sector] ?? 0) + (mv / equity) * 100);
  }
  return out;
}

function herfindahl(concentrations: number[]): number | null {
  if (concentrations.length === 0) return null;
  const sum = concentrations.reduce((s, c) => s + c * c, 0);
  return Math.round(sum * 100) / 100;
}

function finitePositive(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

function candidateRiskR(candidate: MesaCandidateRowV1): number | null {
  const study = candidate.study;
  if (!study) return null;
  if (finitePositive(study.initialRiskR)) {
    return Math.round(study.initialRiskR * 100) / 100;
  }
  const entry = study.entry;
  const stop = study.stop;
  const quantity = study.quantity;
  const riskAmount = study.riskAmount;
  if (
    finitePositive(entry) &&
    stop != null &&
    Number.isFinite(stop) &&
    finitePositive(quantity) &&
    finitePositive(riskAmount)
  ) {
    const dist = Math.abs(entry - stop);
    if (dist <= 0) return null;
    return Math.round(((dist * quantity) / riskAmount) * 100) / 100;
  }
  return null;
}

function candidateNotional(candidate: MesaCandidateRowV1): number | null {
  const study = candidate.study;
  if (!study) return null;
  if (finitePositive(study.positionValue)) return study.positionValue;
  const entry = study.entry;
  if (finitePositive(study.quantity) && finitePositive(entry)) {
    return study.quantity * entry;
  }
  const stop = study.stop;
  const riskAmount = study.riskAmount;
  if (finitePositive(entry) && stop != null && finitePositive(riskAmount)) {
    const dist = Math.abs(entry - stop);
    if (dist > 0) return (riskAmount / dist) * entry;
  }
  return null;
}

export function buildPortfolioScenario(
  input: BuildPortfolioScenarioInput,
): PortfolioScenarioV1 {
  const warnings: string[] = [];
  const equity = input.equity ?? null;
  const cash = input.cash ?? null;
  const riskLimitR =
    input.portfolioRiskLimitR ??
    portfolioRiskLimitR({
      riskTolerance: input.riskTolerance,
      maxAcceptableLossPct: input.maxAcceptableLossPct,
    });

  const summedOpenRiskR = sumPortfolioOpenRiskR(input.positions);
  /** Cartera vacía = 0R abierto (no null). Posiciones sin sizing → null (no inventar). */
  const currentOpenRiskR =
    summedOpenRiskR ?? (input.positions.length === 0 ? 0 : null);
  const addRiskR = candidateRiskR(input.candidate);
  const notional = candidateNotional(input.candidate);

  let currentInvestedPct: number | null = null;
  let currentCashPct: number | null = null;
  let afterInvestedPct: number | null = null;
  let afterCashPct: number | null = null;
  let currentSectors: Record<string, number> = {};
  let afterSectors: Record<string, number> = {};

  if (equity != null && equity > 0 && cash != null) {
    currentInvestedPct = round1(((equity - cash) / equity) * 100);
    currentCashPct = round1((cash / equity) * 100);
    currentSectors = sectorExposure(input.positions, equity);

    if (notional != null) {
      afterInvestedPct = round1(((equity - cash + notional) / equity) * 100);
      afterCashPct = round1(((cash - notional) / equity) * 100);
      const sector = input.candidateSector?.trim() || "Unknown";
      afterSectors = { ...currentSectors };
      afterSectors[sector] = round1(
        (afterSectors[sector] ?? 0) + (notional / equity) * 100,
      );
      if (afterInvestedPct > 100) {
        warnings.push("Exposición proyectada > 100%");
      }
    } else {
      afterInvestedPct = currentInvestedPct;
      afterCashPct = currentCashPct;
      afterSectors = currentSectors;
    }
  }

  const afterOpenRiskR =
    currentOpenRiskR != null && addRiskR != null
      ? Math.round((currentOpenRiskR + addRiskR) * 100) / 100
      : addRiskR;

  if (addRiskR == null || notional == null) {
    warnings.push("Sizing no disponible — no se inventa notional");
  }

  if (afterOpenRiskR != null && afterOpenRiskR > riskLimitR) {
    warnings.push(`Riesgo agregado elevado (>${riskLimitR}R límite mandato)`);
  }

  const maxSector = input.maxSectorExposurePct ?? 40;
  for (const [sector, pct] of Object.entries(afterSectors)) {
    if (pct > maxSector) {
      warnings.push(`Concentración sector ${sector}: ${pct}%`);
    }
  }

  const unknownPct =
    (afterSectors.Unknown ?? 0) || (currentSectors.Unknown ?? 0);
  if (unknownPct > 0) {
    warnings.push(`Datos sectoriales incompletos (${unknownPct}%)`);
  }

  const mandateFit: PortfolioScenarioColumnV1["mandateFit"] =
    input.candidate.gate === "VETO" ? "VETO" : "OK";
  const portfolioFit: PortfolioScenarioColumnV1["portfolioFit"] =
    input.candidate.gate === "VETO"
      ? "VETO"
      : warnings.some((w) => w.includes("Concentración"))
        ? "WARN"
        : "OK";

  let verdict: PortfolioScenarioVerdictV1 = "INSUFFICIENT_DATA";
  let verdictReason: string | null = null;

  const sizingMissing = addRiskR == null || notional == null;

  if (equity != null && currentOpenRiskR != null) {
    if (sizingMissing) {
      verdict = "INSUFFICIENT_DATA";
      verdictReason = "Sizing no disponible — no se inventa notional";
    } else if (
      mandateFit === "VETO" ||
      portfolioFit === "VETO" ||
      warnings.some((w) => w.includes("Concentración"))
    ) {
      verdict = "NO_RECOMENDADA";
      verdictReason =
        warnings.find((w) => w.includes("Concentración")) ??
        "No encaja con mandato/cartera";
    } else if (afterOpenRiskR != null && afterOpenRiskR > riskLimitR) {
      verdict = "NO_RECOMENDADA";
      verdictReason = `Riesgo abierto supera límite (${riskLimitR}R)`;
    } else {
      verdict = "COMPATIBLE";
      verdictReason = "Operación compatible con cartera actual";
    }
  } else if (sizingMissing) {
    verdict = "INSUFFICIENT_DATA";
    verdictReason = "Sizing no disponible — no se inventa notional";
  }

  const currentConc = herfindahl(Object.values(currentSectors));
  const afterConc = herfindahl(Object.values(afterSectors));

  return {
    symbol: input.candidate.symbol,
    current: {
      capital: equity,
      investedPct: currentInvestedPct,
      cashPct: currentCashPct,
      openRiskR: currentOpenRiskR,
      sectorExposurePct: currentSectors,
      sectorConcentration: currentConc,
      concentration: currentConc,
      mandateFit: "OK",
      portfolioFit: "OK",
    },
    after: {
      capital: equity,
      investedPct: afterInvestedPct,
      cashPct: afterCashPct,
      openRiskR: afterOpenRiskR,
      sectorExposurePct: afterSectors,
      sectorConcentration: afterConc,
      concentration: afterConc,
      mandateFit,
      portfolioFit,
    },
    warnings,
    verdict,
    verdictReason,
    riskLimitR,
  };
}

/** @deprecated Usar buildPortfolioScenario. Wrapper de compat. */
export function projectMesaWhatIf(input: {
  symbol: string;
  candidateRiskAmount?: number | null;
  candidateRiskR?: number | null;
  portfolioRiskR?: number | null;
  equity?: number | null;
  cash?: number | null;
  candidateNotional?: number | null;
  portfolioRiskLimitR?: number | null;
  riskTolerance?: string | null;
}): {
  symbol: string;
  currentRiskR: number | null;
  projectedRiskR: number | null;
  currentExposurePct: number | null;
  projectedExposurePct: number | null;
  riskDeltaR: number | null;
  warnings: string[];
  riskLimitR: number;
} {
  const warnings: string[] = [];
  const limit =
    input.portfolioRiskLimitR ??
    portfolioRiskLimitR({ riskTolerance: input.riskTolerance });
  const currentRiskR = input.portfolioRiskR ?? null;
  const addR = input.candidateRiskR ?? null;
  let projectedRiskR: number | null = null;
  if (currentRiskR != null && addR != null) {
    projectedRiskR = Math.round((currentRiskR + addR) * 100) / 100;
  } else if (addR != null) {
    projectedRiskR = addR;
  }

  let currentExposurePct: number | null = null;
  let projectedExposurePct: number | null = null;
  const equity = input.equity;
  const cash = input.cash;
  const notional = input.candidateNotional;
  if (equity != null && equity > 0 && cash != null) {
    currentExposurePct = Math.round(((equity - cash) / equity) * 1000) / 10;
    if (notional != null) {
      projectedExposurePct =
        Math.round(((equity - cash + notional) / equity) * 1000) / 10;
      if (projectedExposurePct > 100) {
        warnings.push("Exposición proyectada > 100%");
      }
    }
  }

  if (projectedRiskR != null && projectedRiskR > limit) {
    warnings.push(`Riesgo agregado elevado (>${limit}R)`);
  }

  return {
    symbol: input.symbol,
    currentRiskR,
    projectedRiskR,
    currentExposurePct,
    projectedExposurePct,
    riskDeltaR:
      currentRiskR != null && projectedRiskR != null
        ? Math.round((projectedRiskR - currentRiskR) * 100) / 100
        : addR,
    warnings,
    riskLimitR: limit,
  };
}
