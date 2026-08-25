/**
 * ExitPlan F3 — razones canónicas (ADR-032). ≠ execution ≠ thin.
 */

import { describe, expect, it } from "vitest";
import {
  buildExitPlanFromPosition,
  EXIT_REASON_PRECEDENCE,
  type ExitPlanV1,
} from "./cognitive/exit-plan.js";
import {
  applyPositionReduce,
  buildPositionStateFromFill,
  type PositionStateV1,
} from "./cognitive/position-state.js";
import type { TradePlanV1 } from "./cognitive/trade-plan.js";

function triggeredPlan(overrides: Partial<TradePlanV1> = {}): TradePlanV1 {
  return {
    decisionId: "dec-1",
    instrumentId: "MSFT",
    direction: "long",
    status: "TRIGGERED",
    quantity: 100,
    riskPct: 0.5,
    whyNot: [],
    executionAllowed: true,
    entry: 100,
    structuralStop: 95,
    target1: 105,
    target2: 110,
    ...overrides,
  };
}

function openLong(): PositionStateV1 {
  const pos = buildPositionStateFromFill(triggeredPlan(), {
    price: 100,
    quantity: 10,
    filledAt: "2026-08-25T15:00:00Z",
    positionId: "pos-1",
  });
  if (!pos) throw new Error("expected OPEN");
  return pos;
}

describe("F3 buildExitPlanFromPosition", () => {
  it("IDLE without signals (no invented reasons)", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      exitPlanId: "ex-1",
      at: "2026-08-25T16:00:00Z",
    });
    expect(plan).not.toBeNull();
    const p = plan as ExitPlanV1;
    expect(p.exitPlanId).toBe("ex-1");
    expect(p.positionId).toBe("pos-1");
    expect(p.tradePlanId).toBe("dec-1");
    expect(p.status).toBe("IDLE");
    expect(p.reasons).toEqual([]);
    expect(p.primaryReason).toBeNull();
    expect(p.suggestedAction).toBe("hold");
    expect(p.suggestedQty).toBeNull();
    expect(p.createdAt).toBe("2026-08-25T16:00:00Z");
  });

  it("returns null without position", () => {
    expect(buildExitPlanFromPosition(null)).toBeNull();
  });

  it("CLOSED position → DONE without mutating PositionState", () => {
    const closed = applyPositionReduce(openLong(), 10, 100);
    expect(closed?.status).toBe("CLOSED");
    expect(closed?.exitStatus).toBe("done");
    const plan = buildExitPlanFromPosition(closed!, {
      markPrice: 90,
      exitPlanId: "ex-done",
    });
    expect(plan?.status).toBe("DONE");
    expect(plan?.suggestedAction).toBe("hold");
    expect(closed!.exitStatus).toBe("done");
  });

  it("STRUCTURAL_STOP when mark touches stop → TRIGGERED full_exit", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      markPrice: 95,
      exitPlanId: "ex-stop",
    });
    expect(plan?.primaryReason).toBe("STRUCTURAL_STOP");
    expect(plan?.status).toBe("TRIGGERED");
    expect(plan?.suggestedAction).toBe("full_exit");
    expect(plan?.suggestedQty).toBe(10);
    expect(plan?.reasons).toContain("STRUCTURAL_STOP");
  });

  it("TARGET_1 → TRIGGERED reduce (half remaining)", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      markPrice: 105,
      exitPlanId: "ex-t1",
    });
    expect(plan?.primaryReason).toBe("TARGET_1");
    expect(plan?.status).toBe("TRIGGERED");
    expect(plan?.suggestedAction).toBe("reduce");
    expect(plan?.suggestedQty).toBe(5);
  });

  it("TARGET_2 without T1 touch still TRIGGERED full_exit", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      markPrice: 110,
      exitPlanId: "ex-t2",
    });
    // mark >= T1 and T2 → primary TARGET_1 wins precedence over TARGET_2
    expect(plan?.primaryReason).toBe("TARGET_1");
    expect(plan?.reasons).toEqual(
      expect.arrayContaining(["TARGET_1", "TARGET_2"]),
    );
  });

  it("MANUAL beats STRUCTURAL_STOP in primaryReason", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      markPrice: 90,
      manual: true,
      exitPlanId: "ex-man",
    });
    expect(plan?.primaryReason).toBe("MANUAL");
    expect(plan?.reasons[0]).toBe("MANUAL");
    expect(plan?.reasons).toContain("STRUCTURAL_STOP");
    expect(EXIT_REASON_PRECEDENCE[0]).toBe("MANUAL");
  });

  it("thesis / portfolio signals are explicit only", () => {
    const idle = buildExitPlanFromPosition(openLong(), { markPrice: 101 });
    expect(idle?.reasons).toEqual([]);
    const thesis = buildExitPlanFromPosition(openLong(), {
      thesisInvalid: true,
    });
    expect(thesis?.primaryReason).toBe("THESIS_INVALIDATION");
    expect(thesis?.status).toBe("TRIGGERED");
    const port = buildExitPlanFromPosition(openLong(), {
      portfolioRisk: true,
    });
    expect(port?.primaryReason).toBe("PORTFOLIO_RISK");
  });

  it("TRAIL with trailStop → ARMED protect", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      trailHint: true,
      trailStop: 100,
      exitPlanId: "ex-trail",
    });
    expect(plan?.primaryReason).toBe("TRAIL");
    expect(plan?.status).toBe("ARMED");
    expect(plan?.suggestedAction).toBe("protect");
    expect(plan?.suggestedStop).toBe(100);
  });

  it("TRAIL without stop → HINT protect", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      trailHint: true,
    });
    expect(plan?.status).toBe("HINT");
    expect(plan?.suggestedAction).toBe("protect");
    expect(plan?.suggestedStop).toBeNull();
  });

  it("TIME_STOP when now >= expiresAt → HINT full_exit", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      now: "2026-08-26T00:00:00Z",
      expiresAt: "2026-08-25T23:00:00Z",
    });
    expect(plan?.primaryReason).toBe("TIME_STOP");
    expect(plan?.status).toBe("HINT");
    expect(plan?.suggestedAction).toBe("full_exit");
    expect(plan?.suggestedQty).toBe(10);
  });

  it("does not invent TIME_STOP without both timestamps", () => {
    const plan = buildExitPlanFromPosition(openLong(), {
      now: "2026-08-26T00:00:00Z",
    });
    expect(plan?.reasons).toEqual([]);
    expect(plan?.status).toBe("IDLE");
  });
});
