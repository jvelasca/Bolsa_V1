/**
 * V2.x — Operator cabin projection tests.
 */

import { describe, expect, it } from "vitest";
import { buildPaperAutoPosture } from "./paper-auto-posture.js";
import {
  buildOperatorAutoChecklist,
  buildOperatorAutoPlanPreview,
  buildOperatorDecision,
  buildOperatorFourAnswers,
  buildOperatorMissionSteps,
  buildOperatorNextActionFromCockpitPhase,
  buildOperatorNextActionFromEntry,
  buildOperatorNextActionFromPosition,
  buildOperatorPositionPlan,
  buildOperatorProtectionState,
  buildOperatorRiskBox,
  mesaNextActionFromOperatorDecision,
  operatorStageFromCockpitPhase,
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
      phase: "prepared",
      phaseLabel: "Preparada",
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
    expiryLabel: null,
    ...overrides,
  };
}

describe("operatorStageFromCockpitPhase", () => {
  it("maps SEMI phases to operator journey stages", () => {
    expect(operatorStageFromCockpitPhase("vigilar")).toBe("estudio");
    expect(operatorStageFromCockpitPhase("preparada")).toBe("oportunidad");
    expect(operatorStageFromCockpitPhase("disparada")).toBe("trigger");
    expect(operatorStageFromCockpitPhase("propuesta")).toBe("entrada");
    expect(operatorStageFromCockpitPhase("posicion")).toBe("posicion");
  });
});

describe("buildOperatorNextActionFromCockpitPhase", () => {
  it("vigilar / descubierto expose operator NEXT ACTION without COMPRAR", () => {
    const vigilar = buildOperatorNextActionFromCockpitPhase("vigilar");
    expect(vigilar.title).toBe("VIGILAR");
    expect(vigilar.title).not.toMatch(/COMPRAR/i);
    expect(vigilar.ctaHint).not.toMatch(/COMPRAR|BUY/i);
    const descubierto = buildOperatorNextActionFromCockpitPhase("descubierto");
    expect(descubierto.title).toBe("CANDIDATO");
    expect(descubierto.ctaHint).not.toMatch(/COMPRAR|BUY/i);
  });
});

describe("buildOperatorNextActionFromEntry", () => {
  it("preparada → ESPERAR TRIGGER (no COMPRAR)", () => {
    const next = buildOperatorNextActionFromEntry(entryTruth("preparada"));
    expect(next.title).toBe("ESPERAR TRIGGER");
    expect(next.tone).toBe("wait_trigger");
    expect(next.ctaHint).not.toMatch(/COMPRAR|BUY|EJECUTAR/i);
  });

  it("disparada → ENTRADA LISTA + Confirm hint", () => {
    const next = buildOperatorNextActionFromEntry(entryTruth("disparada"));
    expect(next.title).toBe("ENTRADA LISTA");
    expect(next.tone).toBe("entry_ready");
    expect(next.ctaHint).toMatch(/Revisar y confirmar/i);
    expect(next.ctaHint).not.toMatch(/COMPRAR/i);
  });

  it("AUTO disparada + exec off → honesty without COMPRAR", () => {
    const posture = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: false,
    });
    const next = buildOperatorNextActionFromEntry(
      entryTruth("disparada", {
        primaryCta: { kind: "none", label: "AUTO armado · ejecución off" },
      }),
      { paperAuto: posture },
    );
    expect(next.title).toBe("ENTRADA LISTA");
    expect(next.ctaHint).toMatch(/Armado ≠ ejecución|ejecución/i);
    expect(JSON.stringify(next)).not.toMatch(/COMPRAR|BUY/i);
  });
});

describe("buildOperatorNextActionFromPosition", () => {
  it("MANTENER / PROTEGER / SALIR tones", () => {
    expect(buildOperatorNextActionFromPosition("MANTENER").title).toBe(
      "MANTENER",
    );
    expect(buildOperatorNextActionFromPosition("SUBIR_STOP").tone).toBe(
      "protect",
    );
    expect(buildOperatorNextActionFromPosition("SALIR").tone).toBe("exit");
  });
});

describe("resolveOperatorNextAction facade V2.11", () => {
  it("entry preparada enriches condition + expires", () => {
    const next = resolveOperatorNextAction({
      kind: "entry",
      truth: entryTruth("preparada", { expiryLabel: "06 SEP 18:00" }),
    });
    expect(next.title).toBe("ESPERAR TRIGGER");
    expect(next.condition).toMatch(/184\.20/);
    expect(next.expires).toBe("06 SEP 18:00");
  });

  it("cockpit phase delegates", () => {
    const next = resolveOperatorNextAction({
      kind: "cockpit_phase",
      phase: "vigilar",
    });
    expect(next.title).toBe("VIGILAR");
  });
});

