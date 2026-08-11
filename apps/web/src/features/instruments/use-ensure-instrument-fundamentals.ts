/**
 * Al seleccionar un instrumento: si no hay snapshot FA útil, dispara sync Yahoo
 * y expone estado legible (cargando / buscando / listo / vacío / error).
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FundamentalCardDto } from "@bolsa/shared";
import { api, ApiError } from "@/lib/api";

export type FundamentalsEnsureStatus =
  | "idle"
  | "loading"
  | "refreshing"
  | "ready"
  | "empty"
  | "error";

/** Evita reintentos en bucle por instrumento en esta sesión de pestaña. */
const autoRefreshAttempted = new Set<string>();

/** Sync en curso compartido entre montajes (barra gráfico + diálogo + panel FA). */
const autoRefreshingIds = new Set<string>();
const refreshListeners = new Set<() => void>();

function notifyRefreshListeners() {
  for (const listener of refreshListeners) listener();
}

function markRefreshing(id: string, active: boolean) {
  if (active) autoRefreshingIds.add(id);
  else autoRefreshingIds.delete(id);
  notifyRefreshListeners();
}

export function fundamentalsSnapshotMissing(
  card: FundamentalCardDto | null | undefined,
): boolean {
  if (!card) return true;
  // Respuesta as-of bloqueada o reconstruida: no auto-refresh.
  if (card.metadata?.pointInTime === "blocked") return false;
  if (card.metadata?.pointInTime === "reconstructed") return false;
  if (!card.metadata?.fetchedAt) return true;
  const f = card.facts;
  const hasCore =
    f?.trailingPe != null ||
    f?.forwardPe != null ||
    f?.marketCap != null ||
    f?.roe != null ||
    (typeof f?.sector === "string" && f.sector.trim().length > 0);
  if (!hasCore && card.scoreDisplay100 == null) return true;
  return false;
}

export function useEnsureInstrumentFundamentals(
  instrumentId: string | undefined | null,
  opts?: { asOf?: string | null },
) {
  const queryClient = useQueryClient();
  const lastIdRef = useRef<string | null>(null);
  const [, bump] = useState(0);
  const asOf = opts?.asOf?.trim() || undefined;

  useEffect(() => {
    const listener = () => bump((n) => n + 1);
    refreshListeners.add(listener);
    return () => {
      refreshListeners.delete(listener);
    };
  }, []);

  const query = useQuery({
    queryKey: ["instrument-fundamentals", instrumentId, asOf ?? null],
    queryFn: () =>
      api.getInstrumentFundamentals(instrumentId!, asOf ? { asOf } : undefined),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
  });

  const refreshMutation = useMutation({
    mutationFn: async (id: string) => {
      autoRefreshAttempted.add(id);
      markRefreshing(id, true);
      try {
        return await api.syncInstrument(id, 5);
      } finally {
        markRefreshing(id, false);
      }
    },
    onSuccess: async (_data, id) => {
      await queryClient.invalidateQueries({
        queryKey: ["instrument-fundamentals", id],
      });
      await queryClient.invalidateQueries({
        queryKey: ["instrument-composite", id],
      });
      await queryClient.invalidateQueries({
        queryKey: ["instrument-profile", id],
      });
    },
  });

  const card = query.data?.data ?? null;
  const missing =
    !query.isLoading && !query.isError && fundamentalsSnapshotMissing(card);
  const sharedRefreshing = Boolean(
    instrumentId && autoRefreshingIds.has(instrumentId),
  );
  const asOfPast = Boolean(asOf);

  useEffect(() => {
    if (!instrumentId) return;
    if (asOfPast) return; // DÍA D: no refrescar Yahoo (look-ahead).
    if (lastIdRef.current !== instrumentId) {
      lastIdRef.current = instrumentId;
      refreshMutation.reset();
    }
    if (query.isLoading || query.isFetching) return;
    if (query.isError) return;
    if (!fundamentalsSnapshotMissing(card)) return;
    if (autoRefreshAttempted.has(instrumentId)) return;
    if (sharedRefreshing || refreshMutation.isPending) return;
    // Marcar antes de mutate: varios montajes comparten la misma clave.
    autoRefreshAttempted.add(instrumentId);
    markRefreshing(instrumentId, true);
    refreshMutation.mutate(instrumentId);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al cambiar id / llegada de card vacía
  }, [
    instrumentId,
    asOfPast,
    query.isLoading,
    query.isFetching,
    query.isError,
    card,
    missing,
    sharedRefreshing,
  ]);

  let status: FundamentalsEnsureStatus = "idle";
  let statusLabel = "";

  if (!instrumentId) {
    status = "idle";
    statusLabel = "";
  } else if (sharedRefreshing || refreshMutation.isPending) {
    status = "refreshing";
    statusLabel = "Buscando / actualizando fundamentales (Yahoo)…";
  } else if (query.isLoading) {
    status = "loading";
    statusLabel = "Cargando análisis fundamental…";
  } else if (query.isError || refreshMutation.isError) {
    status = "error";
    const err = refreshMutation.error ?? query.error;
    statusLabel =
      err instanceof ApiError
        ? `No se pudo actualizar FA: ${err.message}`
        : err instanceof Error
          ? `No se pudo actualizar FA: ${err.message}`
          : "No se pudo cargar ni actualizar el análisis fundamental.";
  } else if (card?.metadata?.pointInTime === "blocked") {
    status = "ready";
    statusLabel = asOf
      ? `FA bloqueada a DÍA D ${asOf} (sin pack de estados; refresca FA)`
      : "FA bloqueada (sin look-ahead)";
  } else if (card?.metadata?.pointInTime === "reconstructed") {
    status = "ready";
    statusLabel = asOf
      ? `FA reconstruida as-of ${asOf} (estados ≤ D)`
      : "FA reconstruida as-of";
  } else if (fundamentalsSnapshotMissing(card)) {
    status = "empty";
    statusLabel = autoRefreshAttempted.has(instrumentId)
      ? "Sin datos FA: Yahoo no devolvió un snapshot usable para este valor."
      : "Sin datos FA todavía.";
  } else {
    status = "ready";
    statusLabel = card?.metadata?.isStale
      ? `FA disponible (datos obsoletos${card.metadata.staleDays != null ? `, ${card.metadata.staleDays} d` : ""})`
      : asOf && card?.metadata?.pointInTime === "snapshot"
        ? `FA as-of ${asOf} (snapshot ≤ D)`
        : "FA disponible";
  }

  return {
    card,
    status,
    statusLabel,
    isRefreshing: sharedRefreshing || refreshMutation.isPending,
    missing: fundamentalsSnapshotMissing(card),
    refetch: () => (instrumentId ? query.refetch() : Promise.resolve()),
    refreshNow: () => {
      if (!instrumentId || asOfPast) return;
      autoRefreshAttempted.delete(instrumentId);
      refreshMutation.mutate(instrumentId);
    },
    query,
    refreshMutation,
  };
}
