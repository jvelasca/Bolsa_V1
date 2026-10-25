/**
 * Hook: dictámenes diarios Estudio (on-demand + caché).
 * @see docs/adr/022-estudio-daily-opinion-motor.md
 */

import { useQuery } from "@tanstack/react-query";
import type {
  InstrumentDailyOpinionHintV1,
  InstrumentDailyOpinionV1,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { positionOpenHintKey } from "@/lib/position-open-hint";

/**
 * Clave de UN hint dentro de la `queryKey`. `positionOpen` es tri-estado: `null` (cartera
 * no medida) NO puede compartir clave con `false` (sin posición), o la caché de una
 * medición anterior se serviría para un estado que el servidor debe fallar cerrado.
 */
export function instrumentDailyOpinionHintKey(
  hint: InstrumentDailyOpinionHintV1,
): string {
  return [
    hint.instrumentId,
    hint.ioScore ?? "",
    hint.distress ? 1 : 0,
    positionOpenHintKey(hint.positionOpen),
    hint.allowTrading === false ? 0 : 1,
    hint.hasEodBar === undefined ? "u" : hint.hasEodBar ? 1 : 0,
  ].join(":");
}

export function useInstrumentDailyOpinions(
  instrumentIds: string[],
  hints: InstrumentDailyOpinionHintV1[] = [],
  options?: {
    enabled?: boolean;
    forceRefresh?: boolean;
    refetchInterval?: number | false;
  },
) {
  const ids = [...new Set(instrumentIds.filter(Boolean))].sort();
  const enabled = (options?.enabled ?? true) && ids.length > 0;

  return useQuery({
    queryKey: [
      "instrument-daily-opinions",
      ids,
      options?.forceRefresh ?? false,
      hints.map(instrumentDailyOpinionHintKey),
    ],
    enabled,
    staleTime: 60_000,
    refetchInterval: options?.refetchInterval,
    queryFn: async (): Promise<InstrumentDailyOpinionV1[]> => {
      const res = await api.queryInstrumentDailyOpinions({
        instrumentIds: ids,
        forceRefresh: options?.forceRefresh ?? false,
        hints: hints.filter((h) => ids.includes(h.instrumentId)),
      });
      return res.data ?? [];
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
