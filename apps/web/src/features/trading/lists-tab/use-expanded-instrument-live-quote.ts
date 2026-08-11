import { useMemo } from "react";
import { useTradingUiStore } from "@/stores/trading-ui-store";
import { useInstrumentLiveQuotesBatch } from "@/features/instruments/use-instrument-live-quotes-batch";

const EXPANDED_QUOTES_REFETCH_MS = 15_000;

/** Cotización live compartida para filas expandidas en listas (una petición batch). */
export function useExpandedInstrumentLiveQuote(
  instrumentId: string,
  expanded: boolean,
) {
  const expandedInstrumentIds = useTradingUiStore(
    (state) => state.expandedInstrumentIds,
  );

  const batchIds = useMemo(() => {
    if (!expanded) return [];
    const ids = Object.entries(expandedInstrumentIds)
      .filter(([, isOpen]) => isOpen)
      .map(([id]) => id);
    if (!ids.includes(instrumentId)) {
      ids.push(instrumentId);
    }
    return [...new Set(ids)];
  }, [expanded, expandedInstrumentIds, instrumentId]);

  const query = useInstrumentLiveQuotesBatch(batchIds, {
    enabled: expanded && batchIds.length > 0,
    refetchInterval: EXPANDED_QUOTES_REFETCH_MS,
    staleTime: EXPANDED_QUOTES_REFETCH_MS,
  });

  const quote = query.data?.find((item) => item.instrumentId === instrumentId);

  return {
    quote,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
  };
}
