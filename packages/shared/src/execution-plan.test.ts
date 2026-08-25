/**
 * ExecutionPlan F4 — PAPER pipeline (ADR-032). ≠ broker ≠ ExecuteTrade.
 */

import { describe, expect, it } from "vitest";
import {
  attemptExecutionBroker,
  buildExecutionPlanFromExitPlan,
  stageExecutionJournal,
  stageExecutionReplay,
  stageExecutionValidate,
  type ExecutionPlanV1,
} from "./cognitive/execution-plan.js";
import { buildExitPlanFromPosition } from "./cognitive/exit-plan.js";
import { buildPositionStateFromFill } from "./cognitive/position-state.js";
import type { TradePlanV1 } from "./cognitive/trade-plan.js";

function triggeredPlan(): TradePlanV1 {
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
  };
}

function openLong() {
  const pos = buildPositionStateFromFill(triggeredPlan(), {
    price: 100,
    quantity: 10,
    filledAt: "2026-08-25T15:00:00Z",
    positionId: "pos-1",
  });
  if (!pos) throw new Error("expected OPEN");
  return pos;
}

function exitTriggeredFull() {
  const exit = buildExitPlanFromPosition(openLong(), {
    markPrice: 95,
    exitPlanId: "ex-1",
    at: "2026-08-25T16:00:00Z",
  });
  if (!exit) throw new Error("expected exit");
  expect(exit.status).toBe("TRIGGERED");
  expect(exit.suggestedAction).toBe("full_exit");
  return exit;
}

describe("F4 buildExecutionPlanFromExitPlan", () => {
  it("TRIGGERED full_exit → PAPER_READY market_exit sell", () => {
    const plan = buildExecutionPlanFromExitPlan(exitTriggeredFull(), {
      executionPlanId: "ep-1",
      markPrice: 95,
      at: "2026-08-25T16:05:00Z",
    });
    expect(plan).not.toBeNull();
    const p = plan as ExecutionPlanV1;
    expect(p.executionPlanId).toBe("ep-1");
    expect(p.exitPlanId).toBe("ex-1");
    expect(p.positionId).toBe("pos-1");
    expect(p.venue).toBe("PAPER");
    expect(p.status).toBe("PAPER_READY");
    expect(p.intentKind).toBe("market_exit");
    expect(p.side).toBe("sell");
    expect(p.quantity).toBe(10);
    expect(p.sourceReason).toBe("STRUCTURAL_STOP");
    expect(p.blockedReason).toBeNull();
    expect(p.paperProjection).toEqual({
      price: 95,
      qty: 10,
      at: "2026-08-25T16:05:00Z",
    });
  });

  it("TRIGGERED TARGET_1 reduce → PAPER_READY reduce", () => {
    const exit = buildExitPlanFromPosition(openLong(), {
      markPrice: 105,
      exitPlanId: "ex-t1",
    });
    const plan = buildExecutionPlanFromExitPlan(exit);
    expect(plan?.intentKind).toBe("reduce");
    expect(plan?.status).toBe("PAPER_READY");
    expect(plan?.quantity).toBe(5);
  });

  it("IDLE ExitPlan → null (no invented send)", () => {
    const idle = buildExitPlanFromPosition(openLong(), {
      exitPlanId: "ex-idle",
    });
    expect(idle?.status).toBe("IDLE");
    expect(buildExecutionPlanFromExitPlan(idle)).toBeNull();
  });

  it("HINT TIME_STOP → null (not TRIGGERED)", () => {
    const hint = buildExitPlanFromPosition(openLong(), {
      now: "2026-08-26T00:00:00Z",
      expiresAt: "2026-08-25T23:00:00Z",
    });
    expect(hint?.status).toBe("HINT");
    expect(buildExecutionPlanFromExitPlan(hint)).toBeNull();
  });

  it("ARMED protect → DRAFT stop_amend", () => {
    const armed = buildExitPlanFromPosition(openLong(), {
      trailHint: true,
      trailStop: 100,
      exitPlanId: "ex-trail",
    });
    expect(armed?.status).toBe("ARMED");
    const plan = buildExecutionPlanFromExitPlan(armed);
    expect(plan?.status).toBe("DRAFT");
    expect(plan?.intentKind).toBe("stop_amend");
    expect(plan?.side).toBe("none");
    expect(plan?.limitPrice).toBe(100);
    expect(plan?.venue).toBe("PAPER");
  });

  it("forceVenue BROKER → BLOCKED broker_not_allowed", () => {
    const plan = buildExecutionPlanFromExitPlan(exitTriggeredFull(), {
      forceVenue: "BROKER",
      executionPlanId: "ep-broker",
    });
    expect(plan?.status).toBe("BLOCKED");
    expect(plan?.venue).toBe("BROKER");
    expect(plan?.blockedReason).toBe("broker_not_allowed");
    expect(plan?.intentKind).toBe("market_exit");
  });

  it("null exit → null", () => {
    expect(buildExecutionPlanFromExitPlan(null)).toBeNull();
  });
});

describe("F4 paper pipeline stages", () => {
  function ready(): ExecutionPlanV1 {
    const plan = buildExecutionPlanFromExitPlan(exitTriggeredFull(), {
      executionPlanId: "ep-pipe",
    });
    if (!plan) throw new Error("expected plan");
    return plan;
  }

  it("PAPER_READY → JOURNALED → REPLAYED → VALIDATED", () => {
    const j = stageExecutionJournal(ready(), "j-1", "2026-08-25T17:00:00Z");
    expect(j?.status).toBe("JOURNALED");
    expect(j?.journalRef).toBe("j-1");
    const r = stageExecutionReplay(j, "r-1");
    expect(r?.status).toBe("REPLAYED");
    expect(r?.replayRef).toBe("r-1");
    const v = stageExecutionValidate(r, "v-1");
    expect(v?.status).toBe("VALIDATED");
    expect(v?.validationRef).toBe("v-1");
    expect(v?.venue).toBe("PAPER");
  });

  it("stages are sequential (no skip)", () => {
    expect(stageExecutionReplay(ready())).toBeNull();
    expect(stageExecutionValidate(ready())).toBeNull();
    expect(stageExecutionJournal(ready())?.status).toBe("JOURNALED");
  });

  it("DRAFT stop_amend cannot journal", () => {
    const armed = buildExitPlanFromPosition(openLong(), {
      trailHint: true,
      trailStop: 100,
    });
    const draft = buildExecutionPlanFromExitPlan(armed);
    expect(draft?.status).toBe("DRAFT");
    expect(stageExecutionJournal(draft)).toBeNull();
  });

  it("attemptBroker always BLOCKED", () => {
    const blocked = attemptExecutionBroker(ready());
    expect(blocked?.status).toBe("BLOCKED");
    expect(blocked?.blockedReason).toBe("broker_not_allowed");
    expect(blocked?.venue).toBe("BROKER");
    const v = stageExecutionValidate(
      stageExecutionReplay(stageExecutionJournal(ready())),
    );
    const fromValidated = attemptExecutionBroker(v);
    expect(fromValidated?.status).toBe("BLOCKED");
    expect(fromValidated?.blockedReason).toBe("broker_not_allowed");
  });
});
