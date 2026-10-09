/**
 * PAPER-1 — contrato de confirmación PAPER: read-model PURO de criterios de suficiencia.
 *
 * Cierra el paso 4 de la orden de MIA: **definir** el contrato de la evidencia PAPER durable
 * (operaciones · ejecuciones · cierres · costes · resultados) y **no emitir** la confirmación.
 * Es el precedente obligatorio de `S4` (`dia-d-evidence-aggregate.ts`) aplicado a la capa PAPER:
 * un constructor determinista que evalúa criterios y concluye SIEMPRE `NO_CONFIRMED`.
 *
 * Invariantes (falsables):
 * - **Nunca se emite la confirmación reservada.** `verdict` es un tipo literal
 *   `"NO_CONFIRMED"`: no existe ninguna rama que emita la confirmación ni el token suelto.
 * - **`UNKNOWN ≠ 0`.** Un hueco se rotula «Sin dato todavía» (vocabulario de `absent-data`),
 *   jamás se colapsa a un cero ni a un criterio cumplido.
 * - **Ningún criterio se cumple sin dato.** Una entrada ausente (o no cargada) declara el
 *   criterio «Sin dato todavía», no «Incumplido»: no medido ≠ medido y descartado.
 * - **Ningún criterio aislado confirma.** Aunque TODOS los criterios estén cumplidos, el
 *   veredicto sigue siendo `NO_CONFIRMED`: la promoción queda reservada al humano/contrato.
 * - **Sin identidad ajena.** Este módulo no conoce veredictos de identidad de otras superficies:
 *   sólo evalúa el material PAPER durable que se le describe.
 *
 * Determinista y sin I/O: sin `Date`, sin red, sin almacenamiento (`Δ motor = 0`). El mapeo desde
 * los DTO hasta estos hechos normalizados lo hace el llamante, no este módulo.
 *
 * @see docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md
 * @see docs/PROJECT_PREMISES.md §5.2 (cuatro capas de evidencia · no equivalencias)
 * @see apps/web/src/features/auto-monitor/dia-d-evidence-aggregate.ts (precedente S4)
 */

import {
  PAPER_CONFIRMATION_CRITERION_COPY,
  PAPER_CONFIRMATION_GLOBAL_VERDICT_LABEL,
  PAPER_CONFIRMATION_NON_PROMOTION_NOTE,
  PAPER_CONFIRMATION_RESERVED_REASON,
  PAPER_CONFIRMATION_STATUS_LABELS,
  PAPER_CONFIRMATION_UNMEASURED_NOTE,
} from "./paper-confirmation-contract-labels";

// ---------------------------------------------------------------------------
// Criterios
// ---------------------------------------------------------------------------

/** Criterios de suficiencia del contrato, en orden fijo. */
export type PaperConfirmationCriterionId =
  | "window"
  | "operation_lineage"
  | "execution_attribution"
  | "closure_reconciliation"
  | "cost_coverage"
  | "durable_results"
  | "non_contradiction";

export const PAPER_CONFIRMATION_CRITERION_ORDER: readonly PaperConfirmationCriterionId[] =
  [
    "window",
    "operation_lineage",
    "execution_attribution",
    "closure_reconciliation",
    "cost_coverage",
    "durable_results",
    "non_contradiction",
  ] as const;

/** Estado de un criterio: cumplido · incumplido · sin dato todavía (`UNKNOWN ≠ 0`). */
export type PaperConfirmationCriterionStatus = "met" | "unmet" | "unknown";

// ---------------------------------------------------------------------------
// Umbrales declarados (falsables y parametrizables)
// ---------------------------------------------------------------------------

/** Ventana mínima operativa: `≥4 días` (PROJECT_PREMISES §5.1). */
export const PAPER_CONFIRMATION_MIN_WINDOW_DAYS = 4;

/** Episodios mínimos en la ventana: `≥2` (PROJECT_PREMISES §5.1). */
export const PAPER_CONFIRMATION_MIN_EPISODES = 2;

