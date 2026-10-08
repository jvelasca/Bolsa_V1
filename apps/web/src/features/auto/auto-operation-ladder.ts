/**
 * UI Contract 5.0 (`UI5-09`/`UI5-11`/`UI5-20`) — escalera universal de operación (helper puro).
 *
 * Una sola gramática de peldaños para toda la app. Traduce los hechos de un ciclo a la escalera
 * canónica del modelo semántico, sin inventar materialización:
 *
 *   Orden preparada → Orden enviada → Esperando ejecución → Ejecución parcial/completada
 *   → Posición creada → Posición cerrada
 *
 * Invariantes:
 * - **Nunca se salta de orden a posición.** `Posición creada` exige traza de materialización; como
 *   AUTO no la tiene, la escalera se detiene en `Ejecución completada` y lo declara.
 * - **`Precio aplicado ≠ posición creada`.** El fill es un precio aplicado; la posición es otro peldaño.
 * - **Un término = un significado.** Este módulo es la única fuente de las etiquetas de peldaño.
 * - **`UNKNOWN ≠ 0`.** Sin evidencia, el peldaño es «Sin dato todavía».
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §UI5-09
 * @see docs/domain-language.md §4.2
 */

import {
  type AutoBasicCycle,
  readEntryQuantities,
} from "@/features/auto/auto-basic-home";
import { AUTO_HOME_NO_DATA_LABEL } from "@/features/auto/auto-home-summary";

export type OperationLadderRungId =
  | "order_prepared"
  | "order_sent"
  | "waiting_execution"
  | "partial_execution"
  | "executed"
  | "position_created"
  | "position_closed";

export type OperationLadderRung = {
  id: OperationLadderRungId;
  label: string;
};

/** Escalera canónica compartida por todas las superficies. El orden es el del contrato. */
export const OPERATION_LADDER: readonly OperationLadderRung[] = [
  { id: "order_prepared", label: "Orden preparada" },
  { id: "order_sent", label: "Orden enviada" },
  { id: "waiting_execution", label: "Esperando ejecución" },
  { id: "partial_execution", label: "Ejecución parcial" },
  { id: "executed", label: "Ejecución completada" },
  { id: "position_created", label: "Posición creada" },
  { id: "position_closed", label: "Posición cerrada" },
] as const;

/** Distancias que la UI debe recordar en todo momento. */
export const OPERATION_LADDER_NOTES = {
  priceAppliedIsNotPosition: "Precio aplicado ≠ posición creada",
  rankingIsNotDecision: "Ranking ≠ decisión",
} as const;

/** Etiqueta canónica de un peldaño por id (fuente única). */
export function operationLadderLabel(id: OperationLadderRungId): string {
  return OPERATION_LADDER.find((rung) => rung.id === id)?.label ?? id;
}

export type OperationLadderRungV1 = {
  /** Peldaño alcanzado, o `null` si no hay evidencia. */
  id: OperationLadderRungId | null;
  /** Etiqueta canónica del peldaño, o «Sin dato todavía». */
  label: string;
  /** Lo que este peldaño NO significa (p. ej. `Precio aplicado ≠ posición creada`). */
  note: string | null;
};

function stepOf(cycle: AutoBasicCycle, id: string) {
  return (cycle.steps ?? []).find((step) => step.id === id);
}

/**
 * Peldaño más avanzado con evidencia real. No deriva de `RUNNING` ni de un fill sin medición.
 * Se detiene antes de `Posición creada`: AUTO no tiene traza de materialización.
 */
export function operationLadderRungFromCycle(
  cycle: AutoBasicCycle,
): OperationLadderRungV1 {
  const order = stepOf(cycle, "ORDER");
  const fill = stepOf(cycle, "FILL");

  if (
    cycle.closed === true &&
    (cycle.closedMeasurement ?? "COMPLETE") === "COMPLETE"
  ) {
    return {
      id: "position_closed",
      label: operationLadderLabel("position_closed"),
      note: null,
    };
  }

  if (fill?.state === "reached") {
    if (order?.state !== "reached") {
      return { id: null, label: AUTO_HOME_NO_DATA_LABEL, note: null };
    }
    if (fill.measurement != null && fill.measurement !== "COMPLETE") {
      return { id: null, label: AUTO_HOME_NO_DATA_LABEL, note: null };
    }
    const { requested, applied } = readEntryQuantities(cycle);
    const id: OperationLadderRungId =
      requested != null && applied != null && applied < requested
        ? "partial_execution"
        : "executed";
    return {
      id,
      label: operationLadderLabel(id),
      note: OPERATION_LADDER_NOTES.priceAppliedIsNotPosition,
    };
  }

  if (fill?.state === "pending") {
    return {
      id: "waiting_execution",
      label: operationLadderLabel("waiting_execution"),
      note: null,
    };
  }

  if (order?.state === "reached") {
    return {
      id: "order_sent",
      label: operationLadderLabel("order_sent"),
      note: null,
    };
  }

  if (order?.state === "pending") {
    return {
      id: "order_prepared",
      label: operationLadderLabel("order_prepared"),
      note: null,
    };
  }

  return { id: null, label: AUTO_HOME_NO_DATA_LABEL, note: null };
}
