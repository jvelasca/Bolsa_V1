/**
 * Observed Profile helpers (RFC-008 D7).
 * Nunca reescribe Declared ni TradingPolicy.
 */

import type {
  DeclaredInvestorProfile,
  ObservedInvestorProfile,
  ProfileHorizon,
} from './investor-profile.js';

export interface BehaviorTradeSampleV1 {
  side: 'buy' | 'sell';
  holdingHours: number;
  riskPctOfEquity: number;
  followedStop: boolean;
  policyBreach?: boolean;
  impulsivityFlag?: boolean;
}

export interface PolicyBehaviorLimitsV1 {
  maxRiskPerTradePct: number;
  maxTradesPerWeek?: number | null;
  primaryHorizon?: ProfileHorizon;
}

function horizonMaxHours(horizon: ProfileHorizon): number {
  if (horizon === 'intraday') return 24;
  if (horizon === 'swing') return 24 * 21;
  if (horizon === 'position') return 24 * 90;
  return 24 * 365;
}

function horizonMinHours(horizon: ProfileHorizon): number {
  if (horizon === 'intraday') return 0;
  if (horizon === 'swing') return 4;
  if (horizon === 'position') return 24 * 5;
  return 24 * 20;
}

/**
 * Calcula Observed desde muestras. Solo observación + divergencias.
 */
export function observeInvestorProfile(
  declared: DeclaredInvestorProfile,
  samples: BehaviorTradeSampleV1[],
  policyLimits?: PolicyBehaviorLimitsV1,
  nowIso?: string,
): ObservedInvestorProfile {
  const ts = nowIso ?? new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const n = samples.length;
  if (n === 0) {
    return {
      sampleTradeCount: 0,
      divergesFromDeclared: false,
      divergesFromPolicy: false,
      lastObservedAt: ts,
      notes: ['Sin muestras de conducta aún'],
    };
  }

  const riskMap = { low: 0.5, moderate: 1.5, high: 3.5 } as const;
  const limits: PolicyBehaviorLimitsV1 = policyLimits ?? {
    maxRiskPerTradePct: declared.maxAcceptableLossPct ?? riskMap[declared.riskTolerance],
    primaryHorizon: declared.horizon,
  };

  const impulseHits = samples.filter((t) => t.impulsivityFlag).length;
  const stopOk = samples.filter((t) => t.followedStop).length;
  const breaches = samples.filter((t) => t.policyBreach).length;
  const riskOver = samples.filter(
    (t) => t.riskPctOfEquity > limits.maxRiskPerTradePct,
  ).length;

  const maxH = horizonMaxHours(declared.horizon);
  const minH = horizonMinHours(declared.horizon);
  const horizonMismatch = samples.filter(
    (t) => t.holdingHours > maxH * 1.5 || t.holdingHours < minH * 0.25,
  ).length;
  const shortChurn = samples.filter(
    (t) => t.holdingHours < Math.max(1, minH * 0.5),
  ).length;

  const impulsivity = Math.min(1, impulseHits / n);
  const overtrading = Math.min(1, (shortChurn + riskOver) / (2 * n));
  const discipline = Math.max(0, (stopOk / n) * (1 - breaches / n));

  const notes: string[] = [];
  let divergesFromDeclared = false;
  let divergesFromPolicy = false;

  const declaredCap =
    declared.maxAcceptableLossPct ?? riskMap[declared.riskTolerance];
  const avgRisk =
    samples.reduce((s, t) => s + t.riskPctOfEquity, 0) / n;
  if (avgRisk > declaredCap * 1.25) {
    divergesFromDeclared = true;
    notes.push(
      `Riesgo medio ${avgRisk.toFixed(2)}% > declarado≈${declaredCap.toFixed(2)}% (no se reescribe Declared)`,
    );
  }
  if (impulsivity >= 0.35) {
    divergesFromDeclared = true;
    notes.push(`Impulsividad observada ${impulsivity.toFixed(2)}`);
  }
  if (horizonMismatch / n >= 0.4) {
    divergesFromDeclared = true;
    notes.push('Holding diverge del horizonte declarado');
  }
  if (breaches > 0 || riskOver / n >= 0.25) {
    divergesFromPolicy = true;
    notes.push('Incumplimientos / riesgo sobre Policy (solo alerta)');
  }
  if (
    limits.maxTradesPerWeek != null &&
    n > limits.maxTradesPerWeek
  ) {
    divergesFromPolicy = true;
    notes.push('Posible overtrading vs límite semanal de Policy');
  }
  if (notes.length === 0) {
    notes.push('Conducta alineada con Declared/Policy (muestra actual)');
  }

  return {
    sampleTradeCount: n,
    impulsivityScore: Math.round(impulsivity * 1000) / 1000,
    overtradingScore: Math.round(overtrading * 1000) / 1000,
    disciplineScore: Math.round(discipline * 1000) / 1000,
    divergesFromDeclared,
    divergesFromPolicy,
    lastObservedAt: ts,
    notes,
  };
}
