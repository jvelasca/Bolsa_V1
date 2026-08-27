import { describe, expect, it } from "vitest";
import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import { computeOperationalPriority } from "./operational-priority.js";

function study(
  partial: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    sessionId: "s1",
    instrumentId: "i1",
    symbol: "NVDA",
    studiedAt: "2026-08-26T10:00:00Z",
    status: "active",
    strength: 9.6,
    hasOperationalPlan: true,
    expectedRR: 2.5,
    tradePlanStatus: "TRIGGERED",
    invalidation: [],
    ...partial,
  } as DecisionJournalStudyViewV1;
}

function row(partial: Partial<MesaCandidateRowV1>): MesaCandidateRowV1 {
  return {
    symbol: "NVDA",
    status: "TRIGGERED",
    statusLabel: "Listo",
    gate: "PASS",
    instrumentId: "i1",
    study: study(),
    ...partial,
  };
}

describe("operational-priority", () => {
  it("high quality + low suitability → NO_OPERAR", () => {
    const p = computeOperationalPriority(row({ symbol: "NVDA" }), {
      entriesBlocked: false,
      portfolioRisk: {
        portfolioPnLR: 2,
        portfolioOpenRiskR: 4.8,
        portfolioStressRiskR: null,
        portfolioRiskLimitR: 5,
      },
      candidateSector: "Technology",
      sectorExposurePct: { Technology: 42 },
      maxSectorExposurePct: 40,
    });
    expect(p.quality.value).toBeGreaterThan(70);
    expect(p.suitability.value).toBeLessThan(50);
    expect(p.verdict).toBe("NO_OPERAR");
  });

  it("TRIGGERED + fit → OPERABLE", () => {
    const p = computeOperationalPriority(row({ symbol: "AAPL" }), {
      entriesBlocked: false,
      portfolioRisk: {
        portfolioPnLR: 0.5,
        portfolioOpenRiskR: 1,
        portfolioStressRiskR: null,
        portfolioRiskLimitR: 5,
      },
    });
    expect(p.verdict).toBe("OPERABLE");
    expect(p.operability.operable).toBe(true);
  });

  it("resolves candidateSector from sectorByInstrumentId", () => {
    const p = computeOperationalPriority(
      row({ symbol: "NVDA", instrumentId: "inst-nvda" }),
      {
        entriesBlocked: false,
        sectorByInstrumentId: { "inst-nvda": "Technology" },
        sectorExposurePct: { Technology: 50 },
        maxSectorExposurePct: 40,
        portfolioRisk: {
          portfolioPnLR: 0,
          portfolioOpenRiskR: 1,
          portfolioStressRiskR: null,
          portfolioRiskLimitR: 5,
        },
      },
    );
    expect(p.suitability.value).toBeLessThan(50);
    expect(p.verdict).toBe("NO_OPERAR");
  });

  it("penalizes missing sector and Unknown portfolio exposure", () => {
    const withSector = computeOperationalPriority(row({ symbol: "AAA" }), {
      entriesBlocked: false,
      candidateSector: "Tech",
      sectorExposurePct: { Tech: 10 },
      maxSectorExposurePct: 40,
      portfolioRisk: {
        portfolioPnLR: 0,
        portfolioOpenRiskR: 1,
        portfolioStressRiskR: null,
        portfolioRiskLimitR: 5,
      },
    });
    const missing = computeOperationalPriority(row({ symbol: "BBB" }), {
      entriesBlocked: false,
      candidateSector: null,
      sectorExposurePct: { Unknown: 12 },
      maxSectorExposurePct: 40,
      portfolioRisk: {
        portfolioPnLR: 0,
        portfolioOpenRiskR: 1,
        portfolioStressRiskR: null,
        portfolioRiskLimitR: 5,
      },
    });
    expect(missing.suitability.value).toBeLessThan(
      withSector.suitability.value,
    );
    expect(
      missing.suitability.factors.some((f) => f.includes("desconocido")),
    ).toBe(true);
    expect(missing.suitability.factors.some((f) => f.includes("Unknown"))).toBe(
      true,
    );
  });
});
