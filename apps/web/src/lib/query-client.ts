import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

/**
 * Fase 3.2 (auditoría externa): un 401 de la API debe cerrar la sesión de la UI.
 *
 * ``api.ts`` ya lanza ``ApiError(401)``; aquí se reacciona una sola vez y sin red:
 *
 * - ``auth_disabled``: la API no exige auth (perfil local). Un 401 no se interpreta como
 *   sesión caducada: no se toca el estado.
 * - ``already_unauthenticated``: ya estamos en el login. No se vuelve a limpiar ni se
 *   llama a ``/api/auth/logout``. Este es el corte del bucle: un login fallido con 401
 *   deja el estado como estaba y no dispara peticiones.
 * - ``session_expired``: había sesión y el servidor la rechaza. Se marca
 *   ``authenticated=false`` conservando ``authEnabled=true``, de modo que ``AuthGate``
 *   pinta el login en el acto (no hay ruta ``/login`` que navegar ni recarga).
 *
 * El resultado es un valor comprobable, no un efecto mudo: los tests fijan cada rama.
 */
export type UnauthorizedOutcome =
  | "session_expired"
  | "not_401"
  | "auth_disabled"
  | "already_unauthenticated";

export function handleUnauthorizedError(error: unknown): UnauthorizedOutcome {
  if (!(error instanceof ApiError) || error.status !== 401) {
    return "not_401";
  }
  const state = useAuthStore.getState();
  if (!state.authEnabled) {
    return "auth_disabled";
  }
  if (!state.authenticated) {
    return "already_unauthenticated";
  }
  state.expireSession();
  return "session_expired";
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({ onError: handleUnauthorizedError }),
    mutationCache: new MutationCache({ onError: handleUnauthorizedError }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // Un 401 no se reintenta: reintentar una sesión caducada solo retrasa el login y
        // duplica peticiones condenadas a fallar. El resto conserva el reintento actual.
        retry: (failureCount, error) =>
          !(error instanceof ApiError && error.status === 401) &&
          failureCount < 1,
      },
    },
  });
}

export const queryClient = createQueryClient();