describe("buildOperatorRiskBox V2.12 sizing", () => {
  it("fills quantity / positionValue / stopDistancePct", () => {
    const box = buildOperatorRiskBox({
      entry: 100,
      stop: 95,
      quantity: 10,
      maxLoss: 50,
    });
    expect(box.quantity).toBe(10);
    expect(box.positionValue).toBe(1000);
    expect(box.stopDistancePct).toBe(5);
  });
});

describe("buildOperatorFourAnswers + risk box", () => {
  it("exposes thesis/trigger/risk/plan", () => {
    const a = buildOperatorFourAnswers({
      phase: "preparada",
      thesisSummary: "Alcista fuerte",
      entry: 184.2,
      stop: 176.8,
      riskAmount: 400,
      riskR: 0.8,
      target1: 195,
      target2: 205,
    });
    expect(a.thesis).toMatch(/Alcista/);
    expect(a.trigger).toMatch(/Esperar/);
    expect(a.risk).toMatch(/176\.80/);
    expect(a.plan).toMatch(/T1/);
  });

  it("derives R/R without schema", () => {
    const box = buildOperatorRiskBox({
      capital: 50_000,
      riskPct: 0.8,
      maxLoss: 400,
      entry: 184.2,
      stop: 176.8,
      lossAtStop: 400,
      target1: 195,
      target2: 205,
    });
    expect(box.rrT1).toBeGreaterThan(1);
    expect(box.rrT2).toBeGreaterThan(box.rrT1!);
  });
});

describe("mission + AUTO checklist", () => {
  it("builds mission steps from journey", () => {
    const journey = {
      entry: 100,
      risk: {
        initialRisk: 50,
        initialStop: 95,
        currentProtected: 10,
        realizedR: 1,
        unrealizedR: 0.5,
        remainingQuantity: 8,
      },
      t1: {
        trigger: 110,
        status: "executed",
        qtyFractionPct: 30,
        executed: true,
      },
      t2: {
        trigger: 120,
        status: "pending",
        qtyFractionPct: 30,
        executed: false,
      },
      trail: {
        active: true,
        activationEligible: true,
        currentStop: 102,
        lastRatchet: null,
        trailWidth: "medium",
      },
      remainingQuantity: 8,
      primaryAction: "MANTENER",
      stageLabel: "Trailing",
      stageMachine: "trailing",
      lineagePathLabel: "trail",
      logHasT2Executed: false,
      logHasTrailApplied: true,
      eventKinds: [],
      autoPosture: null,
      killOn: false,
    } as PositionJourneyReadoutV1;
    const steps = buildOperatorMissionSteps(journey);
    expect(steps.find((s) => s.id === "t1")?.status).toBe("done");
    expect(steps.find((s) => s.id === "trail")?.status).toBe("active");
  });

  it("AUTO checklist uses operator language", () => {
    const posture = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: false,
    });
    const c = buildOperatorAutoChecklist({
      posture,
      templateId: "moderate",
      killOn: false,
    });
    expect(c.autonomyLabel).toBe("Automático");
    expect(c.interveneHint).toMatch(/intervenir/i);
    expect(c.honestyLine).not.toMatch(/PAPER_D_EXECUTE/);
    expect(c.profilePreview).toMatch(/Moderado/);
  });
});

