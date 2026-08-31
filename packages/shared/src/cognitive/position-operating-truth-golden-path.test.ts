/**
 * V1.42 F3 — Golden Paths that PositionOperatingTruth must close (spec §C GP-05…09).
 * GP-03/04/10 remain covered by ExecutionState; POT composes them when present.
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "../types.js";
import {
  buildPositionOperatingTruth,
  formatPositionOperatingExecutionCopy,
} from "./position-operating-truth.js";
import { buildPaperOrder, transitionPaperOrder } from "./paper-order.js";
import { markSendAttempted, recordSubmitIntent } from "./submit-intent.js";

const ASOF = "2026-08-31T14:30:00.000Z";

function openPos(overrides: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "p-gp",
    instrumentId: "inst-gp",
    symbol: "MSFT",
    name: "Microsoft",
    quantity: 8,
    avgCost: 100,
    lastPrice: 102,
    marketValue: 816,
    unrealizedPnl: 16,
    unrealizedPnlPct: 2,
    operational: {
      status: "OPEN",
      direction: "long",
      tradePlanId: "tp-gp",
      plannedEntry: 100,
      actualEntry: 100,
      initialStop: 95,
      currentStop: 95,
      target1: 110,
      target2: 120,
      unrealizedR: 0.4,
      exitPlan: { suggestedAction: "hold" },
    },
    ...overrides,
  };
}

describe("PositionOperatingTruth Golden Paths V1.42 F3", () => {
  it("GP-05 Stop: full_exit → Salir; discrepancy does not flip CTA", () => {
    const pot = buildPositionOperatingTruth({
      position: openPos({
        lastPrice: 94,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-gp",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 110,
          target2: 120,
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    expect(pot!.primaryCta.kind).toBe("exit");
    expect(pot!.primaryCta.label).toBe("Salir");
    expect(pot!.primaryCta.allowsEntry).toBe(false);
    expect(
      pot!.secondaryConditions.some((c) => c.kind === "protection_discrepancy"),
    ).toBe(true);
  });

  it("GP-06 T1: reduce (or maintain if HOLD managed) — never T1_REACHED label", () => {
    const pot = buildPositionOperatingTruth({
      position: openPos({
        lastPrice: 110,
        marketValue: 880,
        unrealizedPnl: 80,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-gp",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 110,
          target2: 120,
          exitPlan: { suggestedAction: "reduce" },
        },
      }),
      asOf: ASOF,
    });
    expect(pot!.primaryCta.kind).toBe("reduce");
    expect(pot!.primaryCta.label).not.toMatch(/T1_REACHED/i);
    expect(pot!.phrase).not.toMatch(/T1_REACHED/i);
  });

  it("GP-07 T2: reduce symmetric to T1", () => {
    const pot = buildPositionOperatingTruth({
      position: openPos({
        lastPrice: 120,
        marketValue: 960,
        unrealizedPnl: 160,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-gp",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 100,
          target1: 110,
          target2: 120,
          exitPlan: { suggestedAction: "reduce" },
        },
      }),
      asOf: ASOF,
    });
    expect(pot!.primaryCta.kind).toBe("reduce");
    expect(pot!.primaryCta.allowsEntry).toBe(false);
  });

  it("GP-08 Trailing: hint ≠ applied · secondary trail_hint_not_applied", () => {
    // R=5; peak 2.5R → tip trail; mark below T1 so CTA stays maintain (wire hold).
    const pot = buildPositionOperatingTruth({
      position: openPos({
        lastPrice: 112.5,
        marketValue: 900,
        unrealizedPnl: 100,
        unrealizedPnlPct: 12.5,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-gp",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 130,
          target2: 150,
          unrealizedR: 2.5,
          exitPlan: { suggestedAction: "hold" },
        },
      }),
      asOf: ASOF,
    });
    expect(pot!.execution.trailingState).toBe("hint");
    expect(pot!.execution.trailingState).not.toBe("applied");
    expect(
      pot!.secondaryConditions.some((c) => c.kind === "trail_hint_not_applied"),
    ).toBe(true);
    const trailLabel = pot!.secondaryConditions.find(
      (c) => c.kind === "trail_hint_not_applied",
    )?.label;
    expect(trailLabel).toMatch(/requiere Confirm/i);
    expect(trailLabel).not.toMatch(/aplicado$/i);
    expect(pot!.primaryCta.kind).toBe("maintain");
  });

  it("GP-08 Trailing: after Confirm stop matches hint → applied · no trail_hint_not_applied", () => {
    // Same geometry as hint case; currentStop raised to trail hint (lockedR=1.5 → 107.5).
    const pot = buildPositionOperatingTruth({
      position: openPos({
        lastPrice: 112.5,
        marketValue: 900,
        unrealizedPnl: 100,
        unrealizedPnlPct: 12.5,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-gp",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 107.5,
          target1: 130,
          target2: 150,
          unrealizedR: 2.5,
          exitPlan: { suggestedAction: "hold" },
        },
      }),
      asOf: ASOF,
    });
    expect(pot!.operational.trailing.applied).toBe(true);
    expect(pot!.execution.trailingState).toBe("applied");
    expect(
      pot!.secondaryConditions.some((c) => c.kind === "trail_hint_not_applied"),
    ).toBe(false);
  });

  it("GP-09 Discrepancy: alone → protect; with full_exit → exit + secondary", () => {
    const alone = buildPositionOperatingTruth({
      position: openPos(),
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    expect(alone!.primaryCta.kind).toBe("protect");

    const withExit = buildPositionOperatingTruth({
      position: openPos({
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-gp",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 110,
          target2: 120,
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      protectionDiscrepancy: true,
      portfolioReconStatus: "ok",
      asOf: ASOF,
    });
    expect(withExit!.primaryCta.kind).toBe("exit");
    expect(
      withExit!.secondaryConditions.some(
        (c) => c.kind === "protection_discrepancy",
      ),
    ).toBe(true);

    const incident = buildPositionOperatingTruth({
      position: openPos(),
      portfolioReconStatus: "drift",
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    expect(incident!.primaryCta.kind).toBe("review");
  });

  it("partial fill composed: ExecutionState partial wins CTA", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: "inst-gp",
          side: "sell",
          quantity: 8,
          orderId: "ORD-gp-part",
        }),
        "SUBMITTED",
      ),
      "PARTIAL",
      { filledQuantity: 3 },
    );
    const pot = buildPositionOperatingTruth({
      position: openPos({
        operational: {
          status: "PARTIAL",
          direction: "long",
          tradePlanId: "tp-gp",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 110,
          target2: 120,
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      paperOrder: paper,
      asOf: ASOF,
    });
    expect(pot!.execution.fillState).toBe("partial");
    expect(pot!.primaryCta.kind).toBe("review");
  });

  it("UNKNOWN composed: review · no duplicar · allowsEntry false", () => {
    const intent = markSendAttempted(
      recordSubmitIntent({
        decisionId: "dec-gp",
        intentId: "int-gp",
        orderId: "ORD-gp",
        accountId: "acc-1",
      }),
    );
    const pot = buildPositionOperatingTruth({
      position: openPos(),
      submitIntent: intent,
      asOf: ASOF,
    });
    expect(pot!.execution.lifecycle).toBe("unknown");
    expect(pot!.primaryCta.kind).toBe("review");
    expect(pot!.primaryCta.allowsEntry).toBe(false);
    expect(formatPositionOperatingExecutionCopy(pot!)).toMatch(/no duplicar/i);
  });
});
