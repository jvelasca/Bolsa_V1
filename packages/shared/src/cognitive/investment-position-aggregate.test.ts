import { describe, expect, it } from "vitest";
import {
  buildInvestmentPositionAggregate,
  buildPositionRouteLevels,
} from "./investment-position-aggregate.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";

function study(): DecisionJournalStudyViewV1 {
  return {
    sessionId: "s1",
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
          currentStop: 178,
          target1: 198,
          target2: 210,
          unrealizedR: 1.2,
          exitPlan: { suggestedAction: "hold" },
        },
      },
      study: study(),
    });
    expect(agg.entry).toBe(182);
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
          currentStop: 178,
          target1: 198,
          target2: 210,
        },
      },
      study: study(),
    });
    const levels = buildPositionRouteLevels(agg);
    expect(levels.some((l) => l.label === "PRECIO")).toBe(true);
    expect(levels.some((l) => l.label === "ENTRADA")).toBe(true);
    expect(agg.thesisSnapshot?.direction).toBe("long");
  });

  it("mutated study does not overwrite original plan", () => {
    const day3Study = {
      ...study(),
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
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 99,
          target1: 110,
          target2: 120,
        },
      },
      study: day3Study,
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
          currentStop: 178,
        },
      },
      study: study(),
    });
    expect(agg.originalPlanAvailable).toBe(false);
    expect(agg.originalPlan).toBeNull();
    expect(agg.tradePlanSnapshot.plannedEntry).toBeNull();
  });
});
