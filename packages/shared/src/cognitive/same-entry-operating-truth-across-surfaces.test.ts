/**
 * V1.38 — misma entrada → misma EntryOperatingTruth en Mercado / Hoy / Journal.
 */

import { describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  buildEntryOperatingTruth,
  entryOperatingSurfaceSnapshot,
  mesaNextActionFromEntryOperatingTruth,
} from "./entry-operating-truth.js";
import { mapCandidateNextAction } from "./mesa-next-action.js";
import { mercadoCockpitPrimaryCta } from "./mercado-cockpit-phase.js";

const ASOF = "2026-08-31T09:00:00.000Z";

function armedStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "decision_journal_study",
    schemaVersion: 1,
    sessionId: "sess-1",
    decisionId: "dec-1",
    instrumentId: "inst-nvda",
    symbol: "NVDA",
    name: "NVIDIA",
    studiedAt: ASOF,
    ageMs: 0,
    period: "swing",
    timeframe: "D",
    opinion: "bullish",
    status: "active",
    strength: 7.5,
    strengthBand: "high",
    vigencia: null,
    entry: 421.5,
    stop: 408,
    target1: 448,
    target2: 470,
    expectedRR: 2,
    riskAmount: 250,
    quantity: 10,
    initialRiskR: 1,
    positionValue: 4215,
    direction: "long",
    hasOperationalPlan: true,
    userThesis: null,
    decisionSummary: "Breakout con volumen",
    analysisNotes: [],
    trends: [],
    consensus: { total: 0, bullish: 0, neutral: 0, bearish: 0 },
    indicators: { primary: null, confirmation: null },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: "ARMED",
    action: null,
    ...overrides,
  } as DecisionJournalStudyViewV1;
}

function fourSurfaces(study: DecisionJournalStudyViewV1) {
  const input = { study, asOf: ASOF };
  return {
    mercado: buildEntryOperatingTruth(input),
    hoy: buildEntryOperatingTruth(input),
    journal: buildEntryOperatingTruth(input),
    operaciones: buildEntryOperatingTruth(input),
  };
}

describe("sameEntryOperatingTruthAcrossSurfaces V1.38", () => {
  it("ARMED/preparada → misma fase, CTA y niveles en las cuatro superficies", () => {
    const { mercado, hoy, journal, operaciones } = fourSurfaces(armedStudy());
    expect(mercado).not.toBeNull();
    const snap = entryOperatingSurfaceSnapshot(mercado!);
    expect(snap).toEqual({
      phase: "preparada",
      phaseLabel: "Preparada",
      ctaLabel: "Preparar operación",
      ctaKind: "prepare",
      phrase: expect.stringMatching(/Disparador de entrada aún no cruzado/i),
      triggerLabel: "Pendiente",
      entry: 421.5,
      stop: 408,
      target1: 448,
      target2: 470,
      expectedRR: 2,
      riskAmount: 250,
      asOf: ASOF,
    });
    expect(entryOperatingSurfaceSnapshot(hoy!)).toEqual(snap);
    expect(entryOperatingSurfaceSnapshot(journal!)).toEqual(snap);
    expect(entryOperatingSurfaceSnapshot(operaciones!)).toEqual(snap);
    expect(mercadoCockpitPrimaryCta("preparada")).toBe("Preparar operación");
    expect(mesaNextActionFromEntryOperatingTruth(mercado!).label).toBe(
      "Preparar operación",
    );
  });

  it("TRIGGERED/disparada → Revisar y confirmar (no «Confirmar» suelto)", () => {
    const study = armedStudy({ tradePlanStatus: "TRIGGERED" });
    const truth = buildEntryOperatingTruth({ study, asOf: ASOF });
    expect(truth?.phase).toBe("disparada");
    expect(truth?.primaryCta.label).toBe("Revisar y confirmar");
    expect(mercadoCockpitPrimaryCta("disparada")).toBe("Revisar y confirmar");
    const candidate = mapCandidateNextAction(
      { status: "TRIGGERED", study, gate: "PASS" },
      false,
    );
    expect(candidate.label).toBe("Revisar y confirmar");
    expect(candidate.label).not.toBe("Confirmar");
    expect(candidate.allowsEntry).toBe(false);
  });

  it("inConfirmQueue → propuesta con misma CTA en Hoy y Mercado", () => {
    const study = armedStudy({ tradePlanStatus: "TRIGGERED" });
    const truth = buildEntryOperatingTruth({
      study,
      inConfirmQueue: true,
      asOf: ASOF,
    });
    expect(truth?.phase).toBe("propuesta");
    expect(truth?.primaryCta.label).toBe("Revisar y confirmar");
    expect(mercadoCockpitPrimaryCta("propuesta")).toBe("Revisar y confirmar");
  });

  it("orderPendingFill → confirmada", () => {
    const study = armedStudy({ tradePlanStatus: "TRIGGERED" });
    const truth = buildEntryOperatingTruth({
      study,
      orderPendingFill: true,
      asOf: ASOF,
    });
    expect(truth?.phase).toBe("confirmada");
    expect(truth?.primaryCta.label).toBe("Ver operaciones");
    expect(truth?.triggerLabel).toBe("Disparado");
  });

  it("entriesBlocked → CTA bloqueada coherente", () => {
    const study = armedStudy();
    const truth = buildEntryOperatingTruth({
      study,
      entriesBlocked: true,
      asOf: ASOF,
    });
    expect(truth?.primaryCta.kind).toBe("none");
    expect(truth?.phrase).toMatch(/bloqueadas/i);
    const candidate = mapCandidateNextAction(
      { status: "ARMED", study, gate: "PASS" },
      true,
    );
    expect(candidate.label).toBe("Entradas bloqueadas");
  });

  it("open position → null (OperationalTruth gobierna posición)", () => {
    expect(
      buildEntryOperatingTruth({
        study: armedStudy(),
        hasOpenPosition: true,
      }),
    ).toBeNull();
  });

  it("never exposes BUY in CTA labels", () => {
    for (const status of ["ARMED", "TRIGGERED"] as const) {
      const study = armedStudy({ tradePlanStatus: status });
      const truth = buildEntryOperatingTruth({ study });
      expect(truth?.primaryCta.label.toUpperCase()).not.toContain("BUY");
      expect(truth?.primaryCta.label.toUpperCase()).not.toContain("COMPRAR");
    }
  });
});