/**
 * Operaciones cerradas mínimas (ida y vuelta con cantidad balanceada). Toma el mínimo declarado
 * por el protocolo del RUN PAPER (`DEFAULT_MIN_MEASURABLE_CYCLES_PER_STRATEGY`): no se baja para
 * forzar una confirmación.
 */
export const PAPER_CONFIRMATION_MIN_CLOSED_OPERATIONS = 32;

/** Fills durables mínimos (dos patas por operación cerrada). */
export const PAPER_CONFIRMATION_MIN_REQUIRED_FILLS =
  PAPER_CONFIRMATION_MIN_CLOSED_OPERATIONS * 2;

// ---------------------------------------------------------------------------
// Entradas normalizadas (todas nullable: la ausencia se puede declarar)
// ---------------------------------------------------------------------------

/** Ventana operativa declarada. */
export type PaperWindowFacts = {
  /** ¿Respondió la lectura? Si no, el criterio es «Sin dato todavía». */
  loaded: boolean;
  days: number | null;
  episodes: number | null;
};

/** Operaciones (round-trips) que el material declara terminadas. */
export type PaperOperationsFacts = {
  loaded: boolean;
  /** Operaciones cerradas declaradas. */
  operations: number | null;
  /** Operaciones con identidad de ciclo (`cycle_id`) probada. */
  withCycleLineage: number | null;
};

/** Ejecuciones durables (fills) atribuidas a su operación. */
export type PaperExecutionsFacts = {
  loaded: boolean;
  /** Fills durables en la ventana. */
  fills: number | null;
  /** Fills atribuidos a una operación (con linaje de ciclo). */
  attributed: number | null;
};

/** Cierres durables y su reconciliación contra la ida y vuelta del material. */
export type PaperClosuresFacts = {
  loaded: boolean;
  /** Cierres publicados por el registro durable (`auto_cycle_settlement`). */
  settlements: number | null;
  /** Cierres reconciliados contra el round-trip balanceado del material. */
  reconciled: number | null;
};

/** Cobertura de la fricción aplicada (costes). */
export type PaperCostsFacts = {
  loaded: boolean;
  /** Operaciones cerradas que exigen un coste aplicado medido. */
  expected: number | null;
  /** Operaciones cuyo coste aplicado está `COMPLETE` (ni suelo ni parcial). */
  complete: number | null;
};

/** Resultados durables y contradicciones de cierre. */
export type PaperResultsFacts = {
  loaded: boolean;
  /** Cierres con resultado medido `COMPLETE`. */
  withMeasuredResult: number | null;
  /** Cierres que se contradicen entre sí (p. ej. settlement y round-trip discrepantes). */
  contradictions: number | null;
};

/** Hechos de evidencia PAPER durable. Todos los bloques son nullable. */
export type PaperConfirmationContractInput = {
  window: PaperWindowFacts | null;
  operations: PaperOperationsFacts | null;
  executions: PaperExecutionsFacts | null;
  closures: PaperClosuresFacts | null;
  costs: PaperCostsFacts | null;
  results: PaperResultsFacts | null;
};

// ---------------------------------------------------------------------------
// Salidas
// ---------------------------------------------------------------------------

export type PaperConfirmationCriterionV1 = {
  id: PaperConfirmationCriterionId;
  title: string;
  /** Enunciado falsable del criterio (se cumple o no). */
  requirement: string;
  /** Origen durable que lo demuestra, en lenguaje de usuario. */
  sourceLabel: string;
  status: PaperConfirmationCriterionStatus;
  statusLabel: string;
  /** Medición humanizada de primer nivel (o `null` si no aplica). */
  measurement: string | null;
  /** Motivo del hueco o del incumplimiento; `null` si está cumplido. */
  reason: string | null;
};

export type PaperConfirmationVerdictV1 = {
  schemaVersion: "paper_confirmation_contract_v1";
  /** Tipo LITERAL: es el único veredicto que este constructor puede devolver. */
  verdict: "NO_CONFIRMED";
  verdictLabel: string;
  summary: string;
  /** Orden fijo: `PAPER_CONFIRMATION_CRITERION_ORDER`. */
  criteria: readonly PaperConfirmationCriterionV1[];
  metCriterionIds: readonly PaperConfirmationCriterionId[];
  unmetCriterionIds: readonly PaperConfirmationCriterionId[];
  unknownCriterionIds: readonly PaperConfirmationCriterionId[];
  /** Criterios incumplidos O sin medir (lo que impide cerrar el contrato hoy). */
  unmetOrUnmeasuredCriterionIds: readonly PaperConfirmationCriterionId[];
  /** Motivo de por qué la confirmación no se emite (reserva de contrato). */
  confirmationBlockedReason: string;
};

