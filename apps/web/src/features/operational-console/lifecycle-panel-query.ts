/**
 * Paneles de lifecycle de la Consola Operacional (outbox · recon · integrity).
 *
 * Los tres endpoints (`/api/lifecycle/outbox/stats`, `/api/lifecycle/reconciliation`,
 * `/api/lifecycle/integrity`) usan `require_jwt_principal`, que **no** cae al principal
 * de settings: sin sesión JWT responden 401 de forma permanente. El resto de la consola
 * usa `get_request_principal`, que sí cae al fallback, y por eso el resto sí responde.
 *
 * Consecuencia sin este helper: `retry:1` reintentaba en vano y `refetchInterval:30s`
 * volvía a llamar cada 30 s para siempre, llenando la consola de errores 401 y dejando
 * el panel en un estado que el operador no puede interpretar.
 *
 * `authError` distingue ese caso para que la UI diga la verdad («requiere sesión») en
 * lugar de «no se pudo cargar», que se lee como avería de datos.
 */
import { ApiError } from "@/lib/api";

/** 401/403 — la API exige un JWT que esta sesión no aporta. Reintentar no lo arregla. */
export function isAuthError(error: unknown): boolean {
  return (
    error instanceof ApiError && (error.status === 401 || error.status === 403)
  );
}

/** Opciones de query para los tres paneles: sin reintento inútil ni sondeo en 401. */
export function lifecyclePanelQueryOptions() {
  return {
    retry: false,
    refetchInterval: (query: { state: { error: unknown } }): number | false =>
      isAuthError(query.state.error) ? false : 30_000,
  };
}
