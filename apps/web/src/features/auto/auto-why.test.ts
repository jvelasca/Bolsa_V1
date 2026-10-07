/**
 * AUTO UI REFACTOR 4.0 (P2) — explicación «¿Por qué?» tri-estado.
 */

import { describe, expect, it } from "vitest";
import { buildAutoHumanState } from "@/features/auto/auto-human-state";
import { buildAutoStateWhy } from "@/features/auto/auto-why";

const FULL_ACTIVITY = {
  currentActivityMeasurement: "COMPLETE",
  currentActivityAtMeasurement: "COMPLETE",
  currentActivityAt: "2026-10-06T09:42:00Z",
  asOf: "2026-10-06T09:43:00Z",
};

describe("buildAutoStateWhy", () => {
  it("en ESPERANDO explica que esperar es un resultado válido", () => {
    const header = {
      state: "RUNNING",
      currentActivity: "WAITING_SIGNAL",
      ...FULL_ACTIVITY,
    };
    const why = buildAutoStateWhy({
      state: buildAutoHumanState({ header }),
      header,
      riskOperationalState: "OK",
      hasOperationsInCourse: false,
    });
    expect(why.conclusion).toContain("esperar");
    const oportunidad = why.reasons.find((r) =>
      r.label.includes("Oportunidad"),
    );
    expect(oportunidad?.status).toBe("no");
    expect(oportunidad?.detail).toBe("Todavía no hay señal");
  });

  it("un hueco de medición es `unknown`, nunca `no`", () => {
    const why = buildAutoStateWhy({
      state: buildAutoHumanState({ header: { state: "RUNNING" } }),
      header: { state: "RUNNING" },
      riskOperationalState: null,
    });
    expect(
      why.reasons.find((r) => r.label === "Datos del mercado al día")?.status,
    ).toBe("unknown");
    expect(
      why.reasons.find((r) => r.label === "Riesgo aceptable")?.status,
    ).toBe("unknown");
  });

  it("riesgo BLOCKED se marca `no` con motivo", () => {
    const header = { state: "RUNNING" };
    const why = buildAutoStateWhy({
      state: buildAutoHumanState({ header }),
      header,
      riskOperationalState: "BLOCKED",
    });
    const riesgo = why.reasons.find((r) => r.label === "Riesgo aceptable");
    expect(riesgo?.status).toBe("no");
    expect(riesgo?.detail).toBe("Entradas bloqueadas");
  });

  it("un token de motor desconocido es `unknown`", () => {
    const why = buildAutoStateWhy({
      state: buildAutoHumanState({ header: { state: "SOMETHING_NEW" } }),
      header: { state: "SOMETHING_NEW" },
    });
    expect(
      why.reasons.find((r) => r.label === "Motor de AUTO medido")?.status,
    ).toBe("unknown");
  });
});
