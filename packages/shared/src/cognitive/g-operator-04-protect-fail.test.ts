/**
 * G-OPERATOR-04 — protect fail-closed (V2.23).
 * PROTEGER → Confirm → persistSkipped → none + PROTEGER on Mercado and Hoy.
 * Never MANTENER after failed protection.
 */

import { describe, expect, it } from "vitest";
import {
  buildOperatorDecision,
  mesaNextActionFromOperatorDecision,
  resolveOperatorNextAction,
} from "./operator-cabin-view.js";
import type { PositionJourneyReadoutV1 } from "./position-journey-readout.js";

function journey(currentStop: number | null): PositionJourneyReadoutV1 {
  return {
    entry: 184.2,
    risk: {
      initialRisk: 400,
      initialStop: 176.8,
      currentProtected: currentStop != null ? 50 : null,
      realizedR: 0,
      unrealizedR: 0.2,
      remainingQuantity: 10,
    },
    t1: {
      trigger: 195,
      status: "pending",
      qtyFractionPct: 30,
      executed: false,
    },
    t2: {
      trigger: 205,
      status: "pending",
      qtyFractionPct: 30,
      executed: false,
    },
    trail: {
      active: false,
      activationEligible: false,
      currentStop,
      lastRatchet: null,
      trailWidth: "medium",
    },
    remainingQuantity: 10,
    primaryAction: "MANTENER",
    stageLabel: null,
    stageMachine: null,
    lineagePathLabel: null,
    logHasT2Executed: false,
    logHasTrailApplied: false,
    eventKinds: [],
    autoPosture: null,
    killOn: false,
  };
}

describe("G-OPERATOR-04 protect fail", () => {
  it("persistSkipped → NO PROTEGIDA + PROTEGER, never MANTENER", () => {
    const j = journey(null);
    const mercado = resolveOperatorNextAction({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
      persistSkipped: true,
    });
    expect(mercado.title).toBe("PROTEGER");
    expect(mercado.title).not.toBe("MANTENER");

    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
      persistSkipped: true,
    });
    expect(decision.protection.kind).toBe("none");
    expect(decision.protection.label).toBe("SIN PROTECCIÓN");
    expect(decision.currentAction.title).toBe("PROTEGER");
    const hoy = mesaNextActionFromOperatorDecision(decision);
    expect(hoy.kind).toBe("protect");
    expect(hoy.label).toBe("Proteger");
  });

  it("protectionDiscrepancy with stale stop still fail-closed", () => {
    const j = journey(176.8);
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
      protectionDiscrepancy: true,
    });
    expect(decision.protection.kind).toBe("none");
    expect(decision.currentAction.title).toBe("PROTEGER");
    expect(mesaNextActionFromOperatorDecision(decision).kind).toBe("protect");
  });
});
