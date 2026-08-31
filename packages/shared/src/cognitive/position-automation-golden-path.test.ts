/**
 * V1.44 — GP-AUTO-01 walk + casos malos (spec §B).
 * Objetos only: no ExecutionRouter, no submit, no Confirm substitution.
 */

import { describe, expect, it } from "vitest";
import { buildExecutionRecord } from "./execution-record.js";
import { buildExitPlanFromPosition } from "./exit-plan.js";
import { checkExitPermission } from "./exit-permission.js";
import {
  buildExecutionState,
  formatExecutionStateCopy,
} from "./execution-state.js";
import { resolveOperatingPolicy } from "./operating-policy.js";
import {
  applyPaperOrderFill,
  buildPaperOrder,
  transitionPaperOrder,
} from "./paper-order.js";
import { decidePositionPolicy } from "./position-policy-decision.js";
import { revisionOriginFromExitReason } from "./position-revision.js";
import {
  applyPositionCurrentStop,
  applyPositionReduce,
  buildPositionStateFromFill,
} from "./position-state.js";
import { reconciliationOpeningVetoReason } from "./reconciliation-opening-veto.js";
import {
  markSendAttempted,
  markSubmitFilled,
  recordSubmitIntent,
  reconstructUnknown,
} from "./submit-intent.js";
import { buildTradeStory } from "./trade-story.js";
import type { TradePlanV1 } from "./trade-plan.js";

const ASOF = "2026-08-31T16:00:00.000Z";
const INST = "inst-msft";
const DECISION = "dec-gp-auto-01";

function plan(qty = 10): TradePlanV1 {
  return {
    decisionId: DECISION,
    instrumentId: INST,
    direction: "long",
    status: "TRIGGERED",
    quantity: qty,
    riskPct: 0.5,
    whyNot: [],
    executionAllowed: true,
    entry: 100,
    structuralStop: 95,
    target1: 110,
    target2: 120,
  };
}

const JIT_ALLOW = {
  autoExecute: true as const,
  paperDExecute: true as const,
  requireJitContext: true as const,
  dataStale: false as const,
  marketClosed: false as const,
  portfolioDrift: false as const,
};

