/**
 * UI Contract 5.0 (`UI5-14`, enmienda UI 6.0) — vocabulario único de dato ausente (Opción B).
 *
 * Tres rótulos NO intercambiables:
 * - `Sin dato todavía` = no medido aún (el sistema todavía no lo sabe).
 * - `No aplica`        = la operación/objeto no tiene ese campo por naturaleza.
 * - `No disponible`    = medido, pero no accesible ahora (p. ej. sin sesión).
 *
 * `—` se reserva al **nivel 3** (auditoría técnica); nunca es comodín de primer nivel.
 * `UNKNOWN ≠ 0`: un hueco se declara, jamás se colapsa a cero ni a verde.
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §UI5-14
 * @see docs/engineering/auditoria-ui-5-0-mapa-problemas-2026-10-08.md §9
 */

export const ABSENT_DATA_NOT_MEASURED = "Sin dato todavía";
export const ABSENT_DATA_NOT_APPLICABLE = "No aplica";
export const ABSENT_DATA_NOT_AVAILABLE = "No disponible";

/** Rótulo reservado a nivel 3 (auditoría/diagnóstico). Nunca en primer nivel. */
export const ABSENT_DATA_TECHNICAL_DASH = "—";

export type AbsentDataKind =
  | "not_measured"
  | "not_applicable"
  | "not_available";

const ABSENT_DATA_LABELS: Record<AbsentDataKind, string> = {
  not_measured: ABSENT_DATA_NOT_MEASURED,
  not_applicable: ABSENT_DATA_NOT_APPLICABLE,
  not_available: ABSENT_DATA_NOT_AVAILABLE,
};

/** Rótulo de primer nivel para un dato ausente. Por defecto: `Sin dato todavía`. */
export function absentDataLabel(kind: AbsentDataKind = "not_measured"): string {
  return ABSENT_DATA_LABELS[kind];
}

/** `true` si el valor no es afirmable (`null`/`undefined`/`NaN`). */
export function isAbsent(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  return typeof value === "number" && Number.isNaN(value);
}

/**
 * Valor formateado o rótulo de ausencia (nivel 1). Evita `—` como comodín: si no hay valor,
 * devuelve el rótulo oficial del hueco en vez de un guion.
 */
export function formatOrAbsent<T>(
  value: T | null | undefined,
  format: (value: T) => string,
  kind: AbsentDataKind = "not_measured",
): string {
  return isAbsent(value) ? absentDataLabel(kind) : format(value as T);
}