// ---------------------------------------------------------------------------
// Utilidades puras
// ---------------------------------------------------------------------------

/** Número medido o `null`; nunca colapsa ausencia a 0. */
function num(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function part(label: string, value: number | null): string {
  return `${label} ${value ?? PAPER_CONFIRMATION_UNMEASURED_NOTE}`;
}

function criterion(
  id: PaperConfirmationCriterionId,
  status: PaperConfirmationCriterionStatus,
  measurement: string | null,
): PaperConfirmationCriterionV1 {
  const copy = PAPER_CONFIRMATION_CRITERION_COPY[id];
  const reason =
    status === "met"
      ? null
      : status === "unknown"
        ? copy.unknownReason
        : copy.unmetReason;
  return {
    id,
    title: copy.title,
    requirement: copy.requirement,
    sourceLabel: copy.sourceLabel,
    status,
    statusLabel: PAPER_CONFIRMATION_STATUS_LABELS[status],
    measurement,
    reason,
  };
}

// ---------------------------------------------------------------------------
// Evaluación de cada criterio
// ---------------------------------------------------------------------------

function buildWindowCriterion(
  facts: PaperWindowFacts | null,
): PaperConfirmationCriterionV1 {
  const days = num(facts?.days);
  const episodes = num(facts?.episodes);
  const measurement = [part("días", days), part("episodios", episodes)].join(
    " · ",
  );
  if (facts?.loaded !== true || days === null || episodes === null) {
    return criterion("window", "unknown", measurement);
  }
  const met =
    days >= PAPER_CONFIRMATION_MIN_WINDOW_DAYS &&
    episodes >= PAPER_CONFIRMATION_MIN_EPISODES;
  return criterion("window", met ? "met" : "unmet", measurement);
}

function buildOperationLineageCriterion(
  facts: PaperOperationsFacts | null,
): PaperConfirmationCriterionV1 {
  const operations = num(facts?.operations);
  const withCycleLineage = num(facts?.withCycleLineage);
  const measurement = [
    part("operaciones cerradas", operations),
    part("con linaje de ciclo", withCycleLineage),
  ].join(" · ");
  if (
    facts?.loaded !== true ||
    operations === null ||
    withCycleLineage === null
  ) {
    return criterion("operation_lineage", "unknown", measurement);
  }
  const met =
    operations >= PAPER_CONFIRMATION_MIN_CLOSED_OPERATIONS &&
    withCycleLineage === operations;
  return criterion("operation_lineage", met ? "met" : "unmet", measurement);
}

function buildExecutionAttributionCriterion(
  facts: PaperExecutionsFacts | null,
): PaperConfirmationCriterionV1 {
  const fills = num(facts?.fills);
  const attributed = num(facts?.attributed);
  const measurement = [
    part("ejecuciones durables", fills),
    part("atribuidas a su operación", attributed),
  ].join(" · ");
  if (facts?.loaded !== true || fills === null || attributed === null) {
    return criterion("execution_attribution", "unknown", measurement);
  }
  const met =
    fills >= PAPER_CONFIRMATION_MIN_REQUIRED_FILLS && attributed === fills;
  return criterion("execution_attribution", met ? "met" : "unmet", measurement);
}

function buildClosureReconciliationCriterion(
  facts: PaperClosuresFacts | null,
): PaperConfirmationCriterionV1 {
  const settlements = num(facts?.settlements);
  const reconciled = num(facts?.reconciled);
  const measurement = [
    part("cierres durables", settlements),
    part("reconciliados", reconciled),
  ].join(" · ");
  if (facts?.loaded !== true || settlements === null || reconciled === null) {
    return criterion("closure_reconciliation", "unknown", measurement);
  }
  const met =
    settlements >= PAPER_CONFIRMATION_MIN_CLOSED_OPERATIONS &&
    reconciled === settlements;
  return criterion(
    "closure_reconciliation",
    met ? "met" : "unmet",
    measurement,
  );
}

function buildCostCoverageCriterion(
  facts: PaperCostsFacts | null,
): PaperConfirmationCriterionV1 {
  const expected = num(facts?.expected);
  const complete = num(facts?.complete);
  const measurement = [
    part("cierres con coste exigido", expected),
    part("con coste medido", complete),
  ].join(" · ");
  if (facts?.loaded !== true || expected === null || complete === null) {
    return criterion("cost_coverage", "unknown", measurement);
  }
  const met =
    expected >= PAPER_CONFIRMATION_MIN_CLOSED_OPERATIONS &&
    complete === expected;
  return criterion("cost_coverage", met ? "met" : "unmet", measurement);
}

function buildDurableResultsCriterion(
  facts: PaperResultsFacts | null,
): PaperConfirmationCriterionV1 {
  const withMeasuredResult = num(facts?.withMeasuredResult);
  const measurement = part("cierres con resultado medido", withMeasuredResult);
  if (facts?.loaded !== true || withMeasuredResult === null) {
    return criterion("durable_results", "unknown", measurement);
  }
  const met = withMeasuredResult >= PAPER_CONFIRMATION_MIN_CLOSED_OPERATIONS;
  return criterion("durable_results", met ? "met" : "unmet", measurement);
}

function buildNonContradictionCriterion(
  facts: PaperResultsFacts | null,
): PaperConfirmationCriterionV1 {
  const contradictions = num(facts?.contradictions);
  const measurement = part("contradicciones", contradictions);
  if (facts?.loaded !== true || contradictions === null) {
    return criterion("non_contradiction", "unknown", measurement);
  }
  return criterion(
    "non_contradiction",
    contradictions === 0 ? "met" : "unmet",
    measurement,
  );
}

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------

/**
 * Evalúa los criterios de suficiencia y devuelve el veredicto reservado. La confirmación NUNCA
 * se emite: `verdict` es el literal `"NO_CONFIRMED"` incluso si todos los criterios se cumplen.
 */
export function buildPaperConfirmationVerdict(
  input: PaperConfirmationContractInput,
): PaperConfirmationVerdictV1 {
  const criteria: PaperConfirmationCriterionV1[] = [
    buildWindowCriterion(input.window),
    buildOperationLineageCriterion(input.operations),
    buildExecutionAttributionCriterion(input.executions),
    buildClosureReconciliationCriterion(input.closures),
    buildCostCoverageCriterion(input.costs),
    buildDurableResultsCriterion(input.results),
    buildNonContradictionCriterion(input.results),
  ];

  const metCriterionIds = criteria
    .filter((item) => item.status === "met")
    .map((item) => item.id);
  const unmetCriterionIds = criteria
    .filter((item) => item.status === "unmet")
    .map((item) => item.id);
  const unknownCriterionIds = criteria
    .filter((item) => item.status === "unknown")
    .map((item) => item.id);
  const unmetOrUnmeasuredCriterionIds = criteria
    .filter((item) => item.status !== "met")
    .map((item) => item.id);

  const unknown = unknownCriterionIds.length;
  const unmet = unmetCriterionIds.length;
  const summary = [
    `Contrato PAPER definido pero no satisfecho: ${metCriterionIds.length}/${criteria.length} criterios cumplidos, ${unknown} sin dato todavía y ${unmet} incumplidos.`,
    PAPER_CONFIRMATION_NON_PROMOTION_NOTE,
  ]
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();

  return {
    schemaVersion: "paper_confirmation_contract_v1",
    verdict: "NO_CONFIRMED",
    verdictLabel: PAPER_CONFIRMATION_GLOBAL_VERDICT_LABEL,
    summary,
    criteria,
    metCriterionIds,
    unmetCriterionIds,
    unknownCriterionIds,
    unmetOrUnmeasuredCriterionIds,
    confirmationBlockedReason: PAPER_CONFIRMATION_RESERVED_REASON,
  };
}
