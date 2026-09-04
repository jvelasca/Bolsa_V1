/**
 * V2.x — Operator cabin projection tests.
 */

import { describe, expect, it } from "vitest";
import { buildPaperAutoPosture } from "./paper-auto-posture.js";
import {
  buildOperatorAutoChecklist,
  buildOperatorFourAnswers,
  buildOperatorMissionSteps,
  buildOperatorNextActionFromCockpitPhase,
  buildOperatorNextActionFromEntry,
  buildOperatorNextActionFromPosition,
  buildOperatorRiskBox,
  operatorStageFromCockpitPhase,
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
