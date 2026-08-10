/**
 * Regresión: 1 Play debe encadenar Universo → Lab → Coach² → Finalistas
 * sin exigir un 2º click. Caso canónico: GRF (Grifols).
 */

import { describe, expect, it } from "vitest";
import {
  canAutoRunStep,
  emptyAssistantProgress,
  withUniverseDone,
} from "@/features/backtests/backtest-assistant-completion";
import {
  resolveFullCycleSaveDecision,
  shouldAutoHandoffLab,
} from "@/features/backtests/backtest-assistant-full-cycle";
import {
  shouldAdvanceToLab,
  resolveCoachProfilePolicy,
} from "@/features/backtests/coach-profile-policy";
import { runIbex35OperativaAudit } from "@/features/backtests/ibex35-operativa-audit";

describe("Play chain · same-tick progress (double-Play bug)", () => {
  it("stale progress after universe battery blocks semifinal (the bug)", () => {
    // Efecto hacía setState(universeDone) y luego canAutoRunStep(closure stale).
    const staleClosure = emptyAssistantProgress();
    expect(canAutoRunStep("semifinal", staleClosure, true)).toBe(false);
  });

  it("passing withUniverseDone lets the chain continue without 2º Play", () => {
    const next = withUniverseDone(emptyAssistantProgress());
    expect(next.universeDone).toBe(true);
    expect(canAutoRunStep("semifinal", next, true)).toBe(true);
  });
});

describe("Play chain · Lab → Coach² → Finalistas (GRF policy)", () => {
  it("handoff only with mejoras; save only post-lab + canSave", () => {
    expect(
      shouldAutoHandoffLab({
        fullCycleActive: true,
        allZonesDone: true,
        improvedCount: 2,
        alreadyTriggered: false,
      }),
    ).toBe(true);

    expect(
      resolveFullCycleSaveDecision({
        postLab: true,
        labImprovedCount: 2,
        canSaveTop: true,
      }),
    ).toMatchObject({
      action: "save_active",
      reason: expect.stringMatching(/→ Finalistas/),
    });
  });

  it("GRF offline coach audit does not throw and returns a snapshot", () => {
    const report = runIbex35OperativaAudit({ symbols: ["GRF"] });
    expect(report.instrumentCount).toBe(1);
    const snap = report.snapshots.find((s) => s.symbol === "GRF");
    expect(snap).toBeTruthy();
    expect(snap!.slotCount).toBeGreaterThanOrEqual(0);
  });

  it("perfil balanced + confianza consensus avanza a Lab", () => {
    const policy = resolveCoachProfilePolicy({
      profileName: "balanced",
      horizon: "swing",
      riskTolerance: "moderate",
    });
    const gate = shouldAdvanceToLab({
      confidence: "consensus",
      policy,
      labEvenIfWeak: false,
      recommendationCount: 3,
    });
    expect(gate.advance).toBe(true);
  });
});
