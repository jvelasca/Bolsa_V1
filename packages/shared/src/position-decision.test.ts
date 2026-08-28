import { describe, expect, it } from "vitest";
import {
  AGGRESSIVE_SWING_EXIT_POLICY,
  CONSERVATIVE_EXIT_POLICY,
  MODERATE_EXIT_POLICY,
  suggestionFromExitPolicy,
} from "./cognitive/exit-policy.js";
import { buildPositionDecision } from "./cognitive/position-decision.js";
import { buildExitPlanFromPosition } from "./cognitive/exit-plan.js";
import {
  applyPositionReduce,
  buildPositionStateFromFill,
  type PositionStateV1,
} from "./cognitive/position-state.js";
import type { TradePlanV1 } from "./cognitive/trade-plan.js";

function plan(overrides: Partial<TradePlanV1> = {}): TradePlanV1 {
  return {
    decisionId: "dec-1",
    instrumentId: "AAPL",
    direction: "long",
    status: "TRIGGERED",
    quantity: 10,
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
  const pos = buildPositionStateFromFill(plan(), {
    price: 100,
    quantity: 10,
    filledAt: "2026-08-28T10:00:00Z",
  });
  if (!pos) throw new Error("expected position");
  return pos;
}

describe("ExitPolicy V1.27", () => {
  it("legacy T1 without policy still halves remaining", () => {
    const s = suggestionFromExitPolicy("TARGET_1", 10, null);
    expect(s.suggestedAction).toBe("reduce");
    expect(s.suggestedQty).toBe(5);
  });

  it("conservative T1 reduces 50%", () => {
    const s = suggestionFromExitPolicy(
      "TARGET_1",
      10,
      CONSERVATIVE_EXIT_POLICY,
    );
    expect(s.suggestedAction).toBe("reduce");
    expect(s.suggestedQty).toBe(5);
  });

  it("moderate T1 reduces 30%", () => {
    const s = suggestionFromExitPolicy("TARGET_1", 10, MODERATE_EXIT_POLICY);
    expect(s.suggestedAction).toBe("reduce");
    expect(s.suggestedQty).toBe(3);
  });

  it("aggressive T1 holds (fraction 0)", () => {
    const s = suggestionFromExitPolicy(
      "TARGET_1",
      10,
      AGGRESSIVE_SWING_EXIT_POLICY,
    );
    expect(s.suggestedAction).toBe("hold");
    expect(s.suggestedQty).toBeNull();
  });

  it("conservative T2 is full exit", () => {
    const s = suggestionFromExitPolicy("TARGET_2", 7, CONSERVATIVE_EXIT_POLICY);
    expect(s.suggestedAction).toBe("full_exit");
    expect(s.suggestedQty).toBe(7);
  });
});

describe("PositionDecision V1.27", () => {
  it("HOLD + nextEvent T1 when mark is between entry and T1", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      templateId: "moderate",
      portfolioReconStatus: "clean",
      at: "2026-08-28T11:00:00Z",
    });
    expect(d?.action).toBe("HOLD");
    expect(d?.attention).toBe("NORMAL");
    expect(d?.nextEvent).toBe("T1");
    expect(d?.reconHealth).toBe("CLEAN");
  });

  it("T1 + moderate → TAKE_PROFIT 30%", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 105 },
      exitPolicy: MODERATE_EXIT_POLICY,
      portfolioReconStatus: "ok",
    });
    expect(d?.action).toBe("TAKE_PROFIT");
    expect(d?.suggestedQty).toBe(3);
    expect(d?.attention).toBe("ATTENTION");
    expect(d?.nextEvent).toBe("T1");
  });

  it("T1 + aggressive → HOLD (evento ≠ vender)", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 105 },
      templateId: "aggressive_swing",
    });
    expect(d?.action).toBe("HOLD");
    expect(d?.primaryReason).toBe("TARGET_1");
  });

  it("thesis invalid → REVIEW, not automatic HOLD", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      thesisInvalid: true,
      portfolioReconStatus: "clean",
    });
    expect(d?.action).toBe("REVIEW");
    expect(d?.attention).toBe("URGENT");
    expect(d?.nextEvent).toBe("THESIS_REVIEW");
  });

  it("recon drift → BLOCKED / CRITICAL / RECONCILIATION", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      portfolioReconStatus: "drift",
    });
    expect(d?.reconHealth).toBe("CRITICAL");
    expect(d?.attention).toBe("BLOCKED");
    expect(d?.action).toBe("REVIEW");
    expect(d?.nextEvent).toBe("RECONCILIATION");
    expect(d?.reason).toBe("reconciliation:portfolio_drift");
  });

  it("structural stop → EXIT URGENT", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 94 },
      portfolioReconStatus: "clean",
    });
    expect(d?.action).toBe("EXIT");
    expect(d?.attention).toBe("URGENT");
    expect(d?.nextEvent).toBe("STOP");
  });

  it("T2 managed seal stops re-emitting TARGET_2", () => {
    const reduced = applyPositionReduce(
      openLong(),
      3,
      105,
      "2026-08-28T12:00:00Z",
      "reduce",
      "t1",
      { markTarget1Achieved: true },
    );
    const sealed = reduced
      ? {
          ...reduced,
          target2AchievedAt: "2026-08-28T13:00:00Z",
        }
      : null;
    const planAtT2 = buildExitPlanFromPosition(sealed, { markPrice: 110 });
    expect(planAtT2?.primaryReason).not.toBe("TARGET_2");
  });
});
