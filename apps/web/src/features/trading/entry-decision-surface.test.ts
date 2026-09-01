import { describe, expect, it } from "vitest";
import type { EntryOperatingPhaseV1 } from "@bolsa/shared";
import {
  entryExecutionStateLabel,
  entryPhaseHeadline,
  entryPhaseTone,
} from "@/features/trading/entry-decision-surface";

describe("entry-decision-surface GP-V162-02/04/05", () => {
  it("GP-V162-02: tone differs by phase", () => {
    expect(entryPhaseTone("preparada")).toBe("sky");
    expect(entryPhaseTone("disparada")).toBe("amber");
    expect(entryPhaseTone("confirmada")).toBe("teal");
    expect(entryPhaseTone("preparada", { entriesBlocked: true })).toBe("rose");
  });

  it("GP-V162-04: primary action honesty labels", () => {
    const cases: Array<{
      phase: EntryOperatingPhaseV1;
      label: string;
    }> = [
      { phase: "preparada", label: "Preparar operación" },
      { phase: "disparada", label: "Revisar y confirmar" },
      { phase: "confirmada", label: "Ver operaciones" },
    ];
    for (const { label } of cases) {
      expect(label).not.toMatch(/comprar/i);
    }
  });

  it("GP-V162-05: DECISIÓN vs EJECUCIÓN copy", () => {
    expect(
      entryExecutionStateLabel("preparada", {
        kind: "prepare",
        label: "Preparar operación",
      }),
    ).toBe("NO REQUERIDA");
    expect(
      entryExecutionStateLabel("disparada", {
        kind: "review_confirm",
        label: "Revisar y confirmar",
      }),
    ).toBe("PENDIENTE");
    expect(
      entryExecutionStateLabel(
        "confirmada",
        { kind: "view_operations", label: "Ver operaciones" },
        { lifecycle: "filled", orderState: "filled", source: "none" } as never,
      ),
    ).toBe("EJECUTADA");
  });

  it("headlines are human-readable", () => {
    expect(entryPhaseHeadline("preparada")).toBe("Entrada preparada");
    expect(entryPhaseHeadline("disparada")).toBe("Disparo activo");
    expect(entryPhaseHeadline("confirmada")).toBe("En ejecución");
  });
});
