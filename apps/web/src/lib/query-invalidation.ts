import type { QueryClient } from '@tanstack/react-query';

/** Refresca datos de mercado tras sync u otras mutaciones que afectan precios/histórico. */
export async function invalidateInstrumentMarketData(
  queryClient: QueryClient,
  instrumentId: string,
) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['instrument', instrumentId] }),
    queryClient.invalidateQueries({ queryKey: ['ohlcv', instrumentId] }),
    queryClient.invalidateQueries({ queryKey: ['indicators', instrumentId] }),
    queryClient.invalidateQueries({ queryKey: ['live-quote', instrumentId] }),
    queryClient.invalidateQueries({ queryKey: ['data-status', instrumentId] }),
    queryClient.invalidateQueries({ queryKey: ['instruments'] }),
    queryClient.invalidateQueries({ queryKey: ['list-quotes'] }),
  ]);
}
