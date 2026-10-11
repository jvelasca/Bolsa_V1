import { describe, expect, it } from "vitest";
import {
  DIA_D_CYCLE_VERIFICATION_LABELS,
  resolveDiaDCycleVerificationState,
} from "@/features/auto-monitor/dia-d-cycle-verification-status";

describe("resolveDiaDCycleVerificationState", () => {
  it("declara «Verificación vinculada» solo si hay registro durable", () => {
    expect(
      resolveDiaDCycleVerificationState({ cycleId: "cyc-1", verified: true }),
    ).toBe("linked");
  });

  it("declara «Sin verificación» si el ciclo existe pero no tiene registro", () => {
    expect(
      resolveDiaDCycleVerificationState({ cycleId: "cyc-1", verified: false }),
    ).toBe("not-verified");
  });

  it("declara «Sin dato todavía» si el ciclo no tiene cycleId", () => {
    expect(
      resolveDiaDCycleVerificationState({ cycleId: "", verified: true }),
    ).toBe("unknown");
    expect(
      resolveDiaDCycleVerificationState({ cycleId: null, verified: false }),
    ).toBe("unknown");
  });

  it("expone rótulos honestos (no códigos crudos)", () => {
    expect(DIA_D_CYCLE_VERIFICATION_LABELS.linked).toBe(
      "Verificación vinculada",
    );
    expect(DIA_D_CYCLE_VERIFICATION_LABELS["not-verified"]).toBe(
      "Sin verificación",
    );
    expect(DIA_D_CYCLE_VERIFICATION_LABELS.unknown).toBe("Sin dato todavía");
  });
});
