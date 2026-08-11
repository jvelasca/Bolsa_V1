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
      hints.map((h) =>
        [
          h.instrumentId,
          h.ioScore ?? "",
          h.distress ? 1 : 0,
          h.positionOpen ? 1 : 0,
          h.allowTrading === false ? 0 : 1,
          h.hasEodBar === undefined ? "u" : h.hasEodBar ? 1 : 0,
        ].join(":"),
      ),
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
