import { describe, expect, it } from "vitest";
import { evaluatePolicyGate } from "@bolsa/shared";

/**
 * Tests de paridad TS↔Py del Policy Gate (RFC-008 D1).
 *
 * `packages/shared/src/cognitive/policy-gate.ts` reimplementa la misma política
 * hard que `bolsa_analytics/analytics/cognitive/policy_gate.py` (la versión de
 * servidor). Estos tests fijan el contrato TS (mismos nombres de regla,
 * PASSED/FAILED/SKIPPED y razones de veto) para detectar drift silencioso entre
 * ambos lados (hallazgo P2.6 de la auditoría consolidada).
 */
function buildPolicy(
  overrides: Partial<Parameters<typeof evaluatePolicyGate>[0]["policy"]> = {},
) {
  return {
    artifactType: "ART-TRADING-POLICY" as const,
    schemaVersion: "1.0.0" as const,
    policyId: "fixture-1",
    version: "0.1.0",
    templateId: "moderate" as const,
    name: "Fixture",
    universe: {
      allowedAssetClasses: ["equities"],
      minMarketCapUSD: 1_000_000,
      minAverageDailyVolumeUSD: 500_000,
      maxSpreadBps: 100,
      excludedSectors: [],
      excludedTickers: [],
      allowShorting: true,
      allowOtc: false,
      allowCrypto: false,
      allowCfds: false,
    },
    exposure: {
      maxLeverage: 1,
      maxOpenPositions: 10,
      maxPortfolioConcentrationPct: 20,
      maxSectorExposurePct: 30,
    },
    risk: {
      maxRiskPerTradePct: 2,
      hardDailyDrawdownLimitPct: 5,
      hardWeeklyDrawdownLimitPct: 10,
      hardMaxDrawdownLimitPct: 20,
      minRewardToRiskRatio: 1.5,
      stopLossRequired: true,
    },
    blackouts: {
      blockPreEarningsHours: 4,
      blockPostEarningsHours: 2,
      blockFedFomc: true,
      blockEcb: true,
      blockHighImpactMacro: true,
      blockedMacroEventTypes: [],
      blockMnaRumors: false,
    },
    horizon: {
      primaryTimeframe: "D1" as const,
      minHoldingPeriodMinutes: 60,
      maxHoldingPeriodDays: 30,
    },
    execution: {
      allowedOrderTypes: ["market", "limit"],
      defaultOrderType: "limit" as const,
    },
    evidence: {
      minimumRequiredCredibility: 70,
      minimumWalkForwardEfficiency: 0.5,
      maxMonteCarloPValue: 0.05,
      requireEdgeReportForAutoLive: true,
    },
    updatedAt: "2026-01-01T00:00:00Z",
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const passingInput = {
  policy: buildPolicy(),
  instrument: {
    symbol: "SAN",
    assetClass: "equities" as const,
    marketCapUSD: 50_000_000,
    averageDailyVolumeUSD: 20_000_000,
    sector: "banks",
    spreadBps: 20,
  },
  proposed: {
    riskPctOfAccount: 1,
    rewardToRiskRatio: 2,
    leverage: 1,
    hasStopLoss: true,
    openPositionsCount: 3,
    portfolioConcentrationPct: 10,
  },
};

describe("Policy Gate — paridad TS↔Py (policy-gate.ts)", () => {
  it("admite una oportunidad que cumple toda la política", () => {
    const r = evaluatePolicyGate(passingInput);
    expect(r.passed).toBe(true);
    expect(r.policyId).toBe("fixture-1");
    expect(r.vetoReasons).toEqual([]);
    // Sin cuenta abierta de circuit-breaker → drawdowns SKIPPED.
    const skipped = r.evaluatedRules
      .filter((x) => x.status === "SKIPPED")
      .map((x) => x.rule);
    expect(skipped).toContain("HardDailyDrawdown");
  });

  it("veto por ticker excluido", () => {
    const r = evaluatePolicyGate({
      ...passingInput,
      instrument: { ...passingInput.instrument, symbol: "RSK" },
      policy: buildPolicy({
        universe: { ...buildPolicy().universe, excludedTickers: ["RSK"] },
      }),
    });
    expect(r.passed).toBe(false);
    expect(
      r.evaluatedRules.find((x) => x.rule === "ExcludedTicker")?.status,
    ).toBe("FAILED");
    expect(r.vetoReasons.join().toLowerCase()).toContain("excluido");
  });

  it("veto por apalancamiento (MaxLeverage)", () => {
    const r = evaluatePolicyGate({
      ...passingInput,
      proposed: { ...passingInput.proposed, leverage: 3 },
    });
    expect(r.passed).toBe(false);
    expect(r.evaluatedRules.find((x) => x.rule === "MaxLeverage")?.status).toBe(
      "FAILED",
    );
  });

  it("veto por capitalización por debajo del mínimo (MinMarketCap)", () => {
    const r = evaluatePolicyGate({
      ...passingInput,
      instrument: { ...passingInput.instrument, marketCapUSD: 100_000 },
    });
    expect(r.passed).toBe(false);
    expect(
      r.evaluatedRules.find((x) => x.rule === "MinMarketCap")?.status,
    ).toBe("FAILED");
  });

  it("veto por stop loss obligatorio ausente (StopLossRequired)", () => {
    const r = evaluatePolicyGate({
      ...passingInput,
      proposed: { ...passingInput.proposed, hasStopLoss: false },
    });
    expect(r.passed).toBe(false);
    expect(
      r.evaluatedRules.find((x) => x.rule === "StopLossRequired")?.status,
    ).toBe("FAILED");
    expect(r.vetoReasons).toContain("Stop loss obligatorio");
  });

  it("veto por blackout pre-earnings", () => {
    const r = evaluatePolicyGate({
      ...passingInput,
      context: { hoursToEarnings: 1 },
    });
    expect(r.passed).toBe(false);
    expect(
      r.evaluatedRules.find((x) => x.rule === "PreEarningsBlackout")?.status,
    ).toBe("FAILED");
  });

  it("veto por drawdown diario (circuit breaker F4)", () => {
    const r = evaluatePolicyGate({
      ...passingInput,
      accountDrawdown: { dailyPct: 8 },
    });
    expect(r.passed).toBe(false);
    expect(
      r.evaluatedRules.find((x) => x.rule === "HardDailyDrawdown")?.status,
    ).toBe("FAILED");
  });

  it("los nombres de regla del paso limpie las reglas incondicionales (paridad policy_gate.py)", () => {
    // Reglas SIEMPRE evaluadas (call sites incondicionales) → deben estar presentes
    // en cualquier corrida, igual que en policy_gate.py del servidor.
    const alwaysEmitted = [
      "AssetClass",
      "MaxLeverage",
      "MaxOpenPositions",
      "MaxConcentration",
      "MaxRiskPerTrade",
      "MinRewardToRisk",
      "StopLossRequired",
      "HardDailyDrawdown",
      "HardWeeklyDrawdown",
      "HardMaxDrawdown",
    ];
    const r = evaluatePolicyGate(passingInput);
    const emitted = new Set(r.evaluatedRules.map((x) => x.rule));
    for (const name of alwaysEmitted) {
      expect(
        emitted.has(name),
        `falta la regla ${name} en el policy gate TS`,
      ).toBe(true);
    }
  });
});
