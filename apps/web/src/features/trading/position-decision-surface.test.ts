import { describe, expect, it } from "vitest";
import type { PositionOperationalStateV1 } from "@bolsa/shared";
import {
  mapPovPrimaryActionToCtaKind,
  povExecutionStateLabel,
  povOperatingStateHeadline,
  povOperatingStateTone,
} from "@/features/trading/position-decision-surface";
import { formatPovPrimaryActionLabel } from "@/features/trading/use-position-operational-view";

describe("position-decision-surface GP-V161-02/04/05", () => {
  it("GP-V161-02: tone differs by operatingState", () => {
    expect(povOperatingStateTone("PROTECTED")).toBe("emerald");
    expect(povOperatingStateTone("RECONCILIATION_DRIFT")).toBe("rose");
    expect(povOperatingStateTone("T2_READY")).toBe("amber");
  });

  it("GP-V161-04: primary action honesty labels", () => {
    const cases: Array<{
      state: PositionOperationalStateV1;
      action: Parameters<typeof formatPovPrimaryActionLabel>[0];
      label: string;
    }> = [
      { state: "PROTECTED", action: "MANTENER", label: "Mantener" },
      { state: "T1_READY", action: "REDUCIR", label: "Reducir" },
      { state: "EXIT_REQUIRED", action: "SALIR", label: "Salir" },
      {
        state: "RECONCILIATION_DRIFT",
        action: "REVISAR_DATOS_NO_FRESCOS",
        label: "Revisar",
      },
      {
        state: "RECONCILIATION_ERROR",
        action: "BLOQUEADO",
        label: "Revisar",
      },
    ];
    for (const { state, action, label } of cases) {
      expect(formatPovPrimaryActionLabel(action)).toBe(label);
      expect(formatPovPrimaryActionLabel(action)).not.toMatch(/comprar/i);
      expect(mapPovPrimaryActionToCtaKind(action)).not.toBe("watch");
      void state;
    }
  });

  it("GP-V161-05: DECISIÓN vs EJECUCIÓN copy", () => {
    expect(povExecutionStateLabel("PROTECTED", "MANTENER")).toBe(
      "NO REQUERIDA",
    );
    expect(povExecutionStateLabel("T2_READY", "REDUCIR")).toBe("PENDIENTE");
    expect(povExecutionStateLabel("T2_EXECUTED", "MONITOR")).toBe("EJECUTADA");
    expect(povExecutionStateLabel("RECONCILIATION_DRIFT", "BLOQUEADO")).toBe(
      "REVISAR",
    );
    expect(povExecutionStateLabel("RECONCILIATION_ERROR", "BLOQUEADO")).toBe(
      "REVISAR",
    );
  });

  it("headlines are human-readable and do not collapse T2/DRIFT", () => {
    expect(povOperatingStateHeadline("PROTECTED")).toBe("Protegida");
    expect(povOperatingStateHeadline("T2_EXECUTED")).toBe("T2 ejecutado");
    expect(povOperatingStateHeadline("T1_READY")).toBe("Requiere atención");
    expect(povOperatingStateHeadline("EXIT_REQUIRED")).toBe("Salida necesaria");
    expect(povOperatingStateHeadline("RECONCILIATION_DRIFT")).toBe(
      "Recon drift",
    );
    expect(povOperatingStateHeadline("RECONCILIATION_ERROR")).toBe(
      "Recon no disponible",
    );
  });
});
