/**
 * V1.44 — PositionPolicyDecision (spec-v144). No Router. No auto-exit.
 */

import { describe, expect, it } from "vitest";
import { buildExitPlanFromPosition } from "./exit-plan.js";
import { resolveOperatingPolicy } from "./operating-policy.js";
import { decidePositionPolicy } from "./position-policy-decision.js";
import { buildPositionStateFromFill } from "./position-state.js";
import type { TradePlanV1 } from "./trade-plan.js";

const ASOF = "2026-08-31T15:00:00.000Z";

function triggeredPlan(): TradePlanV1 {
  return {
    decisionId: "dec-pp",
    instrumentId: "MSFT",
    direction: "long",
    status: "TRIGGERED",
    quantity: 10,
    riskPct: 0.5,
    whyNot: [],
    executionAllowed: true,
    entry: 100,
    structuralStop: 95,
    target1: 110,
    target2: 120,
  };
}

function openLong() {
  const pos = buildPositionStateFromFill(triggeredPlan(), {
    price: 100,
    quantity: 10,
    filledAt: ASOF,
    positionId: "pos-pp",
  });
  if (!pos) throw new Error("expected OPEN");
  return pos;
}

describe("decidePositionPolicy V1.44", () => {
  it("moderate T1 → REDUCE 30%", () => {
    const pos = openLong();
    const exit = buildExitPlanFromPosition(pos, {
      markPrice: 110,
      at: ASOF,
      exitPolicy: resolveOperatingPolicy("moderate").exit,
    });
    const d = decidePositionPolicy(
      pos,
      exit,
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "open", stale: false },
    );
    expect(d.verdict).toBe("REDUCE");
    expect(d.reasonCode).toBe("TARGET_1");
    expect(d.event?.kind).toBe("T1");
    expect(d.quantity).toBe(3);
    expect(d.policyId).toBe("moderate");
    expect(d.authorization).toBe("policy");
    expect(d.riskImpact).toBe("reduce");
  });

  it("conservative T1 → REDUCE 50%; T2 → EXIT", () => {
    const pos = openLong();
    const policy = resolveOperatingPolicy("conservative");
    const t1 = decidePositionPolicy(
      pos,
      buildExitPlanFromPosition(pos, { markPrice: 110, at: ASOF }),
      policy,
      { asOf: ASOF, session: "open" },
    );
    expect(t1.verdict).toBe("REDUCE");
    expect(t1.quantity).toBe(5);

    const t2 = decidePositionPolicy(
      pos,
      buildExitPlanFromPosition(pos, { markPrice: 120, at: ASOF }),
      policy,
      { asOf: ASOF, session: "open" },
    );
    expect(t2.verdict).toBe("EXIT");
    expect(t2.reasonCode).toBe("TARGET_2");
    expect(t2.quantity).toBe(10);
  });

  it("aggressive_swing T1 → HOLD (0%)", () => {
    const pos = openLong();
    const d = decidePositionPolicy(
      pos,
      buildExitPlanFromPosition(pos, { markPrice: 110, at: ASOF }),
      resolveOperatingPolicy("aggressive_swing"),
      { asOf: ASOF, session: "open" },
    );
    expect(d.verdict).toBe("HOLD");
    expect(d.quantity).toBeNull();
  });

  it("TRAIL → TRAIL verdict with clamped newStop", () => {
    const pos = openLong();
    const d = decidePositionPolicy(
      pos,
      buildExitPlanFromPosition(pos, {
        trailHint: true,
        trailStop: 98,
        at: ASOF,
      }),
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "open" },
    );
    expect(d.verdict).toBe("TRAIL");
    expect(d.newStop).toBe(98);
    expect(d.riskImpact).toBe("protect");
  });

  it("worsening trail stop is clamped to currentStop", () => {
    const pos = openLong();
    const d = decidePositionPolicy(
      pos,
      buildExitPlanFromPosition(pos, {
        trailHint: true,
        trailStop: 90,
        at: ASOF,
      }),
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "open" },
    );
    expect(d.verdict).toBe("TRAIL");
    expect(d.newStop).toBe(95);
  });

  it("T1 + mercado cerrado → HOLD queue_next_session", () => {
    const pos = openLong();
    const d = decidePositionPolicy(
      pos,
      buildExitPlanFromPosition(pos, { markPrice: 110, at: ASOF }),
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "closed" },
    );
    expect(d.verdict).toBe("HOLD");
    expect(d.deferReason).toBe("queue_next_session");
  });

  it("stale + T1 → HOLD data_stale; stale + STOP → EXIT", () => {
    const pos = openLong();
    const staleT1 = decidePositionPolicy(
      pos,
      buildExitPlanFromPosition(pos, { markPrice: 110, at: ASOF }),
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "open", stale: true },
    );
    expect(staleT1.verdict).toBe("HOLD");
    expect(staleT1.deferReason).toBe("data_stale");

    const staleStop = decidePositionPolicy(
      pos,
      buildExitPlanFromPosition(pos, { markPrice: 94, at: ASOF }),
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "open", stale: true },
    );
    expect(staleStop.verdict).toBe("EXIT");
    expect(staleStop.reasonCode).toBe("STRUCTURAL_STOP");
    expect(staleStop.deferReason).toBeNull();
  });
});
