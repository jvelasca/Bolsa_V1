/**
 * PAPER-2 — mapeo DTO durable → hechos del contrato PAPER (PURO).
 *
 * Une la superficie de datos (``AutoPaperEvidenceDto``: los siete criterios ya evaluados por el
 * adaptador read-only del backend) con el read-model puro del contrato
 * (`paper-confirmation-contract.ts`). Aquí **no** se evalúa ningún criterio: solo se traducen los
 * contadores nullable a los hechos normalizados, preservando la ausencia como ``null``
 * (`UNKNOWN ≠ 0`). El veredicto y la copy siguen siendo responsabilidad ÚNICA de
 * `buildPaperConfirmationVerdict`, que nunca emite la confirmación.
 *
 * Regla dura: un contador ausente viaja ``null`` — jamás ``0`` — y los ``loaded`` salen de la
 * conciliación del backend (``fillsLoaded``/``settlementsLoaded``), no de la mera presencia del
 * bloque: un bloque vacío por fallo de lectura NO es un material limpio.
 *
 * @see apps/api-python/src/bolsa_api/api/v1/routes/auto_paper_evidence.py
 * @see apps/web/src/features/auto-monitor/paper-confirmation-contract.ts
 */

import type { components } from "@/api/schema";
import {
  buildPaperConfirmationVerdict,
  type PaperConfirmationContractInput,
  type PaperConfirmationVerdictV1,
} from "./paper-confirmation-contract";

type AutoPaperEvidenceDto = components["schemas"]["AutoPaperEvidenceDto"];
type PaperEvidenceCriterionDto =
  components["schemas"]["PaperEvidenceCriterionDto"];

/** Número medido o `null`; nunca colapsa ausencia a `0`. */
function num(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function criterionById(
  criteria: readonly PaperEvidenceCriterionDto[],
  id: string,
): PaperEvidenceCriterionDto | null {
  return criteria.find((item) => item.id === id) ?? null;
}

function count(
  criterion: PaperEvidenceCriterionDto | null,
  key: string,
): number | null {
  return num(criterion?.counts?.[key]);
}

/**
 * Traduce el DTO durable a los hechos del contrato. Los `loaded` provienen de la conciliación
 * (no de la presencia del bloque) para que una lectura fallida se declare «sin dato todavía».
 */
export function paperEvidenceContractInputFromDto(
  dto: AutoPaperEvidenceDto,
): PaperConfirmationContractInput {
  const criteria = dto.criteria ?? [];
  const fillsLoaded = dto.reconciliation?.fillsLoaded === true;
  const settlementsLoaded = dto.reconciliation?.settlementsLoaded === true;
  const resultsLoaded = fillsLoaded && settlementsLoaded;

  const windowCriterion = criterionById(criteria, "window");
  const operationsCriterion = criterionById(criteria, "operation_lineage");
  const executionsCriterion = criterionById(criteria, "execution_attribution");
  const closuresCriterion = criterionById(criteria, "closure_reconciliation");
  const costsCriterion = criterionById(criteria, "cost_coverage");
  const resultsCriterion = criterionById(criteria, "durable_results");
  const nonContradictionCriterion = criterionById(
    criteria,
    "non_contradiction",
  );

  return {
    window: {
      loaded: fillsLoaded,
      days: count(windowCriterion, "days"),
      episodes: count(windowCriterion, "episodes"),
    },
    operations: {
      loaded: fillsLoaded,
      operations: count(operationsCriterion, "operations"),
      withCycleLineage: count(operationsCriterion, "withCycleLineage"),
    },
    executions: {
      loaded: fillsLoaded,
      fills: count(executionsCriterion, "fills"),
      attributed: count(executionsCriterion, "attributed"),
    },
    closures: {
      loaded: settlementsLoaded,
      settlements: count(closuresCriterion, "settlements"),
      reconciled: count(closuresCriterion, "reconciled"),
    },
    costs: {
      loaded: fillsLoaded,
      expected: count(costsCriterion, "expected"),
      complete: count(costsCriterion, "complete"),
    },
    results: {
      loaded: resultsLoaded,
      withMeasuredResult: count(resultsCriterion, "withMeasuredResult"),
      contradictions: count(nonContradictionCriterion, "contradictions"),
    },
  };
}

/** Veredicto reservado a partir del DTO: el constructor del contrato es la única autoridad. */
export function buildPaperEvidenceVerdictFromDto(
  dto: AutoPaperEvidenceDto,
): PaperConfirmationVerdictV1 {
  return buildPaperConfirmationVerdict(paperEvidenceContractInputFromDto(dto));
}
