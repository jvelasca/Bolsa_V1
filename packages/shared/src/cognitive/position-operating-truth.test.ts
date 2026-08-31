/**
 * V1.42 F3 — PositionOperatingTruth unit tests (§A.5 + §A.8).
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "../types.js";
import {
  applyProtectionDiscrepancyToCta,
  buildPositionOperatingTruth,
  formatPositionOperatingExecutionCopy,
  mesaNextActionFromPositionOperatingTruth,
  positionOperatingTruthSurfaceSnapshot,
} from "./position-operating-truth.js";
import { markSendAttempted, recordSubmitIntent } from "./submit-intent.js";
import { buildPaperOrder, transitionPaperOrder } from "./paper-order.js";

const ASOF = "2026-08-31T14:00:00.000Z";

function aaplOpen(overrides: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "p-aapl",
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    name: "Apple",
    quantity: 10,
    avgCost: 100,
    lastPrice: 102,
    marketValue: 1020,
    unrealizedPnl: 20,
    unrealizedPnlPct: 2,
    operational: {
      status: "OPEN",
      direction: "long",
      tradePlanId: "tp-aapl",
      plannedEntry: 100,
      actualEntry: 100,
      initialStop: 95,
      currentStop: 95,
      target1: 105,
      target2: 110,
      unrealizedR: 0.4,
      exitPlan: { suggestedAction: "hold" },
    },
    ...overrides,
  };
}

describe("buildPositionOperatingTruth", () => {
  it("composes OperationalTruth + ExecutionState none for stable HOLD", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen(),
      portfolioReconStatus: "ok",
      asOf: ASOF,
    });
    expect(pot).not.toBeNull();
    expect(pot!.operational.decision.action).toBe("HOLD");
    expect(pot!.execution.lifecycle).toBe("none");
    expect(pot!.primaryCta.kind).toBe("maintain");
    expect(pot!.primaryCta.allowsEntry).toBe(false);
    expect(pot!.protectionDiscrepancy).toBe(false);
    expect(pot!.secondaryConditions).toEqual([]);
    expect(mesaNextActionFromPositionOperatingTruth(pot!).kind).toBe(
      "maintain",
    );
  });

  it("§A.8 full_exit + discrepancy → exit primary + secondary protection_discrepancy", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen({
        lastPrice: 94,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-aapl",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 105,
          target2: 110,
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    expect(pot!.primaryCta.kind).toBe("exit");
    expect(pot!.primaryCta.label).toBe("Salir");
    expect(pot!.protectionDiscrepancy).toBe(true);
    expect(pot!.secondaryConditions.map((c) => c.kind)).toContain(
      "protection_discrepancy",
    );
    expect(
      pot!.secondaryConditions.find((c) => c.kind === "protection_discrepancy")
        ?.label,
    ).toMatch(/discrepant/i);
  });

  it("§A.8 reduce + discrepancy → reduce primary + secondary", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen({
        lastPrice: 105,
        marketValue: 1050,
        unrealizedPnl: 50,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-aapl",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 105,
          target2: 110,
          exitPlan: { suggestedAction: "reduce" },
        },
      }),
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    expect(pot!.primaryCta.kind).toBe("reduce");
    expect(
      pot!.secondaryConditions.some((c) => c.kind === "protection_discrepancy"),
    ).toBe(true);
  });

  it("discrepancy alone → protect (not secondary)", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen(),
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    expect(pot!.primaryCta.kind).toBe("protect");
    expect(
      pot!.secondaryConditions.some((c) => c.kind === "protection_discrepancy"),
    ).toBe(false);
  });

  it("orderPending → ExecutionState wins CTA (Ver operaciones)", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen({
        lastPrice: 105,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-aapl",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 105,
          target2: 110,
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      protectionDiscrepancy: true,
      orderPending: true,
      asOf: ASOF,
    });
    expect(pot!.execution.lifecycle).toBe("in_flight");
    expect(pot!.primaryCta.kind).toBe("review");
    expect(pot!.primaryCta.label).toMatch(/operaciones/i);
    expect(formatPositionOperatingExecutionCopy(pot!)).toMatch(/en vuelo/i);
  });

  it("UNKNOWN submitIntent → review CTA · never allowsEntry", () => {
    const intent = markSendAttempted(
      recordSubmitIntent({
        decisionId: "dec-1",
        intentId: "int-1",
        orderId: "ORD-1",
        accountId: "acc-1",
      }),
    );
    const pot = buildPositionOperatingTruth({
      position: aaplOpen(),
      submitIntent: intent,
      asOf: ASOF,
    });
    expect(pot!.execution.lifecycle).toBe("unknown");
    expect(pot!.primaryCta.kind).toBe("review");
    expect(pot!.primaryCta.allowsEntry).toBe(false);
    expect(formatPositionOperatingExecutionCopy(pot!)).toMatch(/no duplicar/i);
  });

  it("trail hint not applied → secondary trail_hint_not_applied", () => {
    // Trail tip from peak MFE ≥ 1.5R; mark below T1 so HOLD/maintain.
    const pot = buildPositionOperatingTruth({
      position: aaplOpen({
        lastPrice: 112.5,
        marketValue: 1125,
        unrealizedPnl: 125,
        unrealizedPnlPct: 12.5,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-aapl",
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
    expect(
      pot!.secondaryConditions.some((c) => c.kind === "trail_hint_not_applied"),
    ).toBe(true);
    expect(pot!.execution.trailingState).toBe("hint");
  });

  it("recon CRITICAL → review CTA; discrepancy secondary", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen({
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-aapl",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 105,
          target2: 110,
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      portfolioReconStatus: "drift",
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    expect(pot!.primaryCta.kind).toBe("review");
    expect(
      pot!.secondaryConditions.some((c) => c.kind === "protection_discrepancy"),
    ).toBe(true);
  });

  it("returns null without operational plan", () => {
    expect(
      buildPositionOperatingTruth({
        position: aaplOpen({ operational: undefined }),
      }),
    ).toBeNull();
  });

  it("includeExitRoute false skips route", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen(),
      includeExitRoute: false,
      asOf: ASOF,
    });
    expect(pot!.exitRoute).toBeNull();
  });

  it("surface snapshot is stable", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen(),
      asOf: ASOF,
    })!;
    const snap = positionOperatingTruthSurfaceSnapshot(pot);
    expect(snap).toEqual({
      ctaKind: "maintain",
      ctaLabel: "Mantener",
      phrase: pot.phrase,
      protectionDiscrepancy: false,
      secondaryKinds: [],
      executionLifecycle: "none",
      executionOrderState: "none",
      attention: pot.attention,
      asOf: ASOF,
    });
  });
});

describe("applyProtectionDiscrepancyToCta", () => {
  it("keeps exit when discrepancy", () => {
    const r = applyProtectionDiscrepancyToCta(
      { kind: "exit", label: "Salir", allowsEntry: false },
      true,
    );
    expect(r.primaryCta.kind).toBe("exit");
    expect(r.discrepancyIsSecondary).toBe(true);
  });

  it("flips maintain → protect when discrepancy alone", () => {
    const r = applyProtectionDiscrepancyToCta(
      { kind: "maintain", label: "Mantener", allowsEntry: false },
      true,
    );
    expect(r.primaryCta.kind).toBe("protect");
    expect(r.discrepancyIsSecondary).toBe(false);
  });
});

describe("PARTIAL paper order", () => {
  it("partial fill → in_flight CTA review", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: "inst-aapl",
          side: "sell",
          quantity: 10,
          orderId: "ORD-p",
        }),
        "SUBMITTED",
      ),
      "PARTIAL",
      { filledQuantity: 4 },
    );
    const pot = buildPositionOperatingTruth({
      position: aaplOpen(),
      paperOrder: paper,
      asOf: ASOF,
    });
    expect(pot!.execution.orderState).toBe("partial");
    expect(pot!.primaryCta.kind).toBe("review");
  });
});
