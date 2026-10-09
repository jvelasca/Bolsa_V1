/**
 * PAPER-1 — regresión falsable del contrato de confirmación PAPER.
 *
 * Invariantes cubiertos:
 * 1. Nunca se emite la confirmación reservada (`NO_CONFIRMED` invariante, también con TODO cumplido).
 * 2. `UNKNOWN ≠ 0`: sin entradas todo es «Sin dato todavía», jamás un cero ni un criterio cumplido.
 * 3. Un criterio con dato ausente NO se marca cumplido.
 * 4. El módulo no conoce ninguna identidad ajena (p. ej. `SAME_CONFIRMED` de Trading).
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { absentDataLabel } from "@/components/absent-data";
import {
  buildPaperConfirmationVerdict,
  PAPER_CONFIRMATION_CRITERION_ORDER,
  type PaperConfirmationContractInput,
} from "@/features/auto-monitor/paper-confirmation-contract";

const UNMEASURED = absentDataLabel();

/** Material que cumple los SIETE criterios (la promoción SÍ está reservada aun así). */
const ALL_MET: PaperConfirmationContractInput = {
  window: { loaded: true, days: 5, episodes: 3 },
  operations: { loaded: true, operations: 32, withCycleLineage: 32 },
  executions: { loaded: true, fills: 64, attributed: 64 },
  closures: { loaded: true, settlements: 32, reconciled: 32 },
  costs: { loaded: true, expected: 32, complete: 32 },
  results: { loaded: true, withMeasuredResult: 32, contradictions: 0 },
};

const NO_INPUT: PaperConfirmationContractInput = {
  window: null,
  operations: null,
  executions: null,
  closures: null,
  costs: null,
  results: null,
};

function criterionOf(
  result: ReturnType<typeof buildPaperConfirmationVerdict>,
  id: string,
) {
  const criterion = result.criteria.find((item) => item.id === id);
  if (!criterion) throw new Error(`criterio no encontrado: ${id}`);
  return criterion;
}

describe("buildPaperConfirmationVerdict · nunca confirma", () => {
  it("devuelve NO_CONFIRMED con TODOS los criterios cumplidos", () => {
    const result = buildPaperConfirmationVerdict(ALL_MET);
    expect(result.verdict).toBe("NO_CONFIRMED");
    expect(result.criteria.every((item) => item.status === "met")).toBe(true);
    expect(result.unmetOrUnmeasuredCriterionIds).toEqual([]);
    expect(/\bCONFIRMED\b/.test(JSON.stringify(result))).toBe(false);
  });

  it("mantiene NO_CONFIRMED sin ninguna entrada", () => {
    const result = buildPaperConfirmationVerdict(NO_INPUT);
    expect(result.verdict).toBe("NO_CONFIRMED");
    expect(/\bCONFIRMED\b/.test(JSON.stringify(result))).toBe(false);
  });

  it("el word-boundary distingue el token reservado del rótulo permitido", () => {
    expect(/\bCONFIRMED\b/.test("CONFIRMED")).toBe(true);
    expect(/\bCONFIRMED\b/.test("NO_CONFIRMADO")).toBe(false);
    expect(/\bCONFIRMED\b/.test("NO_CONFIRMED")).toBe(false);
  });
});

describe("buildPaperConfirmationVerdict · UNKNOWN != 0", () => {
  it("sin entradas, los siete criterios quedan «Sin dato todavía»", () => {
    const result = buildPaperConfirmationVerdict(NO_INPUT);
    expect(result.criteria.map((item) => item.id)).toEqual([
      ...PAPER_CONFIRMATION_CRITERION_ORDER,
    ]);
    for (const item of result.criteria) {
      expect(item.status).toBe("unknown");
      expect(item.statusLabel).toBe(UNMEASURED);
      expect(item.reason).not.toBeNull();
    }
    expect(result.unknownCriterionIds).toHaveLength(
      PAPER_CONFIRMATION_CRITERION_ORDER.length,
    );
    expect(result.metCriterionIds).toEqual([]);
  });

  it("no colapsa un hueco a cero en la medición humanizada", () => {
    const result = buildPaperConfirmationVerdict(NO_INPUT);
    for (const item of result.criteria) {
      expect(item.measurement ?? "").not.toMatch(/\b0\b/);
    }
  });

  it("un dato ausente NO se marca cumplido", () => {
    const result = buildPaperConfirmationVerdict({
      ...ALL_MET,
      operations: { loaded: true, operations: 32, withCycleLineage: null },
    });
    const lineage = criterionOf(result, "operation_lineage");
    expect(lineage.status).toBe("unknown");
    expect(lineage.statusLabel).toBe(UNMEASURED);
    expect(result.metCriterionIds).not.toContain("operation_lineage");
  });

  it("un criterio medido pero insuficiente se declara incumplido, no sin dato", () => {
    const result = buildPaperConfirmationVerdict({
      ...ALL_MET,
      closures: { loaded: true, settlements: 5, reconciled: 5 },
    });
    const closures = criterionOf(result, "closure_reconciliation");
    expect(closures.status).toBe("unmet");
    expect(closures.statusLabel).toBe("Incumplido");
    expect(result.unmetCriterionIds).toContain("closure_reconciliation");
    expect(result.unknownCriterionIds).not.toContain("closure_reconciliation");
  });
});

describe("buildPaperConfirmationVerdict · no promoción ni identidad ajena", () => {
  it("el constructor no conoce el lens SAME_CONFIRMED de Trading", () => {
    const source = readFileSync(
      resolve(
        process.cwd(),
        "src/features/auto-monitor/paper-confirmation-contract.ts",
      ),
      "utf8",
    );
    expect(source.includes("SAME_CONFIRMED")).toBe(false);
    expect(/["']CONFIRMED["']/.test(source)).toBe(false);
  });

  it("el vocabulario de primer nivel no filtra tokens de motor", () => {
    const result = buildPaperConfirmationVerdict(ALL_MET);
    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain("auto_cycle_settlement");
    expect(serialized).not.toContain("sim_fill_finance_context");
    expect(serialized).not.toContain("OOS_SUPPORTED");
  });
});