describe("GP-AUTO-01 Position Automation contract walk", () => {
  it("T1 reduce → trail revision → T2 reduce → CLOSED → TradeStory", () => {
    const policy = resolveOperatingPolicy("moderate");
    const opened = buildPositionStateFromFill(plan(), {
      price: 100,
      quantity: 10,
      filledAt: ASOF,
      positionId: "pos-auto",
    });
    expect(opened?.status).toBe("OPEN");
    expect(opened?.remainingQuantity).toBe(10);

    const t1Plan = buildExitPlanFromPosition(opened!, {
      markPrice: 110,
      at: ASOF,
      exitPolicy: policy.exit,
    });
    const t1Dec = decidePositionPolicy(opened!, t1Plan, policy, {
      asOf: ASOF,
      session: "open",
      stale: false,
    });
    expect(t1Dec.verdict).toBe("REDUCE");
    expect(t1Dec.quantity).toBe(3);
    expect(t1Dec.event?.kind).toBe("T1");
    const t1Perm = checkExitPermission(t1Plan, { ...JIT_ALLOW, at: ASOF });
    expect(t1Perm.verdict).toBe("ALLOW");
    expect(t1Perm.action).toBe("reduce");

    const afterT1 = applyPositionReduce(
      opened!,
      t1Dec.quantity!,
      110,
      ASOF,
      "reduce",
      "policy_t1",
      { markTarget1Achieved: true },
    );
    expect(afterT1?.remainingQuantity).toBe(7);
    expect(afterT1?.status).toBe("PARTIAL");
    expect(afterT1?.revisions[0]?.origin).toBe("reduce");
    expect(afterT1?.target1AchievedAt).toBe(ASOF);

    const trailPlan = buildExitPlanFromPosition(afterT1!, {
      trailHint: true,
      trailStop: 98,
      at: "2026-08-31T16:30:00.000Z",
    });
    expect(revisionOriginFromExitReason(trailPlan?.primaryReason)).toBe(
      "trail",
    );
    const trailDec = decidePositionPolicy(afterT1!, trailPlan, policy, {
      asOf: "2026-08-31T16:30:00.000Z",
      session: "open",
      stale: false,
    });
    expect(trailDec.verdict).toBe("TRAIL");
    expect(trailDec.newStop).toBe(98);
    const trailPerm = checkExitPermission(trailPlan, {
      ...JIT_ALLOW,
      at: "2026-08-31T16:30:00.000Z",
    });
    expect(trailPerm.verdict).toBe("ALLOW");
    expect(trailPerm.action).toBe("protect");

    const afterTrail = applyPositionCurrentStop(
      afterT1!,
      trailDec.newStop!,
      "2026-08-31T16:30:00.000Z",
      null,
      "trail",
      "trail_confirm",
    );
    expect(afterTrail?.currentStop).toBe(98);
    expect(afterTrail?.revisions.some((r) => r.origin === "trail")).toBe(true);

    const t2Plan = buildExitPlanFromPosition(afterTrail!, {
      markPrice: 120,
      at: "2026-08-31T17:00:00.000Z",
      exitPolicy: policy.exit,
    });
    const t2Dec = decidePositionPolicy(afterTrail!, t2Plan, policy, {
      asOf: "2026-08-31T17:00:00.000Z",
      session: "open",
      stale: false,
    });
    expect(t2Dec.verdict).toBe("REDUCE");
    expect(t2Dec.reasonCode).toBe("TARGET_2");
    expect(t2Dec.quantity).toBe(2.1);

    const afterT2 = applyPositionReduce(
      afterTrail!,
      t2Dec.quantity!,
      120,
      "2026-08-31T17:00:00.000Z",
      "reduce",
      "policy_t2",
      { markTarget2Achieved: true },
    );
    const closed = applyPositionReduce(
      afterT2!,
      afterT2!.remainingQuantity,
      121,
      "2026-08-31T17:10:00.000Z",
      "reduce",
      "remainder_exit",
    );
    expect(closed?.status).toBe("CLOSED");
    expect(closed?.remainingQuantity).toBe(0);

    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: DECISION,
      positionId: "pos-auto",
      positionState: closed,
      asOf: "2026-08-31T17:10:00.000Z",
      fills: [
        { price: 100, quantity: 10, filledAt: ASOF, positionId: "pos-auto" },
      ],
    });
    expect(story.positionId).toBe("pos-auto");
    expect(story.events.some((e) => e.kind === "fill")).toBe(true);
    expect(
      story.events.some(
        (e) => e.kind === "trailing_applied" || e.kind === "stop_updated",
      ),
    ).toBe(true);
    expect(story.events.some((e) => e.kind === "cierre")).toBe(true);
  });
});

