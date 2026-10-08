/**
 * Nav y ruta de Confirmar (R-12 C1).
 *
 * Helpers unit-testeables sin montar la barra. Destino SPA único: `/confirm`.
 *
 * @see docs/engineering/plan-r12-track-c-frontend-2026-08-21.md § C1
 */

/** Ruta de primer nivel para firmar la cola F3. */
export const CONFIRM_PATH = "/confirm" as const;

/** Evento SPA (escuchado por `PlatformShell`). Nunca `window.location`. */
export const BOLSA_NAVIGATE_EVENT = "bolsa:navigate";

export type BolsaNavigateDetail = {
  to: typeof CONFIRM_PATH;
};

/**
 * True solo si `to` es la ruta interna `/confirm` (anti open-redirect).
 */
export function isConfirmNavigateTarget(
  to: unknown,
): to is typeof CONFIRM_PATH {
  return to === CONFIRM_PATH;
}

/**
 * Texto del pill de nav. `null` si no hay pendientes; `9+` si hay más de 9.
 */
export function formatConfirmNavBadge(count: number): string | null {
  if (count <= 0) return null;
  return count > 9 ? "9+" : String(count);
}

/**
 * `aria-label` / `title` del pill cuando hay pendientes.
 *
 * Lenguaje de resultado, sin jerga de mecanismo (`R-G1`): sobre la navegación
 * `Hoy` el contador dice cuántos asuntos requieren atención, no «firmas».
 */
export function confirmNavAriaLabel(count: number): string | undefined {
  if (count <= 0) return undefined;
  return `${count} ${count === 1 ? "requiere" : "requieren"} tu atención`;
}

/** Pregunta de primer nivel de Hoy (`R-G2`): una pantalla = una pregunta. */
export const HOY_ATTENTION_QUESTION = "¿Qué requiere mi atención?" as const;
