/**
 * G-OPERATOR-03 — protection journey (V2.23).
 * OPEN_UNPROTECTED → PROTEGER → Confirm bootstrap → never «stop técnico».
 * Signed technical stop → protection.kind technical.
 */

import { describe, expect, it } from "vitest";
import { bootstrapProtectStopLabel } from "./protect-stop-source.js";
import {
  buildOperatorDecision,
  mesaNextActionFromOperatorDecision,
  resolveOperatorNextAction,
} from "./operator-cabin-view.js";
import type { PositionJourneyReadoutV1 } from "./position-journey-readout.js";

function unprotectedJourney(): PositionJourneyReadoutV1 {
  return {
    entry: 184.2,
    risk: {
      initialRisk: null,
      initialStop: null,
      currentProtected: null,
      realizedR: null,
      unrealizedR: null,
      remainingQuantity: 10,
    },
    t1: {
      trigger: null,
      status: "absent",
      qtyFractionPct: null,
      executed: false,
    },
    t2: {
      trigger: null,
      status: "absent",
      qtyFractionPct: null,
      executed: false,
    },
    trail: {
      active: false,
      activationEligible: false,
      currentStop: null,
      lastRatchet: null,
      trailWidth: null,
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

describe("G-OPERATOR-03 protect journey", () => {
  it("OPEN_UNPROTECTED → PROTEGER on Mercado and Hoy", () => {
    const j = unprotectedJourney();
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
      protectKind: "bootstrap",
    });
    expect(decision.currentAction.title).toBe("PROTEGER");
    expect(decision.protection.kind).toBe("none");
    expect(mesaNextActionFromOperatorDecision(decision).kind).toBe("protect");
    expect(decision.currentAction.subtitle).toMatch(/emergencia/i);
    expect(decision.currentAction.title).not.toMatch(/técnico/i);
  });

  it("Confirm bootstrap copy is emergency, never stop técnico", () => {
    const label = bootstrapProtectStopLabel();
    expect(label.title).toMatch(/sin protección/i);
    expect(label.suggestedLine).toMatch(/emergencia/i);
    expect(label.disclaimer).toMatch(/No sustituye/i);
    expect(label.title).not.toMatch(/técnico/i);
    expect(label.suggestedLine).not.toMatch(/técnico/i);
  });

  it("signed bootstrap stop → emergency, not technical", () => {
    const j = unprotectedJourney();
    j.trail.currentStop = 174.99;
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
      protectKind: "bootstrap",
      currentStop: 174.99,
      entry: 184.2,
    });
    expect(decision.protection.kind).toBe("emergency");
    expect(decision.protection.isTechnical).toBe(false);
    expect(decision.protection.label).not.toMatch(/técnico/i);
  });

  it("signed technical stop → Protegida", () => {
    const j = unprotectedJourney();
    j.trail.currentStop = 176.8;
    j.risk.initialStop = 176.8;
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
      protectKind: "plan",
      currentStop: 176.8,
    });
    expect(decision.protection.kind).toBe("technical");
    expect(decision.currentAction.title).toBe("MANTENER");
  });

  it("planned stop only (not executed) never counts as technical protection", () => {
    const j = unprotectedJourney();
    j.risk.initialStop = 176.8;
    const next = resolveOperatorNextAction({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
    });
    expect(next.title).toBe("PROTEGER");
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
    });
    expect(decision.protection.kind).toBe("none");
  });
});
