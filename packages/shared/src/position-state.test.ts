/**
 * PositionState F2 + F2.1 — factory + transitions (ADR-032).
 */

import { describe, expect, it } from "vitest";
import {
  applyPositionCurrentStop,
  applyPositionMark,
  applyPositionReduce,
  applyTargetLeg,
  buildPositionStateFromFill,
  doesStopWorsen,
  targetLegFromUnknown,
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

describe("F2 buildPositionStateFromFill", () => {
  it("builds OPEN from TradePlan + fill", () => {
    const pos = buildPositionStateFromFill(triggeredPlan(), {
      price: 100.5,
      quantity: 10,
      filledAt: "2026-08-25T15:00:00Z",
      positionId: "pos-1",
    });
    expect(pos).not.toBeNull();
    const p = pos as PositionStateV1;
    expect(p.status).toBe("OPEN");
    expect(p.positionId).toBe("pos-1");
    expect(p.tradePlanId).toBe("dec-1");
    expect(p.plannedEntry).toBe(100);
    expect(p.actualEntry).toBe(100.5);
    expect(p.initialStop).toBe(95);
    expect(p.currentStop).toBe(95);
    expect(p.target1).toBe(105);
    expect(p.target2).toBe(110);
    expect(p.quantity).toBe(10);
    expect(p.remainingQuantity).toBe(10);
    expect(p.initialRisk).toBe(5.5);
    expect(p.realizedR).toBe(0);
    expect(p.unrealizedR).toBeNull();
    expect(p.mfeMae).toEqual({ mfeR: null, maeR: null, source: "none" });
    expect(p.thesisHealth).toEqual({ status: "none" });
    expect(p.protectionState).toEqual({ status: "none" });
    expect(p.trailing).toEqual({ status: "none" });
    expect(p.exitStatus).toBe("none");
    expect(p.revisions).toEqual([]);
    expect(p.target1Leg?.status).toBe("pending");
    expect(p.target2Leg?.status).toBe("pending");
    expect(p.createdAt).toBe("2026-08-25T15:00:00Z");
  });

  it("returns null without TradePlan", () => {
    expect(
      buildPositionStateFromFill(null, { price: 100, quantity: 1 }),
    ).toBeNull();
  });

  it("returns null without valid fill", () => {
    expect(buildPositionStateFromFill(triggeredPlan(), null)).toBeNull();
    expect(
      buildPositionStateFromFill(triggeredPlan(), { price: 0, quantity: 1 }),
    ).toBeNull();
    expect(
      buildPositionStateFromFill(triggeredPlan(), {
        price: 100,
        quantity: 0,
      }),
    ).toBeNull();
  });

  it("returns null when plan direction is none", () => {
    expect(
      buildPositionStateFromFill(triggeredPlan({ direction: "none" }), {
        price: 100,
        quantity: 1,
      }),
    ).toBeNull();
  });

  it("short geometry uses |entry−stop| for initialRisk", () => {
    const pos = buildPositionStateFromFill(
      triggeredPlan({
        direction: "short",
        entry: 100,
        structuralStop: 105,
        target1: 95,
        target2: 90,
      }),
      { price: 99, quantity: 5, positionId: "pos-s" },
    );
    expect(pos?.initialRisk).toBe(6);
    expect(pos?.direction).toBe("short");
  });

  it("GP-V165-03: preserves decisionId and tradePlanId from TradePlan", () => {
    const pos = buildPositionStateFromFill(
      triggeredPlan({
        decisionId: "DEC-1",
        tradePlanId: "TP-1",
        direction: "long",
        status: "TRIGGERED",
      }),
      {
        price: 100,
        quantity: 10,
        filledAt: "2026-08-25T15:00:00Z",
        positionId: "pos-dec-tp",
      },
    );
    expect(pos).not.toBeNull();
    expect(pos!.decisionId).toBe("DEC-1");
    expect(pos!.tradePlanId).toBe("TP-1");
    expect(pos!.decisionId).not.toBe("TP-1");
  });
});

describe("F2.1 applyPositionMark", () => {
  it("sets unrealizedR and close_proxy MFE/MAE peaks", () => {
    const marked = applyPositionMark(openLong(), 105, "2026-08-25T16:00:00Z");
    expect(marked).not.toBeNull();
    expect(marked!.status).toBe("OPEN");
    expect(marked!.unrealizedR).toBe(1);
    expect(marked!.mfeMae).toEqual({
      mfeR: 1,
      maeR: 1,
      source: "close_proxy",
    });
    expect(marked!.updatedAt).toBe("2026-08-25T16:00:00Z");
  });

  it("tracks adverse MAE without changing status", () => {
    const up = applyPositionMark(openLong(), 105)!;
    const down = applyPositionMark(up, 95)!;
    expect(down.status).toBe("OPEN");
    expect(down.unrealizedR).toBe(-1);
    expect(down.mfeMae.mfeR).toBe(1);
    expect(down.mfeMae.maeR).toBe(-1);
    expect(down.mfeMae.source).toBe("close_proxy");
  });

  it("returns null on CLOSED or bad mark", () => {
    const closed = applyPositionReduce(openLong(), 10, 100)!;
    expect(applyPositionMark(closed, 105)).toBeNull();
    expect(applyPositionMark(openLong(), 0)).toBeNull();
  });
});

describe("F2.1 applyPositionReduce", () => {
  it("PARTIAL then CLOSED with weighted realizedR", () => {
    const partial = applyPositionReduce(openLong(), 5, 105, "t1");
    expect(partial!.status).toBe("PARTIAL");
    expect(partial!.remainingQuantity).toBe(5);
    expect(partial!.realizedR).toBe(0.5);
    expect(partial!.exitStatus).toBe("none");

    const closed = applyPositionReduce(partial, 5, 110, "t2");
    expect(closed!.status).toBe("CLOSED");
    expect(closed!.remainingQuantity).toBe(0);
    expect(closed!.realizedR).toBe(1.5);
    expect(closed!.exitStatus).toBe("done");
  });

  it("rejects oversize and CLOSED terminal", () => {
    expect(applyPositionReduce(openLong(), 11, 100)).toBeNull();
    const closed = applyPositionReduce(openLong(), 10, 100)!;
    expect(applyPositionReduce(closed, 1, 100)).toBeNull();
  });
});

describe("F2.1 applyPositionCurrentStop", () => {
  it("BE stop → PROTECTED; below entry stays OPEN", () => {
    const be = applyPositionCurrentStop(openLong(), 100);
    expect(be!.status).toBe("PROTECTED");
    expect(be!.currentStop).toBe(100);

    const open = applyPositionCurrentStop(openLong(), 97);
    expect(open!.status).toBe("OPEN");
    expect(open!.currentStop).toBe(97);
  });

  it("PROTECTED wins over PARTIAL when BE", () => {
    const partial = applyPositionReduce(openLong(), 4, 105)!;
    expect(partial.status).toBe("PARTIAL");
    const prot = applyPositionCurrentStop(partial, 100)!;
    expect(prot.status).toBe("PROTECTED");
    expect(prot.remainingQuantity).toBe(6);
  });

  it("short BE is stop <= entry", () => {
    const short = buildPositionStateFromFill(
      triggeredPlan({
        direction: "short",
        entry: 100,
        structuralStop: 105,
      }),
      { price: 100, quantity: 10, positionId: "s1" },
    )!;
    expect(applyPositionCurrentStop(short, 100)!.status).toBe("PROTECTED");
    expect(applyPositionCurrentStop(short, 102)!.status).toBe("OPEN");
  });
});

describe("H2 invariantes from_fill / stop", () => {
  it("WATCH / ARMED / BLOCKED do not birth a position", () => {
    const fill = { price: 100, quantity: 1 };
    expect(
      buildPositionStateFromFill(triggeredPlan({ status: "WATCH" }), fill),
    ).toBeNull();
    expect(
      buildPositionStateFromFill(triggeredPlan({ status: "ARMED" }), fill),
    ).toBeNull();
    expect(
      buildPositionStateFromFill(triggeredPlan({ status: "BLOCKED" }), fill),
    ).toBeNull();
  });

  it("WATCH births with audited override", () => {
    const pos = buildPositionStateFromFill(
      triggeredPlan({ status: "WATCH" }),
      { price: 100, quantity: 1, positionId: "ov-1" },
      { reason: "manual_fill_after_review" },
    );
    expect(pos?.status).toBe("OPEN");
    expect(pos?.positionId).toBe("ov-1");
  });

  it("empty override reason is not audited", () => {
    expect(
      buildPositionStateFromFill(
        triggeredPlan({ status: "WATCH" }),
        { price: 100, quantity: 1 },
        { reason: "  " },
      ),
    ).toBeNull();
  });

  it("long stop cannot worsen without override", () => {
    expect(applyPositionCurrentStop(openLong(), 94)).toBeNull();
    const worse = applyPositionCurrentStop(openLong(), 94, null, {
      reason: "gap_widen",
    });
    expect(worse?.currentStop).toBe(94);
    expect(worse?.revisions[0]?.origin).toBe("override");
  });

  it("short stop cannot worsen without override", () => {
    const short = buildPositionStateFromFill(
      triggeredPlan({
        direction: "short",
        entry: 100,
        structuralStop: 105,
      }),
      { price: 100, quantity: 10, positionId: "s2" },
    )!;
    expect(applyPositionCurrentStop(short, 106)).toBeNull();
    expect(
      applyPositionCurrentStop(short, 106, null, { reason: "widen" })
        ?.currentStop,
    ).toBe(106);
  });

  it("OP-05 — trailing/stop ratchet never worsens without override", () => {
    const open = openLong();
    const up1 = applyPositionCurrentStop(open, 97);
    expect(up1?.currentStop).toBe(97);
    const up2 = applyPositionCurrentStop(up1!, 100);
    expect(up2?.currentStop).toBe(100);
    expect(applyPositionCurrentStop(up2!, 98)).toBeNull();
  });

  it("V1.52 TargetLeg pending at birth; executed on T1 reduce", () => {
    const open = openLong();
    expect(open.target1Leg?.status).toBe("pending");
    const trig = applyTargetLeg(
      open,
      "t1",
      "triggered",
      "2026-09-01T11:00:00Z",
      "ev-t1",
    );
    expect(trig.target1Leg?.status).toBe("triggered");
    const reduced = applyPositionReduce(
      trig,
      5,
      105,
      "2026-09-01T11:01:00Z",
      "reduce",
      null,
      {
        markTarget1Achieved: true,
        fillId: "tx-t1",
        eventId: "ev-t1",
      },
    );
    expect(reduced?.target1Leg?.status).toBe("executed");
    expect(reduced?.target1Leg?.fillId).toBe("tx-t1");
    expect(reduced?.target1AchievedAt).toBe("2026-09-01T11:01:00Z");
  });

  it("V1.52 legacy snapshot hydrates executed from achievedAt", () => {
    const leg = targetLegFromUnknown(undefined, 105, "2026-08-25T16:00:00Z");
    expect(leg?.status).toBe("executed");
  });
});

describe("doesStopWorsen H2 LONG/SHORT parity", () => {
  it("long worsens when next is lower; short when higher", () => {
    expect(doesStopWorsen("long", 100, 99)).toBe(true);
    expect(doesStopWorsen("long", 100, 101)).toBe(false);
    expect(doesStopWorsen("short", 100, 101)).toBe(true);
    expect(doesStopWorsen("short", 100, 99)).toBe(false);
    expect(doesStopWorsen("long", null, 99)).toBe(false);
  });
});
