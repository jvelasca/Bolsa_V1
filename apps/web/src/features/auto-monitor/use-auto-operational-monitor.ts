/**
 * AUTO Operational Monitor (M1) — hook de lectura read-only.
 *
 * Una sola query sobre el DTO canónico; el view model puro de `@bolsa/shared` añade labels
 * y tonos SIN reinterpretar. La UI no completa pasos ni re-deriva cifras.
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

export function useAutoOperationalMonitor(input?: {
  cycleId?: string;
  enabled?: boolean;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const query = useQuery({
    queryKey: [
      "auto-operational-monitor",
      effectiveAccountId,
      input?.cycleId ?? null,
    ],
    queryFn: () => api.getAutoOperationalMonitor({ cycleId: input?.cycleId }),
    enabled: (input?.enabled ?? true) && Boolean(effectiveAccountId),
    staleTime: 10_000,
    refetchInterval: 20_000,
    retry: false,
  });

  const view: AutoOperationalMonitorViewV1 | null = useMemo(
    () =>
      query.data?.data
        ? buildAutoOperationalMonitorView(
            query.data.data as unknown as AutoOperationalMonitorV1,
          )
        : null,
    [query.data],
  );

  return { ...query, view, accountId: effectiveAccountId };
}
