import { describe, expect, it } from "vitest";
import {
  buildOperationalPlanFromPosition,
  buildOperationalPlanFromStudy,
  isTrailingStopApplied,
  targetProgressHint,
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
    expect(plan.target1Touched).toBe(true);
    expect(plan.target1Managed).toBe(false);
    expect(plan.target2Reached).toBe(false);
    expect(plan.target2Touched).toBe(false);
    expect(plan.target2Managed).toBe(false);
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

  it("H2 — price at T1 without target1AchievedAt is touched, not managed", () => {
    const ps = {
      status: "OPEN",
      direction: "long",
      actualEntry: 100,
      plannedEntry: 100,
      initialStop: 94,
      currentStop: 94,
      target1: 112,
      target2: 124,
      unrealizedR: 2,
      initialRisk: 6,
    } as PositionStateV1;
    const plan = buildOperationalPlanFromPosition({
      positionState: ps,
      markPrice: 112,
    });
    expect(plan.target1Touched).toBe(true);
    expect(plan.target1Managed).toBe(false);
    expect(plan.target1Reached).toBe(true);
  });

  it("H2 — target1AchievedAt marks T1 managed even if price pulled back", () => {
    const ps = {
      status: "PARTIAL",
      direction: "long",
      actualEntry: 100,
      plannedEntry: 100,
      initialStop: 94,
      currentStop: 100,
      target1: 112,
      target2: 124,
      target1AchievedAt: "2026-08-27T10:00:00Z",
      unrealizedR: 0.5,
      initialRisk: 6,
    } as PositionStateV1;
    const plan = buildOperationalPlanFromPosition({
      positionState: ps,
      markPrice: 104,
    });
    expect(plan.target1Touched).toBe(false);
    expect(plan.target1Managed).toBe(true);
    expect(plan.target1Reached).toBe(true);
    expect(plan.target2Managed).toBe(false);
  });

  it("targetProgressHint distinguishes pending / touched / managed", () => {
    expect(targetProgressHint(false, false)).toBe("○ pendiente");
    expect(targetProgressHint(true, false)).toBe(
      "● alcanzado · ○ pendiente de gestión",
    );
    expect(targetProgressHint(true, true)).toBe("✓ gestionado");
    expect(targetProgressHint(false, true)).toBe("✓ gestionado");
  });

  it("H2 — target1AchievedAt on aggregate.targets (no positionState)", () => {
    const plan = buildOperationalPlanFromPosition({
      aggregate: {
        instrumentId: "nvda",
        symbol: "NVDA",
        entry: 100,
        currentPrice: 104,
        protection: {
          currentStop: 100,
          protectHint: false,
          discrepancy: false,
        },
        targets: {
          target1: 112,
          target2: 124,
          target1AchievedAt: "2026-08-27T10:00:00Z",
        },
        risk: { unrealizedR: 0.5, openRiskR: null },
        thesisSnapshot: { direction: "long" },
      } as never,
      markPrice: 104,
    });
    expect(plan.target1Managed).toBe(true);
    expect(plan.target1Touched).toBe(false);
  });

  it("stopInicial missing → null (no silent fallback to vigente)", () => {
    const ps = {
      status: "OPEN",
      direction: "long",
      actualEntry: 100,
      plannedEntry: 100,
      initialStop: null,
      currentStop: 108,
      target1: 112,
      target2: 124,
      unrealizedR: 1,
      initialRisk: 6,
    } as PositionStateV1;
    const plan = buildOperationalPlanFromPosition({
      positionState: ps,
      markPrice: 110,
    });
    expect(plan.stopVigente).toBe(108);
    expect(plan.stopInicial).toBeNull();
  });

  it("isTrailingStopApplied respects long/short", () => {
    expect(
      isTrailingStopApplied({
        direction: "long",
        stopVigente: 103,
        trailingStopHint: 101,
      }),
    ).toBe(true);
    expect(
      isTrailingStopApplied({
        direction: "short",
        stopVigente: 104,
        trailingStopHint: 106,
      }),
    ).toBe(true);
    expect(
      isTrailingStopApplied({
        direction: "short",
        stopVigente: 108,
        trailingStopHint: 106,
      }),
    ).toBe(false);
  });
});
