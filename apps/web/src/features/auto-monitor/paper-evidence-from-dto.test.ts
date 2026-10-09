/**
 * PAPER-2 — mapeo DTO durable → contrato PAPER: invariantes del primer nivel.
 *
 * Fija, sin red ni almacenamiento, lo que el mapeo NO puede romper:
 *
 * 1. Una fuente no cargada o un contador ausente viaja `null` y deja el criterio «sin dato
 *    todavía» (`UNKNOWN ≠ 0`): nunca se colapsa a `0` ni a «Cumplido».
 * 2. Un bloque medido pero por debajo del mínimo declarado es «Incumplido», no «Cumplido».
 * 3. Aunque los SIETE criterios se cumplan, el veredicto sigue siendo `NO_CONFIRMED`: el token
 *    reservado no aparece suelto en el resultado.
 */

import { describe, expect, it } from "vitest";
import type { components } from "@/api/schema";
import {
  buildPaperEvidenceVerdictFromDto,
  paperEvidenceContractInputFromDto,
} from "./paper-evidence-from-dto";
import type { PaperConfirmationCriterionStatus } from "./paper-confirmation-contract";

type AutoPaperEvidenceDto = components["schemas"]["AutoPaperEvidenceDto"];
type PaperEvidenceCriterionDto =
  components["schemas"]["PaperEvidenceCriterionDto"];

const ALL_IDS = [
  "window",
  "operation_lineage",
  "execution_attribution",
  "closure_reconciliation",
  "cost_coverage",
  "durable_results",
  "non_contradiction",
] as const;

function criterion(
  id: string,
  counts: Record<string, number | null> = {},
): PaperEvidenceCriterionDto {
  return {
    id,
    status: "unknown",
    measurement: "",
    source: "test",
    counts,
    notes: [],
  };
}

function makeDto(overrides: {
  criteria?: PaperEvidenceCriterionDto[];
  fillsLoaded?: boolean;
  settlementsLoaded?: boolean;
}): AutoPaperEvidenceDto {
  return {
    schemaVersion: "paper_evidence_adapter_v1",
    readOnly: true,
    verdict: "NO_CONFIRMED",
    criteria: overrides.criteria ?? ALL_IDS.map((id) => criterion(id)),
    reconciliation: {
      fillsLoaded: overrides.fillsLoaded ?? false,
      settlementsLoaded: overrides.settlementsLoaded ?? false,
      fillsTotal: 0,
      fillsWithCycle: 0,
      duplicateExecutions: 0,
      orphanExecutions: 0,
      closedCycles: 0,
      anonymousClosedCycles: 0,
      windowDays: null,
      windowEpisodes: null,
      settlementsTotal: 0,
      settlementsReconciled: 0,
      settlementsDivergent: 0,
      settlementsUnmatched: 0,
      cycles: [],
      contradictions: [],
      notes: [],
    },
  } as unknown as AutoPaperEvidenceDto;
}

function statusById(
  dto: AutoPaperEvidenceDto,
  id: string,
): PaperConfirmationCriterionStatus {
  const verdict = buildPaperEvidenceVerdictFromDto(dto);
  const found = verdict.criteria.find((item) => item.id === id);
  if (!found) throw new Error(`criterio ausente: ${id}`);
  return found.status;
}

describe("paper-evidence-from-dto", () => {
  it("keeps absence as null and never promotes it to met", () => {
    const input = paperEvidenceContractInputFromDto(makeDto({}));

    expect(input.window?.loaded).toBe(false);
    expect(input.window?.days).toBeNull();
    expect(input.results?.contradictions).toBeNull();

    const verdict = buildPaperEvidenceVerdictFromDto(makeDto({}));
    expect(verdict.verdict).toBe("NO_CONFIRMED");
    expect(verdict.criteria.every((item) => item.status === "unknown")).toBe(
      true,
    );
  });

  it("marks a measured block below the minimum as unmet, not met", () => {
    const dto = makeDto({
      fillsLoaded: true,
      settlementsLoaded: true,
      criteria: [
        criterion("closure_reconciliation", {
          settlements: 5,
          reconciled: 5,
          divergent: 0,
          unmatched: 0,
        }),
      ],
    });

    expect(statusById(dto, "closure_reconciliation")).toBe("unmet");
  });

  it("keeps a criterion unknown when a required count is missing", () => {
    const dto = makeDto({
      fillsLoaded: true,
      settlementsLoaded: true,
      criteria: [criterion("window", { days: 10, episodes: null })],
    });

    expect(statusById(dto, "window")).toBe("unknown");
  });

  it("never emits the reserved confirmation even when all seven criteria are met", () => {
    const dto = makeDto({
      fillsLoaded: true,
      settlementsLoaded: true,
      criteria: [
        criterion("window", { days: 10, episodes: 3 }),
        criterion("operation_lineage", {
          operations: 40,
          withCycleLineage: 40,
        }),
        criterion("execution_attribution", { fills: 80, attributed: 80 }),
        criterion("closure_reconciliation", {
          settlements: 40,
          reconciled: 40,
        }),
        criterion("cost_coverage", { expected: 40, complete: 40 }),
        criterion("durable_results", { withMeasuredResult: 40 }),
        criterion("non_contradiction", { contradictions: 0 }),
      ],
    });

    const verdict = buildPaperEvidenceVerdictFromDto(dto);
    expect(verdict.criteria.every((item) => item.status === "met")).toBe(true);
    expect(verdict.verdict).toBe("NO_CONFIRMED");
    expect(/\bCONFIRMED\b/.test(JSON.stringify(verdict))).toBe(false);
  });
});
