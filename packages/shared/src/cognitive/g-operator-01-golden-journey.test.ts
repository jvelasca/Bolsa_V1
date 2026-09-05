/**
 * G-OPERATOR-01 — Golden Operator Journey (V2.15).
 * Matrix: WAIT_TRIGGER → ENTRY_READY → OPEN unprotected → PROTECTED → T1 → TRAIL → T2 → EXIT
 * Asserts NEXT ACTION · Risk Box · Mission · AUTO preview · chart kinds per stage.
 * Projection-only — not a second FSM.
 */

import { describe, expect, it } from "vitest";
import { buildPaperAutoPosture } from "./paper-auto-posture.js";
import {
  buildOperatorAutoPlanPreview,
  buildOperatorDecision,
  buildOperatorMissionSteps,
  buildOperatorRiskBox,
  buildPositionReductionReadout,
  mesaNextActionFromOperatorDecision,
  resolveOperatorNextAction,
} from "./operator-cabin-view.js";
import type { EntryOperatingTruthV1 } from "./entry-operating-truth.js";
import type { PositionJourneyReadoutV1 } from "./position-journey-readout.js";

function entryTruth(
  phase: EntryOperatingTruthV1["phase"],
  overrides: Partial<EntryOperatingTruthV1> = {},
): EntryOperatingTruthV1 {
  return {
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    asOf: "2026-09-04T10:00:00.000Z",
    phase,
    phaseLabel: phase,
    triggerLabel: phase === "preparada" ? "Pendiente" : "Disparado",
    phrase: "test",
    primaryCta: {
      kind:
        phase === "preparada"
          ? "prepare"
          : phase === "confirmada"
            ? "view_operations"
            : "review_confirm",
      label:
        phase === "preparada"
          ? "Preparar operación"
          : phase === "confirmada"
            ? "Ver operaciones"
            : "Revisar y confirmar",
    },
    plan: {
      phase: phase === "preparada" ? "prepared" : "triggered",
      phaseLabel: phase === "preparada" ? "Preparada" : "Disparada",
      direction: "long",
      entry: 184.2,
      stopVigente: 176.8,
      stopInicial: 176.8,
      target1: 195,
      target2: 205,
      target1Reached: false,
      target2Reached: false,
      target1Touched: false,
      target1Managed: false,
      target2Touched: false,
      target2Managed: false,
      expectedRR: 1.46,
      riskR: 0.8,
      currentPrice: 183.5,
      unrealizedR: null,
      trailingActive: false,
      trailingPeakMfeR: null,
      trailingPeakPrice: null,
      trailingStopHint: null,
      trailingDistanceR: null,
      exitAuthorityHint: null,
      hasPlan: true,
      emptyCopy: "",
    },
    sizing: {
      quantity: 62,
      riskAmount: 400,
      expectedRR: 1.46,
      riskR: 0.8,
      positionValue: 11420,
    },
    entriesBlocked: false,
    gateStatus: null,
    expiryLabel: "06 SEP 18:00",
    ...overrides,
  };
}

function journey(
  partial: Partial<PositionJourneyReadoutV1> & {
    primaryAction: PositionJourneyReadoutV1["primaryAction"];
  },
): PositionJourneyReadoutV1 {
  return {
    entry: 184.2,
    risk: {
      initialRisk: 400,
      initialStop: 176.8,
      currentProtected: 50,
      realizedR: 0,
      unrealizedR: 0.2,
      remainingQuantity: 62,
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
      currentStop: 176.8,
      lastRatchet: null,
      trailWidth: "medium",
    },
    remainingQuantity: 62,
    stageLabel: null,
    stageMachine: null,
    lineagePathLabel: null,
    logHasT2Executed: false,
    logHasTrailApplied: false,
    eventKinds: [],
    autoPosture: null,
    killOn: false,
    ...partial,
  };
}

