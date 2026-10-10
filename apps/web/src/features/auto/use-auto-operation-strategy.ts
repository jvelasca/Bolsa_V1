/**
 * AUTO UI — hook read-only del puente operación → estrategia ganadora (P3/P4).
 *
 * Resuelve, para el ciclo seleccionado del monitor AUTO, el UUID del instrumento (el monitor
 * expone el TICKER, no el UUID), el TOP de Finalistas del valor y la definición de la estrategia
 * #1. Con ello compone la vista pura (`auto-operation-strategy.ts`). No recalcula nada: copia el
 * TOP ya producido por el embudo.
 *
 * Fail-closed: si no se puede resolver el instrumento o no hay TOP, la vista declara el hueco;
 * ninguna query lanza ni rellena con ceros.
 *
 * @see docs/PROJECT_PREMISES.md §6
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  buildAutoOperationStrategyView,
  type AutoOperationStrategyViewV1,
} from "@/features/auto/auto-operation-strategy";

export type UseAutoOperationStrategyInput = {
  /**
   * Ciclo seleccionado del monitor (tal cual): el `instrumentId` es el TICKER (puede faltar)
   * y el `strategyVersion` es el sello declarado por el motor. `null` = sin operación.
   */
  cycle: {
    instrumentId?: string | null;
    strategyVersion?: string | null;
  } | null;
  timeframe?: string;
};

export function useAutoOperationStrategy(
  input: UseAutoOperationStrategyInput,
): {
  view: AutoOperationStrategyViewV1 | null;
} {
  const timeframe = input.timeframe ?? "1d";
  const hasCycle = input.cycle != null;
  const ticker = input.cycle?.instrumentId?.trim() || null;
  const cycleStrategyVersion = input.cycle?.strategyVersion?.trim() || null;

  const instrumentsQuery = useQuery({
    queryKey: ["instruments"],
    queryFn: () => api.getInstruments(),
    enabled: Boolean(ticker),
    staleTime: 300_000,
    retry: false,
  });

  const resolvedInstrumentId = useMemo(() => {
    if (!ticker) return null;
    const list = instrumentsQuery.data?.data ?? [];
    const upper = ticker.toUpperCase();
    const found = list.find((inst) => inst.symbol?.toUpperCase() === upper);
    return found?.id ?? null;
  }, [ticker, instrumentsQuery.data]);

  const topQuery = useQuery({
    queryKey: ["instrument-strategy-top", resolvedInstrumentId, timeframe],
    queryFn: () =>
      api.getInstrumentStrategyTop(resolvedInstrumentId!, timeframe),
    enabled: Boolean(resolvedInstrumentId),
    staleTime: 30_000,
    retry: false,
  });

  const top = topQuery.data?.data ?? null;

  const strategyDefinitionId = useMemo(() => {
    const slot = top
      ? ([...top.slots].sort((a, b) => a.rank - b.rank)[0] ?? null)
      : null;
    return slot?.strategyDefinitionId?.trim() || null;
  }, [top]);

  const definitionQuery = useQuery({
    queryKey: ["strategy", strategyDefinitionId],
    queryFn: () => api.getStrategy(strategyDefinitionId!),
    enabled: Boolean(strategyDefinitionId),
    staleTime: 60_000,
    retry: false,
  });

  const definition = definitionQuery.data?.data?.definition ?? null;

  // Lecturas en vuelo (solo cuentan las queries HABILITADAS: una deshabilitada reporta
  // `isLoading === false`). Con alguna en vuelo, un hueco todavía no es una ausencia.
  const loading =
    instrumentsQuery.isLoading ||
    topQuery.isLoading ||
    definitionQuery.isLoading;

  const view = useMemo(
    () =>
      buildAutoOperationStrategyView({
        // La forma del ciclo se conserva tal cual: un ciclo SELECCIONADO sin ticker sigue
        // rindiendo una vista (con hueco declarado), no un `null` que oculte la tarjeta.
        cycle: hasCycle
          ? {
              instrumentId: ticker,
              strategyVersion: cycleStrategyVersion,
            }
          : null,
        instrumentId: resolvedInstrumentId,
        top,
        // Un FALLO de lectura no es una ausencia: se propaga como error declarado.
        topError: topQuery.isError,
        definition,
        definitionError: definitionQuery.isError,
        loading,
      }),
    [
      hasCycle,
      ticker,
      cycleStrategyVersion,
      resolvedInstrumentId,
      top,
      topQuery.isError,
      definition,
      definitionQuery.isError,
      loading,
    ],
  );

  return { view };
}