describe("V2.19–V2.22 OperatorDecision + protection + remaining", () => {
  const protectedJourney = {
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
    primaryAction: "MANTENER",
    stageLabel: null,
    stageMachine: null,
    lineagePathLabel: null,
    logHasT2Executed: false,
    logHasTrailApplied: false,
    eventKinds: [],
    autoPosture: null,
    killOn: false,
  } as PositionJourneyReadoutV1;

  it("V2.33 — planned initialStop without ratified stop → MANTENER · Planificado", () => {
    const j = {
      ...protectedJourney,
      trail: { ...protectedJourney.trail, currentStop: null },
    };
    const next = resolveOperatorNextAction({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
    });
    expect(next.title).toBe("MANTENER");
    expect(next.tone).toBe("maintain");
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: j,
    });
    expect(decision.protection.phase).toBe("planned");
  });

  it("persistSkipped → PROTEGER never MANTENER", () => {
    const next = resolveOperatorNextAction({
      kind: "position",
      primaryAction: "MANTENER",
      journey: protectedJourney,
      persistSkipped: true,
    });
    expect(next.title).toBe("PROTEGER");
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: protectedJourney,
      persistSkipped: true,
    });
    expect(decision.protection.kind).toBe("none");
    expect(decision.protection.honesty).toBe("sent");
    expect(mesaNextActionFromOperatorDecision(decision).kind).toBe("protect");
  });

  it("executed technical stop (protect revision) → Protegida + MANTENER", () => {
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: protectedJourney,
      hasProtectRevision: true,
    });
    expect(decision.currentAction.title).toBe("MANTENER");
    expect(decision.protection.kind).toBe("technical");
    expect(decision.protection.honesty).toBe("confirmed");
    expect(
      decision.currentAction.reasons?.some((r) => r.id === "stop" && r.ok),
    ).toBe(true);
    expect(decision.currentAction.nextChange).toMatch(/T1 @/);
  });

  it("bootstrap protectKind with executed stop → emergency not technical", () => {
    const decision = buildOperatorDecision({
      kind: "position",
      primaryAction: "MANTENER",
      journey: {
        ...protectedJourney,
        trail: { ...protectedJourney.trail, currentStop: 174.99 },
      },
      protectKind: "bootstrap",
      entry: 184.2,
    });
    expect(decision.protection.kind).toBe("emergency");
    expect(decision.protection.isTechnical).toBe(false);
    expect(decision.protection.label).toMatch(/emergencia/i);
  });

  it("entry ESPERAR TRIGGER exposes Porque + nextChange", () => {
    const next = resolveOperatorNextAction({
      kind: "entry",
      truth: entryTruth("preparada", { expiryLabel: "06 SEP" }),
    });
    expect(next.reasons?.map((r) => r.id)).toEqual(["setup", "risk"]);
    expect(next.nextChange).toMatch(/cierre >/);
  });

  it("AUTO preview remaining + ExitPolicy percents", () => {
    const next = resolveOperatorNextAction({
      kind: "position",
      primaryAction: "MANTENER",
      journey: {
        ...protectedJourney,
        remainingQuantity: 43,
        t1: { ...protectedJourney.t1, executed: true, status: "executed" },
      },
    });
    const preview = buildOperatorAutoPlanPreview({
      journey: {
        ...protectedJourney,
        remainingQuantity: 43,
        t1: { ...protectedJourney.t1, executed: true, status: "executed" },
      },
      templateId: "moderate",
      nextAction: next,
      birthQuantity: 62,
    });
    expect(preview.headline).toBe("AUTO HARÁ ESTO");
    expect(preview.t1Pct).toBe(30);
    expect(preview.t2Pct).toBe(30);
    expect(preview.remainingPct).toBeCloseTo(69.4, 0);
    expect(preview.entry).toBe(184.2);
  });

  it("mission includes RESTANTE", () => {
    const steps = buildOperatorMissionSteps(protectedJourney, {
      birthQuantity: 62,
    });
    expect(steps.find((s) => s.id === "remaining")?.detail).toMatch(/100/);
  });

  it("V2.28 PLAN DE LA POSICIÓN fuses mission + remaining", () => {
    const plan = buildOperatorPositionPlan(protectedJourney, {
      birthQuantity: 62,
    });
    expect(plan.steps.map((s) => s.id)).toEqual([
      "entry",
      "protection",
      "t1",
      "t2",
      "trail",
      "exit",
    ]);
    expect(plan.steps.find((s) => s.id === "protection")?.label).toBe(
      "Protección",
    );
    expect(plan.steps.find((s) => s.id === "trail")?.label).toMatch(/Gestión/);
    expect(plan.steps.find((s) => s.id === "exit")?.detail).toMatch(/RESTANTE/);
    expect(plan.remainingPct).toBe(100);
  });

  it("protection state none vs technical", () => {
    expect(buildOperatorProtectionState({ executedStop: null }).kind).toBe(
      "none",
    );
    expect(buildOperatorProtectionState({ executedStop: null }).phase).toBe(
      "none",
    );
    expect(
      buildOperatorProtectionState({ executedStop: 176.8, protectKind: "plan" })
        .kind,
    ).toBe("technical");
    expect(
      buildOperatorProtectionState({ executedStop: 176.8, protectKind: "plan" })
        .phase,
    ).toBe("protected");
  });

  it("V2.29 planned stop → Planificado, executed → Protegido, persist → Enviado", () => {
    const planned = buildOperatorProtectionState({
      plannedStop: 176.8,
      executedStop: null,
    });
    expect(planned.kind).toBe("none");
    expect(planned.phase).toBe("planned");
    expect(planned.phaseLabel).toBe("Planificado");
    expect(planned.stop).toBeNull();
    expect(planned.plannedStop).toBe(176.8);

    const protectedState = buildOperatorProtectionState({
      plannedStop: 176.8,
      executedStop: 176.8,
      protectKind: "plan",
    });
    expect(protectedState.phase).toBe("protected");
    expect(protectedState.phaseLabel).toBe("Protegido");
    expect(protectedState.stop).toBe(176.8);

    const sent = buildOperatorProtectionState({
      plannedStop: 176.8,
      executedStop: 176.8,
      persistSkipped: true,
    });
    expect(sent.phase).toBe("sent");
    expect(sent.phaseLabel).toBe("Enviado");
    expect(sent.stop).toBeNull();
  });
});
