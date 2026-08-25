/**
 * ExitPermission — veto salida (ADR-032). ≠ check_opening ≠ auto-exit.
 */

import { describe, expect, it } from "vitest";
import { buildExecutionPlanFromExitPlan } from "./cognitive/execution-plan.js";
import { buildExitPlanFromPosition } from "./cognitive/exit-plan.js";
import { checkExitPermission } from "./cognitive/exit-permission.js";
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

function exitTriggered() {
  const exit = buildExitPlanFromPosition(openLong(), {
    markPrice: 95,
    exitPlanId: "ex-1",
    at: "2026-08-25T16:00:00Z",
  });
  if (!exit) throw new Error("expected exit");
  return exit;
}

describe("F5 checkExitPermission", () => {
  it("ALLOW for TRIGGERED full_exit (SEMI, no auto)", () => {
    const perm = checkExitPermission(exitTriggered(), {
      at: "2026-08-25T16:10:00Z",
    });
    expect(perm.verdict).toBe("ALLOW");
    expect(perm.allowed).toBe(true);
    expect(perm.reasons).toEqual([]);
    expect(perm.action).toBe("full_exit");
    expect(perm.exitPlanId).toBe("ex-1");
    expect(perm.positionId).toBe("pos-1");
  });

  it("ALLOW for TRIGGERED reduce", () => {
    const exit = buildExitPlanFromPosition(openLong(), { markPrice: 105 });
    const perm = checkExitPermission(exit);
    expect(perm.allowed).toBe(true);
    expect(perm.action).toBe("reduce");
  });

  it("ALLOW for ARMED protect", () => {
    const exit = buildExitPlanFromPosition(openLong(), {
      trailHint: true,
      trailStop: 100,
    });
    const perm = checkExitPermission(exit);
    expect(perm.allowed).toBe(true);
    expect(perm.action).toBe("protect");
  });

  it("DENY missing_exit_plan", () => {
    const perm = checkExitPermission(null);
    expect(perm.verdict).toBe("DENY");
    expect(perm.reasons).toEqual(["missing_exit_plan"]);
    expect(perm.action).toBe("none");
  });

  it("DENY not_actionable for IDLE", () => {
    const idle = buildExitPlanFromPosition(openLong());
    expect(idle?.status).toBe("IDLE");
    const perm = checkExitPermission(idle);
    expect(perm.reasons).toEqual(["not_actionable"]);
  });

  it("DENY not_actionable for HINT", () => {
    const hint = buildExitPlanFromPosition(openLong(), {
      now: "2026-08-26T00:00:00Z",
      expiresAt: "2026-08-25T23:00:00Z",
    });
    expect(hint?.status).toBe("HINT");
    const perm = checkExitPermission(hint);
    expect(perm.reasons).toEqual(["not_actionable"]);
  });

  it("DENY position_closed", () => {
    const perm = checkExitPermission(exitTriggered(), {
      positionClosed: true,
    });
    expect(perm.reasons).toEqual(["position_closed"]);
  });

  it("DENY kill_switch", () => {
    const perm = checkExitPermission(exitTriggered(), { killSwitch: true });
    expect(perm.reasons).toEqual(["kill_switch"]);
  });

  it("DENY broker_not_allowed when brokerRequested", () => {
    const perm = checkExitPermission(exitTriggered(), {
      brokerRequested: true,
    });
    expect(perm.reasons).toEqual(["broker_not_allowed"]);
  });

  it("DENY broker_not_allowed from ExecutionPlan BROKER", () => {
    const exec = buildExecutionPlanFromExitPlan(exitTriggered(), {
      forceVenue: "BROKER",
    });
    const perm = checkExitPermission(exitTriggered(), {
      executionPlan: exec,
    });
    expect(perm.reasons).toEqual(["broker_not_allowed"]);
  });

  it("DENY paper_auto_env_blocked when autoExecute without PAPER_D", () => {
    const perm = checkExitPermission(exitTriggered(), {
      autoExecute: true,
      paperDExecute: false,
    });
    expect(perm.reasons).toEqual(["paper_auto_env_blocked"]);
  });

  it("ALLOW autoExecute when paperDExecute true", () => {
    const perm = checkExitPermission(exitTriggered(), {
      autoExecute: true,
      paperDExecute: true,
    });
    expect(perm.allowed).toBe(true);
  });

  it("DENY execution_blocked when PAPER plan is BLOCKED (non-broker reason)", () => {
    const ready = buildExecutionPlanFromExitPlan(exitTriggered());
    expect(ready).not.toBeNull();
    const weird = {
      ...ready!,
      status: "BLOCKED" as const,
      venue: "PAPER" as const,
      blockedReason: null,
    };
    const perm = checkExitPermission(exitTriggered(), {
      executionPlan: weird,
    });
    expect(perm.reasons).toEqual(["execution_blocked"]);
  });

  it("kill_switch precedes not_actionable", () => {
    const idle = buildExitPlanFromPosition(openLong());
    const perm = checkExitPermission(idle, { killSwitch: true });
    expect(perm.reasons).toEqual(["kill_switch"]);
  });
});
