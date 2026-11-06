/**
 * P1-01 (`UI5-14`, `UNKNOWN ≠ 0`) — un fallo de lectura NO es una colección vacía.
 *
 * El patrón `query.data ?? []` colapsa tres estados distintos en uno: la colección
 * **medida y vacía** («no hay nada»), la colección **que no se ha podido leer**
 * (error de red / 5xx) y la **que todavía no consta** (query deshabilitada o sin
 * dato). Los dos últimos no autorizan ninguna frase de vacío: la UI debe declarar
 * el hueco (`No disponible` / `Sin dato todavía`), jamás `Sin movimientos`.
 *
 * Este helper es puro y sin React para que cada superficie ancle su propia prueba
 * de render sin repetir la precedencia. El orden es deliberado:
 * `error` > `loading` > `sin dato` > `vacío` > `listo`. Un error durante un
 * refetch con datos previos sigue siendo `error`: la cifra visible ya no es la
 * verdad del servidor.
 *
 * @see apps/web/src/components/absent-data.ts (vocabulario de ausencia)
 * @see docs/engineering/auditoria-ui-operativa-profunda-2026-10-28.md §3.1 / §7 I-01
 */

/** Estado de lectura de una colección remota. */
export type CollectionReadState =
  | "loading"
  | "error"
  | "unavailable"
  | "empty"
  | "ready";

export type CollectionReadInput = {
  /** La consulta falló (`isError` de TanStack Query). */
  isError?: boolean;
  /** Primera carga en curso (`isLoading`). */
  isLoading?: boolean;
  /**
   * Número de elementos **ya leídos**. `null`/`undefined` = no consta (query
   * deshabilitada o sin dato todavía) y NUNCA se interpreta como `0`.
   */
  count?: number | null;
};

/** Resuelve el estado de lectura con la precedencia `error > loading > sin dato > vacío`. */
export function queryCollectionState(
  input: CollectionReadInput,
): CollectionReadState {
  if (input.isError === true) return "error";
  if (input.isLoading === true) return "loading";
  if (input.count == null) return "unavailable";
  return input.count === 0 ? "empty" : "ready";
}

/** `true` si el estado no autoriza ninguna frase de colección vacía. */
export function isCollectionAbsent(state: CollectionReadState): boolean {
  return state === "error" || state === "unavailable" || state === "loading";
}

/** Rótulo de primer nivel del hueco (`No disponible` / `Sin dato todavía` / carga). */
export function collectionAbsenceLabel(
  state: CollectionReadState,
): string | null {
  switch (state) {
    case "error":
      return "No disponible";
    case "unavailable":
      return "Sin dato todavía";
    case "loading":
      return "Cargando…";
    case "empty":
    case "ready":
      return null;
  }
}

/**
 * Frase completa del hueco, con el sujeto en minúscula y artículo
 * (p. ej. `el historial de movimientos`). `null` cuando no hay hueco que declarar.
 */
export function collectionAbsenceCopy(
  state: CollectionReadState,
  subject: string,
): string | null {
  switch (state) {
    case "error":
      return `No disponible — no se pudo leer ${subject}.`;
    case "unavailable":
      return `Sin dato todavía — ${subject} no consta.`;
    case "loading":
      return `Cargando ${subject}…`;
    case "empty":
    case "ready":
      return null;
  }
}
