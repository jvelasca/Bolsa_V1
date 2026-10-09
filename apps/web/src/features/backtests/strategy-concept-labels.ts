/**
 * UI 5.0 · P3 (Slice B) — vocabulario único para SEPARAR los tres conceptos del embudo.
 *
 * El embudo mezclaba en una sola cadena (y a veces con enums crudos) tres cosas distintas:
 *  1. SELECCIÓN  — qué estrategia/peldaño se eligió (ciclo del TOP: Borrador/Semifinal/Activo).
 *  2. VALIDACIÓN — si está validada fuera de muestra (lab OOS) o solo in-sample.
 *  3. EVIDENCIA  — indicadores/procedencia que la respaldan (estrellas, hold-out/WF/CPCV).
 *
 * Estas funciones dan la etiqueta humana de cada eje por separado y nunca devuelven el enum
 * crudo (`active`, `in_sample_only`, `lab_validated`). Criterio de aceptación (auditoría P3):
 * debe quedar claro qué estrategia se seleccionó y qué evidencia la respalda.
 *
 * @see docs/engineering/research-lifecycle.md
 */

import type { InstrumentStrategyTopStatus } from "@bolsa/shared";
import { absentDataLabel } from "@/components/absent-data";

export type StrategyEvidenceLevel = "in_sample_only" | "lab_validated";

const SELECTION_STATUS_LABELS: Record<InstrumentStrategyTopStatus, string> = {
  draft: "Borrador",
  semifinal: "Semifinal",
  active: "Activo",
};

/**
 * SELECCIÓN — estado del ciclo del TOP en lenguaje humano.
 * Nunca el enum crudo; `null`/vacío conserva el hueco (`Sin dato todavía`).
 */
export function strategySelectionStatusLabel(
  status: InstrumentStrategyTopStatus | string | null | undefined,
): string {
  if (status == null || status === "") return absentDataLabel();
  return (
    SELECTION_STATUS_LABELS[status as InstrumentStrategyTopStatus] ??
    String(status)
  );
}

/**
 * VALIDACIÓN — `lab_validated` → «lab OOS»; `in_sample_only` → «solo in-sample».
 * Nunca el enum crudo; `null`/vacío conserva el hueco.
 */
export function strategyValidationLabel(
  evidenceLevel: StrategyEvidenceLevel | string | null | undefined,
): string {
  if (evidenceLevel == null || evidenceLevel === "") return absentDataLabel();
  return evidenceLevel === "lab_validated" ? "Lab OOS" : "solo in-sample";
}