describe("G-OPERATOR-01 Golden Operator Journey", () => {
  it("WAIT_TRIGGER — NEXT ACTION + condition + expires + risk sizing", () => {
    const truth = entryTruth("preparada");
    const next = resolveOperatorNextAction({ kind: "entry", truth });
    expect(next.title).toBe("ESPERAR TRIGGER");
    expect(next.tone).toBe("wait_trigger");
    expect(next.condition).toMatch(/cierre > 184\.20/i);
    expect(next.expires).toMatch(/06 SEP/);
    expect(next.levels?.entry).toBe(184.2);
    expect(next.levels?.stop).toBe(176.8);
    const box = buildOperatorRiskBox({
      entry: 184.2,
      stop: 176.8,
      quantity: 62,
      positionValue: 11420,
      maxLoss: 400,
      target1: 195,
      target2: 205,
    });
    expect(box.quantity).toBe(62);
    expect(box.positionValue).toBe(11420);
    expect(box.stopDistancePct).toBeGreaterThan(0);
  });

  it("ENTRY_READY — Confirm hint, no COMPRAR", () => {
    const next = resolveOperatorNextAction({
      kind: "entry",
      truth: entryTruth("disparada"),
    });
    expect(next.title).toBe("ENTRADA LISTA");
    expect(next.tone).toBe("entry_ready");
    expect(next.ctaHint).toMatch(/Revisar y confirmar/i);
    expect(JSON.stringify(next)).not.toMatch(/COMPRAR|BUY/i);
  });

  it("OPEN unprotected — PROTEGER emergency, not MANTENER", () => {
    const j = journey({
      primaryAction: "MANTENER",
      risk: {
        initialRisk: null,
        initialStop: null,
        currentProtected: null,
        realizedR: null,
        unrealizedR: null,
        remainingQuantity: 10,
      },
      trail: {
        active: false,
        activationEligible: false,
        currentStop: null,
        lastRatchet: null,
        trailWidth: null,
      },
      remainingQuantity: 10,
    });
    const next = resolveOperatorNextAction({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
    });
    expect(next.title).toBe("PROTEGER");
    expect(next.tone).toBe("protect");
    expect(next.subtitle).toMatch(/emergencia|−5/i);
    expect(next.condition).toMatch(/emergencia|técnico/i);
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
    });
    expect(decision.protection.kind).toBe("none");
    expect(mesaNextActionFromOperatorDecision(decision).kind).toBe("protect");
  });

  it("PROTECTED — MANTENER + mission + AUTO preview", () => {
    const j = journey({ primaryAction: "MANTENER" });
    const next = resolveOperatorNextAction({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
    });
    expect(next.title).toBe("MANTENER");
    // V2.33 — birth currentStop alone is Planificado; protect revision = Protegido.
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
      hasProtectRevision: true,
    });
    expect(decision.protection.kind).toBe("technical");
    expect(decision.currentAction.reasons?.length).toBeGreaterThan(0);
    const steps = buildOperatorMissionSteps(j);
    expect(steps.find((s) => s.id === "entry")?.status).toBe("done");
    expect(steps.find((s) => s.id === "stop")?.status).toBe("done");
    expect(steps.find((s) => s.id === "t1")?.detail).toMatch(/195/);
    const posture = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: false,
    });
    const preview = buildOperatorAutoPlanPreview({
      journey: j,
      templateId: "moderate",
      nextAction: next,
      posture,
    });
    expect(
      preview.items.some((i) => i.id === "t1" && i.label.includes("30%")),
    ).toBe(true);
    expect(preview.ifReachesLines[0]).toMatch(/195\.00/);
    expect(preview.honestyLine).not.toMatch(/PAPER_D_EXECUTE/);
  });

  it("T1 executed → TRAILING — remaining qty + realized %", () => {
    const j = journey({
      primaryAction: "MANTENER",
      remainingQuantity: 43,
      risk: {
        initialRisk: 400,
        initialStop: 176.8,
        currentProtected: 20,
        realizedR: 1,
        unrealizedR: 0.5,
        remainingQuantity: 43,
      },
      t1: {
        trigger: 195,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      trail: {
        active: true,
        activationEligible: true,
        currentStop: 191.2,
        lastRatchet: null,
        trailWidth: "medium",
      },
    });
    const steps = buildOperatorMissionSteps(j);
    expect(steps.find((s) => s.id === "t1")?.status).toBe("done");
    expect(steps.find((s) => s.id === "trail")?.status).toBe("active");
    const reduction = buildPositionReductionReadout({
      birthQuantity: 62,
      remainingQuantity: 43,
      t1QtyFractionPct: 30,
      t2QtyFractionPct: 30,
    });
    expect(reduction.remainingPct).toBeCloseTo(69.4, 0);
    expect(reduction.realizedPct).toBeCloseTo(30.6, 0);
  });

  it("T2 then EXIT", () => {
    const afterT2 = journey({
      primaryAction: "MANTENER",
      remainingQuantity: 31,
      t1: {
        trigger: 195,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      t2: {
        trigger: 205,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      trail: {
        active: true,
        activationEligible: true,
        currentStop: 200,
        lastRatchet: null,
        trailWidth: "medium",
      },
    });
    expect(
      buildOperatorMissionSteps(afterT2).find((s) => s.id === "t2")?.status,
    ).toBe("done");

    const exit = resolveOperatorNextAction({
      kind: "position",
      primaryAction: "SALIR",
      journey: afterT2,
    });
    expect(exit.title).toBe("SALIR");
    expect(exit.tone).toBe("exit");
  });
});
