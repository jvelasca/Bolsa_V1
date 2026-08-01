/**
 * Cotizaciones live en lote (H2) — evita N+1 en listas y órdenes pendientes.
 *
 * Una sola petición `GET /instruments/live-quotes?ids=…` compartida vía React Query.
 * La clave de caché ordena los IDs para maximizar reutilización entre paneles.
 */
import { useQuery } from '@tanstack/react-query';
import type { InstrumentLiveQuoteDto } from '@bolsa/shared';
import { api } from '@/lib/api';

/** Clave estable de React Query para un conjunto de instrumentos. */
function batchQueryKey(ids: string[]): string[] {
  return ['live-quotes-batch', [...ids].sort().join(',')];
}

/**
 * Hook batch de cotizaciones live.
 *
 * @param ids - IDs de instrumento (se deduplican y filtran vacíos).
 * @param options.enabled - Por defecto true si hay IDs.
 * @param options.refetchInterval - Polling (p. ej. 15_000 ms en listas expandidas).
 * @param options.staleTime - Tiempo fresco antes de refetch; por defecto 10 s.
 */
export function useInstrumentLiveQuotesBatch(
  ids: string[],
  options?: {
    enabled?: boolean;
    refetchInterval?: number;
    staleTime?: number;
  },
) {
  const uniqueIds = [...new Set(ids.filter(Boolean))];
  const enabled = (options?.enabled ?? true) && uniqueIds.length > 0;

  return useQuery({
    queryKey: batchQueryKey(uniqueIds),
    queryFn: async () => {
      const response = await api.getInstrumentLiveQuotes(uniqueIds);
      return response.data;
    },
    enabled,
    staleTime: options?.staleTime ?? 10_000,
    refetchInterval: options?.refetchInterval,
  });
}

/** Mapa instrumentId → cotización para lookup O(1) en filas de lista. */
export function liveQuotesMap(
  quotes: InstrumentLiveQuoteDto[] | undefined,
): Map<string, InstrumentLiveQuoteDto> {
  return new Map((quotes ?? []).map((quote) => [quote.instrumentId, quote]));
}
