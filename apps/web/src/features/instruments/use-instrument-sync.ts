/**
 * Hook compartido para sincronizar histórico Yahoo de un instrumento.
 *
 * Tras éxito invalida queries OHLCV/indicators y dispara reflow del gráfico.
 * Usado por InstrumentSyncDialog y OhlcvChart (overlay sin datos).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { invalidateInstrumentMarketData } from "@/lib/query-invalidation";
import { requestChartReflow } from "@/features/charts/chart-utils";

export function useInstrumentSync(instrumentId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => {
      if (!instrumentId) {
        throw new Error("Instrumento no seleccionado");
      }
      return api.syncInstrument(instrumentId, 5);
    },
    onSuccess: async () => {
      if (!instrumentId) return;
      await invalidateInstrumentMarketData(queryClient, instrumentId);
      requestChartReflow();
    },
  });
}

export function formatSyncError(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError && error.message === "Failed to fetch") {
    return "No se pudo contactar con la API. Comprueba que el backend esté en marcha (puerto 8000 o «Bolsa: API Python + Web»).";
  }
  if (error instanceof Error) return error.message;
  return "Error desconocido al sincronizar";
}
