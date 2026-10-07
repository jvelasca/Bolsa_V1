/**
 * AUTO UI REFACTOR 4.0 (P1) — cinco estados humanos y frase-resumen.
 *
 * Fija el contrato: el estado interno se colapsa, el hueco se declara y «no operar» no se
 * lee como «detenido».
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_HUMAN_STATE_LABEL,
  AUTO_HUMAN_STATE_SENTENCE,
  buildAutoHumanState,
} from "@/features/auto/auto-human-state";

const FULL_ACTIVITY = {
  currentActivityMeasurement: "COMPLETE",
  currentActivityAtMeasurement: "COMPLETE",
  currentActivityAt: "2026-10-06T09:42:00Z",
  asOf: "2026-10-06T09:43:00Z",
};

describe("buildAutoHumanState", () => {
  it("colapsa RUNNING sin fase a FUNCIONANDO", () => {
    const s = buildAutoHumanState({ header: { state: "RUNNING" } });
    expect(s.ready).toBe(true);
    expect(s.id).toBe("working");
    expect(s.label).toBe("FUNCIONANDO");
    expect(s.sentence).toBe(AUTO_HUMAN_STATE_SENTENCE.working);
  });

  it("ANALYZING medido → ANALIZANDO; WAITING_SIGNAL → ESPERANDO (no «parado»)", () => {
    const analyzing = buildAutoHumanState({
      header: {
        state: "RUNNING",
        currentActivity: "ANALYZING",
        ...FULL_ACTIVITY,
      },
    });
    expect(analyzing.id).toBe("analyzing");
    expect(analyzing.label).toBe("ANALIZANDO");

    const waiting = buildAutoHumanState({
      header: {
        state: "RUNNING",
        currentActivity: "WAITING_SIGNAL",
        ...FULL_ACTIVITY,
      },
    });
    expect(waiting.id).toBe("waiting");
    expect(waiting.label).toBe("ESPERANDO");
    expect(waiting.sentence).toContain("no significa que esté parado");
  });

  it("PAUSED → DETENIDO; BLOCKED → ATENCIÓN", () => {
    expect(buildAutoHumanState({ header: { state: "PAUSED" } }).label).toBe(
      AUTO_HUMAN_STATE_LABEL.stopped,
    );
    expect(buildAutoHumanState({ header: { state: "BLOCKED" } }).label).toBe(
      AUTO_HUMAN_STATE_LABEL.attention,
    );
  });

  it("la integridad financiera DEGRADED/BLOCKED eleva a ATENCIÓN", () => {
    const degraded = buildAutoHumanState({
      header: { state: "RUNNING" },
      riskOperationalState: "DEGRADED",
    });
    expect(degraded.id).toBe("attention");
    const blocked = buildAutoHumanState({
      header: { state: "RUNNING" },
      riskOperationalState: "BLOCKED",
    });
    expect(blocked.id).toBe("attention");
  });

  it("un token de motor desconocido es hueco, nunca verde", () => {
    const s = buildAutoHumanState({ header: { state: "SOMETHING_NEW" } });
    expect(s.ready).toBe(false);
    expect(s.id).toBeNull();
    expect(s.label).toBe("Sin dato todavía");
    expect(s.label).not.toBe(AUTO_HUMAN_STATE_LABEL.working);
  });

  it("sin cabecera (carga/error) es hueco declarado", () => {
    const loading = buildAutoHumanState({ header: null, isLoading: true });
    expect(loading.ready).toBe(false);
    expect(loading.isLoading).toBe(true);

    const error = buildAutoHumanState({ header: null, isError: true });
    expect(error.isError).toBe(true);
    expect(error.sentence).toContain("No se pudo leer");
  });

  it("una actividad vieja no se presenta como actual", () => {
    const stale = buildAutoHumanState({
      header: {
        state: "RUNNING",
        currentActivity: "ANALYZING",
        currentActivityMeasurement: "COMPLETE",
        currentActivityAt: "2026-10-06T09:00:00Z",
        currentActivityAtMeasurement: "COMPLETE",
        asOf: "2026-10-06T10:00:00Z",
      },
    });
    // La fase no es utilizable → cae a FUNCIONANDO (motor RUNNING), no a ANALIZANDO.
    expect(stale.id).toBe("working");
  });
});
