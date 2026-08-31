/**
 * PositionRevision OI-5 — historia auditada (ADR-034).
 */

import { describe, expect, it } from "vitest";
import {
  buildPositionRevision,
  positionRevisionFromUnknown,
  revisionsFromUnknown,
  stopOrStatusChanged,
} from "./cognitive/position-revision.js";
import {
  applyPositionCurrentStop,
  applyPositionMark,
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

function openLong(stop = 95): PositionStateV1 {
  const pos = buildPositionStateFromFill(
    triggeredPlan({ structuralStop: stop }),
    {
      price: 100,
      quantity: 10,
      filledAt: "2026-08-26T00:00:00Z",
      positionId: "pos-1",
    },
  );
  if (!pos) throw new Error("expected OPEN");
  return pos;
}

describe("OI-5 PositionRevision factory", () => {
  it("builds revision fields", () => {
    const rev = buildPositionRevision({
      revisionId: "REV-1",
      at: "2026-08-26T12:00:00Z",
      previousStop: 95,
      nextStop: 98,
      previousStatus: "OPEN",
      nextStatus: "OPEN",
      origin: "protect",
    });
    expect(rev).toEqual({
      revisionId: "REV-1",
      at: "2026-08-26T12:00:00Z",
      previousStop: 95,
      nextStop: 98,
      previousStatus: "OPEN",
      nextStatus: "OPEN",
      origin: "protect",
      reason: null,
    });
  });

  it("accepts origin trail", () => {
    const rev = buildPositionRevision({
      revisionId: "REV-T",
      at: "2026-08-31T12:00:00Z",
      previousStop: 95,
      nextStop: 98,
      origin: "trail",
      reason: "trail_confirm",
    });
    expect(rev.origin).toBe("trail");
    expect(positionRevisionFromUnknown(rev)?.origin).toBe("trail");
  });

  it("detects stop/status change", () => {
    expect(
      stopOrStatusChanged({
        previousStop: 95,
        nextStop: 98,
        previousStatus: "OPEN",
        nextStatus: "OPEN",
      }),
    ).toBe(true);
    expect(
      stopOrStatusChanged({
        previousStop: 95,
        nextStop: 95,
        previousStatus: "OPEN",
        nextStatus: "OPEN",
      }),
    ).toBe(false);
  });

  it("skips invalid raw revisions", () => {
    expect(revisionsFromUnknown(null)).toEqual([]);
    expect(positionRevisionFromUnknown({ revisionId: "x" })).toBeNull();
  });
});

describe("OI-5 apply stop/reduce revisions", () => {
  it("from_fill starts with empty revisions", () => {
    expect(openLong().revisions).toEqual([]);
  });

  it("applyCurrentStop appends protect revision", () => {
    const nxt = applyPositionCurrentStop(
      openLong(),
      98,
      "2026-08-26T01:00:00Z",
      null,
      "protect",
    );
    expect(nxt?.currentStop).toBe(98);
    expect(nxt?.revisions).toHaveLength(1);
    expect(nxt?.revisions[0]?.origin).toBe("protect");
    expect(nxt?.revisions[0]?.previousStop).toBe(95);
    expect(nxt?.revisions[0]?.nextStop).toBe(98);
  });

  it("applyCurrentStop appends trail revision", () => {
    const nxt = applyPositionCurrentStop(
      openLong(),
      98,
      "2026-08-26T01:00:00Z",
      null,
      "trail",
      "trail_confirm",
    );
    expect(nxt?.currentStop).toBe(98);
    expect(nxt?.revisions).toHaveLength(1);
    expect(nxt?.revisions[0]?.origin).toBe("trail");
    expect(nxt?.revisions[0]?.reason).toBe("trail_confirm");
  });

  it("same stop does not append", () => {
    const nxt = applyPositionCurrentStop(openLong(), 95, "t1");
    expect(nxt?.revisions).toEqual([]);
  });

  it("BE stop appends status change", () => {
    const be = applyPositionCurrentStop(openLong(), 100, "t1");
    expect(be?.status).toBe("PROTECTED");
    expect(be?.revisions[0]?.previousStatus).toBe("OPEN");
    expect(be?.revisions[0]?.nextStatus).toBe("PROTECTED");
  });

  it("worsen with override uses origin override", () => {
    const worse = applyPositionCurrentStop(openLong(98), 94, "t1", {
      reason: "gap_widen",
    });
    expect(worse?.revisions[0]?.origin).toBe("override");
    expect(worse?.revisions[0]?.reason).toBe("gap_widen");
  });

  it("reduce appends status revision", () => {
    const partial = applyPositionReduce(openLong(), 5, 105, "t1");
    expect(partial?.status).toBe("PARTIAL");
    expect(partial?.revisions).toHaveLength(1);
    expect(partial?.revisions[0]?.origin).toBe("reduce");
  });

  it("mark does not append", () => {
    const marked = applyPositionMark(openLong(), 105, "t1");
    expect(marked?.revisions).toEqual([]);
  });
});
