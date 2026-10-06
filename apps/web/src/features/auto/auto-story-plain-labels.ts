/**
 * AUTO UI REFACTOR (F4b) — etiquetas llanas de la historia (glosario de primer nivel).
 *
 * Traduce el nombre técnico de una etapa de la operación a lenguaje de usuario. Sólo afecta al
 * **texto visible** del panel de la historia: el modelo semántico de `@bolsa/shared` NO se toca y
 * el término técnico se conserva en el detalle (`title`). `data-stage`/`data-state` tampoco cambian.
 *
 * @see docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md §F4
 */

import type { AutoOperationStoryStageId } from "@bolsa/shared";

export const AUTO_STORY_PLAIN_LABELS: Record<
  AutoOperationStoryStageId,
  string
> = {
  OPPORTUNITY: "De dónde salió",
  SIGNAL: "Aviso de entrada",
  SELECTION: "Elegida entre las mejores",
  DECISION: "Decisión de cartera",
  RISK: "Riesgo controlado",
  RESERVATION: "Capital apartado",
  ORDER: "Orden anotada",
  FILL: "Precio aplicado",
  // Sólo visible si el monitor trae un paso `POSITION` propio. Mientras se pliega en el precio,
  // esta frase no se pinta como fila «Hecho».
  POSITION: "Posición",
  PROTECTION: "Protección fijada",
  EXIT: "Intención de salida",
  SETTLEMENT: "Resultado de la venta",
  RESULT: "Resultado final",
  EXPLANATION: "Qué enseña",
};

/**
 * Etiqueta llana de una etapa. Un id desconocido degrada a la etiqueta técnica recibida (el modelo
 * es la fuente de verdad), nunca a un texto inventado.
 */
export function plainStageLabel(id: string, technicalLabel: string): string {
  return (
    AUTO_STORY_PLAIN_LABELS[id as AutoOperationStoryStageId] ?? technicalLabel
  );
}

/**
 * Estado de una etapa en lenguaje de usuario (nivel 1). `NO MEDIDO` es el término correcto de
 * auditoría, pero no de usuario: en primer nivel se declara «Sin dato todavía» (spec 3.0 §1.9).
 */
export const AUTO_STORY_PLAIN_STATE_LABELS: Record<string, string> = {
  REACHED: "Hecho",
  PENDING: "Pendiente",
  ABSENT: "No ocurrió",
  NOT_MEASURED: "Sin dato todavía",
};

export function plainStateLabel(state: string, technicalLabel: string): string {
  return AUTO_STORY_PLAIN_STATE_LABELS[state] ?? technicalLabel;
}
