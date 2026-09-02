import { describe, expect, it } from "vitest";
import {
  buildInvestmentPositionAggregate,
  buildPositionRouteLevels,
} from "./investment-position-aggregate.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";

function study(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    sessionId: "s1",
    decisionId: "D1",
    instrumentId: "i1",
    symbol: "AAPL",
    studiedAt: "2026-08-26T10:00:00Z",
    status: "active",
    hasOperationalPlan: true,
    entry: 180,
    stop: 170,
    target1: 198,
    target2: 210,
    expectedRR: 2,
    riskAmount: 1000,
    tradePlanStatus: "TRIGGERED",
    invalidation: [],
    ...overrides,
  } as DecisionJournalStudyViewV1;
}

describe("investment-position-aggregate", () => {
  it("builds aggregate with next action and entry from avgCost", () => {
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 182,
        lastPrice: 194,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "D1",
          currentStop: 178,
          target1: 198,
          target2: 210,
          unrealizedR: 1.2,
          exitPlan: { suggestedAction: "hold" },
        },
      },
      study: study(),
      originStudy: study(),
    });
    expect(agg.entry).toBe(182);
    expect(agg.originDecisionId).toBe("D1");
    expect(agg.lineage.packageAvailable).toBe(true);
    expect(agg.thesisSnapshot?.entry).toBe(180);
    expect(agg.nextAction.kind).toBe("review_proposal");
    expect(agg.risk.openRiskR).not.toBeNull();
  });

  it("buildPositionRouteLevels includes PRECIO and distances", () => {
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 185,
        lastPrice: 194,
        operational: {
          direction: "long",
          tradePlanId: "D1",
          currentStop: 178,
          target1: 198,
          target2: 210,
        },
      },
      study: study(),
      originStudy: study(),
    });
    const levels = buildPositionRouteLevels(agg);
    expect(levels.some((l) => l.label === "PRECIO")).toBe(true);
    expect(levels.some((l) => l.label === "ENTRADA")).toBe(true);
    expect(agg.thesisSnapshot?.direction).toBe("long");
  });

  it("mutated study does not overwrite original plan", () => {
    const day3Study = {
      ...study({ decisionId: "D1" }),
      entry: 103,
      stop: 98,
      target1: 112,
    };
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 100,
        lastPrice: 104,
        operational: {
          direction: "long",
          tradePlanId: "D1",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 99,
          target1: 110,
          target2: 120,
        },
      },
      study: day3Study,
      originStudy: day3Study,
    });
    expect(agg.originalPlanAvailable).toBe(true);
    expect(agg.originalPlan?.entry).toBe(100);
    expect(agg.originalPlan?.stop).toBe(95);
    expect(agg.currentPlan.stop).toBe(99);
    expect(agg.thesisSnapshot?.entry).toBe(103);
  });

  it("missing initialStop does not silently copy current study into original", () => {
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 182,
        lastPrice: 194,
        operational: {
          direction: "long",
          tradePlanId: "D1",
          currentStop: 178,
        },
      },
      study: study(),
      originStudy: study(),
    });
    expect(agg.originalPlanAvailable).toBe(false);
    expect(agg.originalPlan).toBeNull();
    expect(agg.tradePlanSnapshot.plannedEntry).toBeNull();
  });

  it("wires originDecisionId from operational.tradePlanId", () => {
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 182,
        operational: { tradePlanId: "D1", direction: "long" },
      },
    });
    expect(agg.originDecisionId).toBe("D1");
    expect(agg.lineage.orphanReason).toBe("session_not_found");
    expect(agg.thesisSnapshot).toBeNull();
  });

  it("does not adopt other-decision study as thesisSnapshot (orphan)", () => {
    const other = study({ decisionId: "D-OTHER", entry: 999 });
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 182,
        lastPrice: 190,
        operational: {
          tradePlanId: "D1",
          direction: "long",
          currentStop: 178,
        },
      },
      study: other,
      originStudy: other,
    });
    expect(agg.originDecisionId).toBe("D1");
    expect(agg.lineage.packageAvailable).toBe(false);
    expect(agg.thesisSnapshot).toBeNull();
    expect(agg.lineage.orphanReason).toBe("package_missing");
  });

  it("uses matching originStudy for thesis while evolution study drives targets", () => {
    const origin = study({ decisionId: "D1", entry: 180, riskAmount: 1000 });
    const evolution = study({
      decisionId: "D-LATER",
      entry: 190,
      target1: 220,
      target2: 240,
    });
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 182,
        lastPrice: 194,
        operational: {
          tradePlanId: "D1",
          direction: "long",
          currentStop: 178,
        },
      },
      study: evolution,
      originStudy: origin,
    });
    expect(agg.lineage.packageAvailable).toBe(true);
    expect(agg.thesisSnapshot?.entry).toBe(180);
    expect(agg.currentPlan.target1).toBe(220);
  });

  it("uses operational.originThesis snapshot when studies disagree", () => {
    const wrong = study({ decisionId: "D-LATER", entry: 999 });
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 182,
        lastPrice: 194,
        operational: {
          tradePlanId: "D1",
          direction: "long",
          currentStop: 178,
          originThesis: {
            decisionId: "D1",
            instrumentId: "i1",
            entry: 180,
            stop: 170,
            riskAmount: 1000,
            strength: 7,
            hasOperationalPlan: true,
            direction: "long",
          },
        },
      },
      study: wrong,
    });
    expect(agg.lineage.packageAvailable).toBe(true);
    expect(agg.thesisSnapshot?.entry).toBe(180);
    expect(agg.thesisSnapshot?.strength).toBe(7);
  });

  it("§A.8 full_exit + protectionDiscrepancy → exit (inherits mapMesaNextAction)", () => {
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 100,
        lastPrice: 94,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "D1",
          currentStop: null,
          exitPlan: { suggestedAction: "full_exit" },
        },
      },
      protectPlan: {
        status: "protect_hint",
        target1: null,
        suggestedProtectStop: 100,
        rMultiple: 1,
        why: ["mfe_ge_1r"],
      },
    });
    expect(agg.currentState.protectionDiscrepancy).toBe(true);
    expect(agg.currentState.exitSuggestedAction).toBe("full_exit");
    expect(agg.nextAction.kind).toBe("exit");
    expect(agg.nextAction.label).toBe("Salir");
  });

  it("§A.8 reduce + protectionDiscrepancy → reduce", () => {
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 100,
        lastPrice: 110,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "D1",
          currentStop: null,
          exitPlan: { suggestedAction: "reduce" },
        },
      },
      protectPlan: {
        status: "protect_hint",
        target1: null,
        suggestedProtectStop: 100,
        rMultiple: 1,
        why: ["mfe_ge_1r"],
      },
    });
    expect(agg.currentState.protectionDiscrepancy).toBe(true);
    expect(agg.nextAction.kind).toBe("reduce");
  });

  it("GP-V165-03: originDecisionId uses decisionId not tradePlanId", () => {
    const origin = study({ decisionId: "DEC-1" });
    const agg = buildInvestmentPositionAggregate({
      position: {
        symbol: "AAPL",
        instrumentId: "i1",
        quantity: 10,
        avgCost: 182,
        lastPrice: 194,
        operational: {
          status: "OPEN",
          direction: "long",
          decisionId: "DEC-1",
          tradePlanId: "TP-1",
          currentStop: 178,
          target1: 198,
          target2: 210,
          unrealizedR: 1.2,
          exitPlan: { suggestedAction: "hold" },
        },
      },
      study: origin,
      originStudy: origin,
    });
    expect(agg.originDecisionId).toBe("DEC-1");
    expect(agg.originDecisionId).not.toBe("TP-1");
    expect(agg.lineage.originDecisionId).toBe("DEC-1");
    expect(agg.lineage.thesisId).toBe("DEC-1");
    expect(agg.lineage.packageAvailable).toBe(true);
  });
});
