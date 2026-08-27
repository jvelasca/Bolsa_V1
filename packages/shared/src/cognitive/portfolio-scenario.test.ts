import { describe, expect, it } from "vitest";
import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import { buildPortfolioScenario } from "./portfolio-scenario.js";

function candidate(
  partial: Partial<MesaCandidateRowV1> = {},
): MesaCandidateRowV1 {
  return {
    symbol: "NVDA",
    status: "TRIGGERED",
    statusLabel: "Listo",
    gate: "PASS",
    instrumentId: "i1",
    study: {
      sessionId: "s1",
      instrumentId: "i1",
      symbol: "NVDA",
      studiedAt: "2026-08-26T10:00:00Z",
      status: "active",
      hasOperationalPlan: true,
      entry: 100,
      stop: 95,
      riskAmount: 500,
      quantity: 100,
      initialRiskR: 1,
      invalidation: [],
    } as MesaCandidateRowV1["study"],
    ...partial,
  };
}

describe("buildPortfolioScenario", () => {
  it("COMPATIBLE when within risk limit", () => {
    const s = buildPortfolioScenario({
      candidate: candidate(),
      positions: [
        {
          avgCost: 50,
          quantity: 100,
          marketValue: 30_000,
          operational: { currentStop: 48, direction: "long" },
          study: { stop: 48, riskAmount: 200 },
        },
      ],
      equity: 100_000,
      cash: 60_000,
      riskTolerance: "moderate",
    });
    expect(s.verdict).toBe("COMPATIBLE");
    expect(s.riskLimitR).toBe(5);
  });

  it("NO_RECOMENDADA when projected open risk exceeds limit", () => {
    const s = buildPortfolioScenario({
      candidate: candidate(),
      positions: [
        {
          avgCost: 100,
          quantity: 100,
          marketValue: 50_000,
          operational: { currentStop: 90, direction: "long" },
          study: { stop: 90, riskAmount: 500 },
        },
        {
          avgCost: 80,
          quantity: 100,
          marketValue: 40_000,
          operational: { currentStop: 75, direction: "long" },
          study: { stop: 75, riskAmount: 500 },
        },
        {
          avgCost: 70,
          quantity: 100,
          marketValue: 30_000,
          operational: { currentStop: 65, direction: "long" },
          study: { stop: 65, riskAmount: 500 },
        },
      ],
      equity: 100_000,
      cash: 10_000,
      riskTolerance: "low",
    });
    expect(s.verdict).toBe("NO_RECOMENDADA");
  });

  it("NO_RECOMENDADA on sector concentration", () => {
    const s = buildPortfolioScenario({
      candidate: candidate(),
      candidateSector: "Technology",
      maxSectorExposurePct: 40,
      positions: [
        {
          avgCost: 50,
          quantity: 100,
          marketValue: 45_000,
          sector: "Technology",
          operational: { currentStop: 48, direction: "long" },
          study: { stop: 48, riskAmount: 500 },
        },
      ],
      equity: 100_000,
      cash: 50_000,
      riskTolerance: "moderate",
    });
    expect(s.verdict).toBe("NO_RECOMENDADA");
    expect(s.warnings.some((w) => w.includes("Concentración"))).toBe(true);
  });

  it("uses explicit portfolioRiskLimitR from mandate snapshot", () => {
    const s = buildPortfolioScenario({
      candidate: candidate(),
      positions: [
        {
          avgCost: 50,
          quantity: 100,
          marketValue: 30_000,
          operational: { currentStop: 48, direction: "long" },
          study: { stop: 48, riskAmount: 200 },
        },
      ],
      equity: 100_000,
      cash: 60_000,
      portfolioRiskLimitR: 0.5,
    });
    expect(s.riskLimitR).toBe(0.5);
    expect(s.verdict).toBe("NO_RECOMENDADA");
  });

  it("uses TradePlan quantity for candidate R, not a 1R stub", () => {
    const s = buildPortfolioScenario({
      candidate: candidate({
        study: {
          sessionId: "s1",
          instrumentId: "i1",
          symbol: "NVDA",
          studiedAt: "2026-08-26T10:00:00Z",
          status: "active",
          hasOperationalPlan: true,
          entry: 100,
          stop: 95,
          riskAmount: 500,
          quantity: 50,
          invalidation: [],
        } as MesaCandidateRowV1["study"],
      }),
      positions: [
        {
          avgCost: 50,
          quantity: 100,
          marketValue: 30_000,
          operational: { currentStop: 48, direction: "long" },
          study: { stop: 48, riskAmount: 200 },
        },
      ],
      equity: 100_000,
      cash: 60_000,
      riskTolerance: "moderate",
    });
    expect(s.after.openRiskR).toBe(1.5);
    expect(s.verdict).toBe("COMPATIBLE");
  });

  it("does not invent notional when stop is missing", () => {
    const s = buildPortfolioScenario({
      candidate: candidate({
        study: {
          sessionId: "s1",
          instrumentId: "i1",
          symbol: "NVDA",
          studiedAt: "2026-08-26T10:00:00Z",
          status: "active",
          hasOperationalPlan: true,
          entry: 100,
          stop: null,
          riskAmount: 500,
          invalidation: [],
        } as MesaCandidateRowV1["study"],
      }),
      positions: [
        {
          avgCost: 50,
          quantity: 100,
          marketValue: 30_000,
          operational: { currentStop: 48, direction: "long" },
          study: { stop: 48, riskAmount: 200 },
        },
      ],
      equity: 100_000,
      cash: 60_000,
    });
    expect(s.verdict).toBe("INSUFFICIENT_DATA");
    expect(s.warnings.some((w) => w.includes("no se inventa notional"))).toBe(
      true,
    );
    expect(s.after.openRiskR).toBeNull();
  });

  it("warns when Unknown sector exposure is present", () => {
    const s = buildPortfolioScenario({
      candidate: candidate(),
      candidateSector: "Technology",
      positions: [
        {
          avgCost: 50,
          quantity: 100,
          marketValue: 40_000,
          sector: "Technology",
          operational: { currentStop: 48, direction: "long" },
          study: { stop: 48, riskAmount: 500 },
        },
        {
          avgCost: 80,
          quantity: 50,
          marketValue: 12_000,
          sector: null,
          operational: { currentStop: 75, direction: "long" },
          study: { stop: 75, riskAmount: 500 },
        },
      ],
      equity: 100_000,
      cash: 48_000,
      riskTolerance: "moderate",
    });
    expect(s.current.sectorExposurePct.Unknown).toBe(12);
    expect(
      s.warnings.some((w) => w.includes("Datos sectoriales incompletos")),
    ).toBe(true);
    expect(s.current.sectorConcentration).not.toBeNull();
  });
});
