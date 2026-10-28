/**
 * AUTO Operational Monitor (M1) — hook de lectura read-only.
 *
 * Una sola query sobre el DTO canónico; el view model puro de `@bolsa/shared` añade labels
 * y tonos SIN reinterpretar. La UI no completa pasos ni re-deriva cifras.
 *
 * Estados de lectura explícitos: `view === null` NO es una colección vacía válida. Cuando la
 * query no se ejecuta (sin cuenta activa o `enabled: false`) el estado es `not_consulted`; la UI
 * debe declararlo y no pintar «no hay declaraciones», porque no se ha leído nada.
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  buildAutoOperationalMonitorView,
  type AutoOperationalMonitorV1,
  type AutoOperationalMonitorViewV1,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

/**
 * Estado de la lectura del monitor:
 * - `loading`: la cuenta se está resolviendo o la query está en curso.
 * - `ready`: el DTO se leyó (aunque la ventana venga vacía).
 * - `error`: la lectura falló.
 * - `not_consulted`: la query no se ejecutó (sin cuenta activa o deshabilitada).
 */
export type AutoOperationalMonitorReadState =
  | "loading"
  | "ready"
  | "error"
  | "not_consulted";

export function useAutoOperationalMonitor(input?: {
  cycleId?: string;
  enabled?: boolean;
}) {
  const { effectiveAccountId, isLoading: accountLoading } = useActiveAccount();
  const enabled = (input?.enabled ?? true) && Boolean(effectiveAccountId);
  const query = useQuery({
    queryKey: [
      "auto-operational-monitor",
      effectiveAccountId,
      input?.cycleId ?? null,
    ],
    queryFn: () => api.getAutoOperationalMonitor({ cycleId: input?.cycleId }),
    enabled,
    staleTime: 10_000,
    refetchInterval: 20_000,
    retry: false,
  });

  const view: AutoOperationalMonitorViewV1 | null = useMemo(
    () =>
      query.data
        ? buildAutoOperationalMonitorView(
            query.data as unknown as AutoOperationalMonitorV1,
          )
        : null,
    [query.data],
  );

  const readState: AutoOperationalMonitorReadState = query.isError
    ? "error"
    : query.isPending
      ? // Una query deshabilitada queda en `pending`/`idle`: si no hay consulta en curso porque
        // falta la cuenta, el estado es `not_consulted`, no una ventana vacía. Mientras la
        // cuenta se resuelve, sigue siendo carga.
        enabled || accountLoading
        ? "loading"
        : "not_consulted"
      : "ready";

  return { ...query, view, accountId: effectiveAccountId, readState };
}
