/**
 * Hook: dictámenes diarios Estudio (on-demand + caché POR CUENTA).
 *
 * El cliente NO envía hints: la postura depende de las posiciones de la cuenta y los
 * scores de los chips, y ambos los mide el servidor. El `accountId` forma parte de la
 * `queryKey` porque la caché del servidor también está separada por cuenta.
 *
 * @see docs/adr/022-estudio-daily-opinion-motor.md
 */

import { useQuery } from "@tanstack/react-query";
import type { InstrumentDailyOpinionV1 } from "@bolsa/shared";
import { chunkIds, DAILY_OPINIONS_BATCH_LIMIT } from "@bolsa/shared";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { api } from "@/lib/api";

export function useInstrumentDailyOpinions(
  instrumentIds: string[],
  options?: {
    enabled?: boolean;
    forceRefresh?: boolean;
    refetchInterval?: number | false;
    /** Scope explícito; por defecto la cuenta Activa. */
    accountId?: string | null;
  },
) {
  const ids = [...new Set(instrumentIds.filter(Boolean))].sort();
  const { effectiveAccountId } = useActiveAccount();
  // `null` explícito = scope global (`__global__` en servidor); sólo `undefined` cae a
  // la cuenta activa. Con `??` un null explícito se colaba como cuenta activa.
  const accountId =
    options?.accountId === undefined
      ? effectiveAccountId
      : options.accountId;
  const enabled = (options?.enabled ?? true) && ids.length > 0;

  return useQuery({
    queryKey: [
      "instrument-daily-opinions",
      ids,
      accountId ?? null,
      options?.forceRefresh ?? false,
    ],
    enabled,
    staleTime: 60_000,
    refetchInterval: options?.refetchInterval,
    queryFn: async (): Promise<InstrumentDailyOpinionV1[]> => {
      // El API acepta 200 ids por petición: Visualizados puede superarlo.
      const chunks = chunkIds(ids, DAILY_OPINIONS_BATCH_LIMIT);
      const parts = await Promise.all(
        chunks.map((chunk) =>
          api.queryInstrumentDailyOpinions({
            instrumentIds: chunk,
            forceRefresh: options?.forceRefresh ?? false,
            accountId: accountId ?? null,
          }),
        ),
      );
      return parts.flatMap((res) => res.data ?? []);
    },
  });
}

export function opinionByInstrumentId(
  rows: InstrumentDailyOpinionV1[] | undefined,
): Map<string, InstrumentDailyOpinionV1> {
  const map = new Map<string, InstrumentDailyOpinionV1>();
  for (const row of rows ?? []) {
    map.set(row.instrumentId, row);
  }
  return map;
}
