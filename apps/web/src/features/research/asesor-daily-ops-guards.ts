/**
 * Asesor → Diario · lectura defensiva del parte diario (H-22).
 *
 * Qué hace: convierte un campo del parte en un valor **afirmable o nulo**, para
 * que un payload parcial se declare ausente en vez de romper la pantalla.
 *
 * Qué NO hace: **no** normaliza a colección vacía. `[]` afirmaría «cero» desde un
 * hueco, que es exactamente lo que `UNKNOWN ≠ 0` prohíbe. `null` significa «no se
 * midió» y la superficie debe pintar `absentDataLabel()`.
 *
 * Motivo: el contrato `DailyOpsReportV1` declara estos campos obligatorios y el
 * backend los envía siempre; esto es defensa en la frontera de lectura, no un
 * cambio de contrato. No se toca `packages/shared`.
 *
 * @see docs/engineering/auditoria-operativa-asesor-2026-11-15.md §6.b (H-22)
 */

/**
 * `readonly T[]` si el valor es realmente un array; `null` si no llegó.
 * La diferencia con `?? []` es la diferencia entre «no medido» y «cero medido».
 */
export function asDeclaredList<T>(value: unknown): readonly T[] | null {
  return Array.isArray(value) ? (value as readonly T[]) : null;
}

/** `number` finito si el valor es un número medido; `null` si no llegó. */
export function asDeclaredNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
