import { describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import { computeOperationalPriority } from "./operational-priority.js";
import {
  projectBestNextR,
  projectOpportunityEvidence,
  qualityScoreFromOpportunityEvidence,
  type OpportunityEvidenceV1,
} from "./opportunity-evidence.js";

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
    initialRiskR: 1,
    invalidation: [],
    ...partial,
  } as DecisionJournalStudyViewV1;
}

function row(partial: Partial<MesaCandidateRowV1> = {}): MesaCandidateRowV1 {
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

function assertNoBuyFields(evidence: OpportunityEvidenceV1) {
  const keys = Object.keys(evidence);
  expect(keys).not.toContain("action");
  expect(keys).not.toContain("buy");
  expect(keys).not.toContain("permission");
  expect(keys).not.toContain("operable");
  expect(keys).not.toContain("verdict");
  expect(evidence.provisional).toBe(true);
}

describe("opportunity-evidence", () => {
  it("evidence ≠ BUY — provisional Quality pura without action/permission", () => {
    const evidence = projectOpportunityEvidence(row());
    assertNoBuyFields(evidence);
    expect(evidence.symbol).toBe("NVDA");
    expect(evidence.strength).toBe(9.6);
    expect(evidence.expectedRR).toBe(2.5);
    expect(evidence.qualityValue).toBeGreaterThan(0);
    expect(evidence.factors.some((f) => f.includes("Strength"))).toBe(true);
    expect(evidence.factors.some((f) => f.includes("R/R"))).toBe(true);
    // Operability signals must not appear as Quality factors
    expect(
      evidence.factors.some((f) => /trigger|plan operativo/i.test(f)),
    ).toBe(false);
  });

  it("high Quality + low Suitability still NO_OPERAR via priority helpers", () => {
    const candidate = row({ symbol: "NVDA" });
    const evidence = projectOpportunityEvidence(candidate);
    expect(evidence.qualityValue).toBeGreaterThanOrEqual(70);

    const priority = computeOperationalPriority(candidate, {
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
    expect(priority.quality.value).toBeGreaterThan(70);
    expect(priority.suitability.value).toBeLessThan(50);
    expect(priority.verdict).toBe("NO_OPERAR");
  });

  it("blocked Operability does not lower Opportunity", () => {
    const strong = {
      strength: 9,
      expectedRR: 3,
      hasOperationalPlan: true,
    };
    const triggered = projectOpportunityEvidence(
      row({
        symbol: "AAA",
        status: "TRIGGERED",
        study: study({ ...strong, tradePlanStatus: "TRIGGERED" }),
      }),
    );
    const blocked = projectOpportunityEvidence(
      row({
        symbol: "AAA",
        status: "BLOCKED",
        gate: "VETO",
        study: study({
          ...strong,
          hasOperationalPlan: false,
          tradePlanStatus: "BLOCKED",
        }),
      }),
    );

    expect(triggered.qualityValue).toBe(blocked.qualityValue);
    expect(triggered.strength).toBe(blocked.strength);
    expect(triggered.expectedRR).toBe(blocked.expectedRR);
    expect(triggered.label).toBe(blocked.label);

    const priorityBlocked = computeOperationalPriority(
      row({
        symbol: "AAA",
        status: "BLOCKED",
        gate: "VETO",
        study: study({
          ...strong,
          hasOperationalPlan: false,
          tradePlanStatus: "BLOCKED",
        }),
      }),
      { entriesBlocked: true },
    );
    expect(priorityBlocked.operability.operable).toBe(false);
    expect(priorityBlocked.verdict).toBe("NO_OPERAR");
  });

  it("best-next-R does not imply operable", () => {
    const projection = projectBestNextR(
      [
        row({
          symbol: "LOW",
          status: "TRIGGERED",
          study: study({
            symbol: "LOW",
            strength: 5,
            expectedRR: 1.2,
            initialRiskR: 1,
            hasOperationalPlan: true,
          }),
        }),
        row({
          symbol: "BEST",
          status: "BLOCKED",
          gate: "VETO",
          study: study({
            symbol: "BEST",
            strength: 8,
            expectedRR: 3,
            initialRiskR: 1.5,
            hasOperationalPlan: false,
            tradePlanStatus: "BLOCKED",
          }),
        }),
      ],
      {
        portfolioRisk: {
          portfolioPnLR: 0,
          portfolioOpenRiskR: 2,
          portfolioStressRiskR: null,
          portfolioRiskLimitR: 5,
        },
      },
    );

    expect(projection.provisional).toBe(true);
    expect(projection.impliesOperable).toBe(false);
    expect(projection.bestSymbol).toBe("BEST");
    expect(projection.ordered[0]?.symbol).toBe("BEST");
    expect(projection.ordered[0]?.expectedRewardR).toBe(4.5);

    const bestPriority = computeOperationalPriority(
      row({
        symbol: "BEST",
        status: "BLOCKED",
        gate: "VETO",
        study: study({
          symbol: "BEST",
          strength: 8,
          expectedRR: 3,
          initialRiskR: 1.5,
          hasOperationalPlan: false,
          tradePlanStatus: "BLOCKED",
        }),
      }),
      { entriesBlocked: false },
    );
    expect(bestPriority.operability.operable).toBe(false);
    expect(bestPriority.verdict).not.toBe("OPERABLE");
  });

  it("qualityScoreFromOpportunityEvidence is a thin adapter (no weights change)", () => {
    const evidence = projectOpportunityEvidence(row());
    const q = qualityScoreFromOpportunityEvidence(evidence);
    expect(q.value).toBe(evidence.qualityValue);
    expect(q.label).toBe(evidence.label);
    expect(q.factors).toEqual(evidence.factors);
  });
});
