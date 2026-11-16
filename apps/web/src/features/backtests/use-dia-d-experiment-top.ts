/**
 * R6 — lee el TOP experimento DÍA D (F-D) del **servidor** y lo hidrata en la caché.
 *
 * Los paneles leen la caché de forma síncrona durante el render, así que el hook
 * hace dos cosas a la vez:
 *
 * 1. pide el experimento durable (`GET /api/research/dia-d-experiment-top`);
 * 2. lo hidrata en la caché local si es más reciente que lo que hubiera.
 *
 * Con esto un navegador nuevo (o un dispositivo distinto) ve el experimento que
 * se guardó en otro: el F-D deja de vivir solo en `localStorage`.
 */

import { useEffect, useMemo, useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  getDiaDExperimentTop,
  getDiaDExperimentTopSnapshot,
  hydrateDiaDExperimentTop,
  subscribeDiaDExperimentTop,
  type DiaDExperimentTop,
} from "@/features/backtests/dia-d-experiment-top";
import { api } from "@/lib/api";

export type DiaDExperimentTopState = {
  record: DiaDExperimentTop | null;
  isLoading: boolean;
  /** `true` solo si el servidor devolvió un experimento guardado. */
  fromServer: boolean;
};

export function useDiaDExperimentTop(input: {
  instrumentId: string | null;
  timeframe: string;
  asOfDiaD: string | null;
}): DiaDExperimentTopState {
  const { instrumentId, timeframe, asOfDiaD } = input;
  const enabled = Boolean(instrumentId && asOfDiaD);

  const query = useQuery({
    queryKey: ["dia-d-experiment-top", instrumentId, timeframe, asOfDiaD],
    enabled,
    staleTime: 30_000,
    retry: false,
    queryFn: () =>
      api.getDiaDExperimentTop({
        instrumentId: instrumentId as string,
        timeframe,
        asOfDiaD: asOfDiaD as string,
      }),
  });

  const serverRow = query.data?.data ?? null;
  useEffect(() => {
    if (serverRow) hydrateDiaDExperimentTop(serverRow);
  }, [serverRow]);

  const revision = useSyncExternalStore(
    subscribeDiaDExperimentTop,
    getDiaDExperimentTopSnapshot,
    () => 0,
  );
  const record = useMemo(() => {
    if (!instrumentId || !asOfDiaD) return null;
    // `revision` invalida el memo cuando la hidratación mueve la caché local.
    void revision;
    return getDiaDExperimentTop(instrumentId, timeframe, asOfDiaD);
  }, [instrumentId, timeframe, asOfDiaD, revision]);

  return {
    record,
    isLoading: enabled && query.isLoading,
    fromServer: Boolean(serverRow),
  };
}