describe("GP-AUTO bad paths (V1.44 contract)", () => {
  it("GP-BAD-CRASH: UNKNOWN · never reenviar · same ids", () => {
    const durable = markSendAttempted(
      recordSubmitIntent({
        decisionId: DECISION,
        intentId: "int-crash",
        orderId: "ORD-crash",
        accountId: "acc-1",
      }),
    );
    const record = reconstructUnknown(durable);
    const paper = transitionPaperOrder(
      buildPaperOrder({
        instrumentId: INST,
        side: "buy",
        quantity: 10,
        orderId: "ORD-crash",
        intentId: "int-crash",
      }),
      "UNKNOWN",
    );
    const s = buildExecutionState({
      instrumentId: INST,
      submitIntent: durable,
      executionRecord: record,
      paperOrder: paper,
    });
    expect(s.lifecycle).toBe("unknown");
    expect(s.nextAction?.kind).toBe("review");
    expect(formatExecutionStateCopy(s)).toMatch(/no duplicar/i);
    const retry = buildExecutionState({
      instrumentId: INST,
      submitIntent: durable,
      executionRecord: record,
      paperOrder: paper,
    });
    expect(retry.orderId).toBe(s.orderId);
    expect(retry.intentId).toBe(s.intentId);
    const filled = buildExecutionState({
      instrumentId: INST,
      paperOrder: applyPaperOrderFill(paper, "tx-recovered"),
      submitIntent: markSubmitFilled(durable),
      executionRecord: buildExecutionRecord({
        filled: true,
        transactionId: "tx-recovered",
      }),
      orderReconciled: true,
    });
    expect(filled.orderId).toBe("ORD-crash");
    expect(filled.lifecycle).toBe("reconciled");
  });

  it("GP-BAD-PARTIAL: 100→40 one position · remaining 60 · no second position", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: INST,
          side: "buy",
          quantity: 100,
          orderId: "ORD-partial",
        }),
        "SUBMITTED",
      ),
      "PARTIAL",
      { filledQuantity: 40 },
    );
    expect(paper.quantity).toBe(100);
    expect(paper.filledQuantity).toBe(40);
    const remaining = paper.quantity - (paper.filledQuantity ?? 0);
    expect(remaining).toBe(60);

    const pos = buildPositionStateFromFill(plan(100), {
      price: 100,
      quantity: 40,
      filledAt: ASOF,
      positionId: "pos-partial",
    });
    expect(pos?.remainingQuantity).toBe(40);
    expect(pos?.quantity).toBe(40);
    const second = buildPositionStateFromFill(plan(100), {
      price: 100,
      quantity: 60,
      filledAt: ASOF,
      positionId: "pos-partial",
    });
    expect(second?.positionId).toBe(pos?.positionId);
  });

  it("GP-BAD-T1T2: same tick → TARGET_2 only · one reduce", () => {
    const pos = buildPositionStateFromFill(plan(), {
      price: 100,
      quantity: 10,
      filledAt: ASOF,
      positionId: "pos-t1t2",
    });
    const exit = buildExitPlanFromPosition(pos!, { markPrice: 120, at: ASOF });
    expect(exit?.primaryReason).toBe("TARGET_2");
    expect(exit?.reasons).not.toContain("TARGET_1");
    const d = decidePositionPolicy(
      pos!,
      exit,
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "open" },
    );
    expect(d.verdict).toBe("REDUCE");
    expect(d.reasonCode).toBe("TARGET_2");
  });

  it("GP-BAD-CLOSED: T1 + market closed → HOLD queue; AUTO permission DENY", () => {
    const pos = buildPositionStateFromFill(plan(), {
      price: 100,
      quantity: 10,
      filledAt: ASOF,
      positionId: "pos-closed",
    });
    const exit = buildExitPlanFromPosition(pos!, { markPrice: 110, at: ASOF });
    const d = decidePositionPolicy(
      pos!,
      exit,
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "closed" },
    );
    expect(d.verdict).toBe("HOLD");
    expect(d.deferReason).toBe("queue_next_session");
    const perm = checkExitPermission(exit, {
      ...JIT_ALLOW,
      marketClosed: true,
    });
    expect(perm.verdict).toBe("DENY");
    expect(perm.reasons).toContain("market_closed");
  });

  it("GP-BAD-STALE: AUTO T1 DENY; STOP protective ALLOW", () => {
    const pos = buildPositionStateFromFill(plan(), {
      price: 100,
      quantity: 10,
      filledAt: ASOF,
      positionId: "pos-stale",
    });
    const t1 = buildExitPlanFromPosition(pos!, { markPrice: 110, at: ASOF });
    const t1Dec = decidePositionPolicy(
      pos!,
      t1,
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "open", stale: true },
    );
    expect(t1Dec.deferReason).toBe("data_stale");
    const t1Perm = checkExitPermission(t1, { ...JIT_ALLOW, dataStale: true });
    expect(t1Perm.reasons).toContain("data_stale");

    const stop = buildExitPlanFromPosition(pos!, { markPrice: 94, at: ASOF });
    const stopDec = decidePositionPolicy(
      pos!,
      stop,
      resolveOperatingPolicy("moderate"),
      { asOf: ASOF, session: "open", stale: true },
    );
    expect(stopDec.verdict).toBe("EXIT");
    const stopPerm = checkExitPermission(stop, {
      ...JIT_ALLOW,
      dataStale: true,
    });
    expect(stopPerm.verdict).toBe("ALLOW");
  });

  it("GP-BAD-RECON: drift blocks entries; protective exit ALLOW; T1 AUTO DENY", () => {
    expect(
      reconciliationOpeningVetoReason({
        portfolioReconStatus: "drift",
        require: true,
      }),
    ).toBe("reconciliation:portfolio_drift");

    const pos = buildPositionStateFromFill(plan(), {
      price: 100,
      quantity: 10,
      filledAt: ASOF,
      positionId: "pos-recon",
    });
    const stop = buildExitPlanFromPosition(pos!, { markPrice: 94, at: ASOF });
    const protectPerm = checkExitPermission(stop, {
      ...JIT_ALLOW,
      portfolioDrift: true,
    });
    expect(protectPerm.verdict).toBe("ALLOW");

    const t1 = buildExitPlanFromPosition(pos!, { markPrice: 110, at: ASOF });
    const t1Perm = checkExitPermission(t1, {
      ...JIT_ALLOW,
      portfolioDrift: true,
    });
    expect(t1Perm.reasons).toContain("portfolio_drift");
  });
});
