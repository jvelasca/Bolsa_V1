import { describe, expect, it } from "vitest";
import {
  buildOperationalPlanFromPosition,
  buildOperationalPlanFromStudy,
} from "./operational-plan-view.js";
import {
  NO_OPERATIONAL_PLAN_COPY,
  type DecisionJournalStudyViewV1,
} from "./decision-journal-study.js";
import type { PositionStateV1 } from "./position-state.js";

describe("operational-plan-view", () => {
  it("study without plan → empty copy", () => {
    const plan = buildOperationalPlanFromStudy({
      hasOperationalPlan: false,
      symbol: "SAN",
    } as DecisionJournalStudyViewV1);
    expect(plan.hasPlan).toBe(false);
    expect(plan.emptyCopy).toBe(NO_OPERATIONAL_PLAN_COPY);
  });

  it("study with geometry → prepared plan, single stop vigente", () => {
    const plan = buildOperationalPlanFromStudy({
      hasOperationalPlan: true,
      tradePlanStatus: "ARMED",
      entry: 100,
      stop: 94,
      target1: 112,
      target2: 124,
      expectedRR: 2,
      initialRiskR: 1,
      symbol: "NVDA",
    } as DecisionJournalStudyViewV1);
    expect(plan.hasPlan).toBe(true);
    expect(plan.phase).toBe("prepared");
    expect(plan.stopVigente).toBe(94);
    expect(plan.stopInicial).toBe(94);
    expect(plan.target1).toBe(112);
    expect(plan.target2).toBe(124);
  });

  it("position uses currentStop as stop vigente", () => {
    const ps = {
      status: "OPEN",
      direction: "long",
      actualEntry: 100,
      plannedEntry: 100,
      initialStop: 94,
      currentStop: 100,
      target1: 112,
      target2: 124,
      unrealizedR: 1.2,
      initialRisk: 6,
      mfeMae: { mfeR: 1.2, maeR: 0, source: "close_proxy" },
    } as PositionStateV1;
    const plan = buildOperationalPlanFromPosition({
      positionState: ps,
      markPrice: 118,
    });
    expect(plan.phase).toBe("position");
    expect(plan.stopVigente).toBe(100);
    expect(plan.stopInicial).toBe(94);
    expect(plan.target1Reached).toBe(true);
    expect(plan.target2Reached).toBe(false);
    expect(plan.trailingActive).toBe(false);
  });

  it("ratchet MFE ≥ 2R → trailingActive with stop hint (advisory)", () => {
    const ps = {
      status: "OPEN",
      direction: "long",
      actualEntry: 100,
      plannedEntry: 100,
      initialStop: 94,
      currentStop: 100,
      target1: 112,
      target2: 124,
      unrealizedR: 2.5,
      initialRisk: 6,
      mfeMae: { mfeR: 2.5, maeR: -0.2, source: "close_proxy" },
    } as PositionStateV1;
    const plan = buildOperationalPlanFromPosition({
      positionState: ps,
      markPrice: 115,
    });
    expect(plan.trailingActive).toBe(true);
    expect(plan.trailingPeakMfeR).toBe(2.5);
    expect(plan.trailingStopHint).not.toBeNull();
    expect(plan.trailingDistanceR).toBe(1);
    // Does not mutate stop vigente
    expect(plan.stopVigente).toBe(100);
  });
});
