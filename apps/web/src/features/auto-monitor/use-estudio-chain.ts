/**
 * AUTO · ESTUDIO — evidencia de la CADENA durable por valor (read-only).
 *
 * Una sola query por informe (`GET /auto/estudio-chain`), indexada por `instrumentId`: la
 * ficha diaria no hace 35 peticiones ni recalcula nada. El lector del backend reutiliza el
 * MISMO `auto_chain_durable_reader`; aquí solo se indexa y se declaran los huecos.
 *
 * `available=false` con `error` NO es «lista vacía»: es un fallo declarado que la UI muestra
 * como alerta. Un valor sin ciclos llega con `measured=false` y `cycles=[]` (hueco declarado).
 */

import { useQuery } from "@tanstack/react-query";
import type {
  EstudioChainResponseV1,
  EstudioChainValueV1,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

export function estudioChainQueryKey(
  accountId: string | null,
  asOf: string | null,
) {
  return ["auto-estudio-chain", accountId, asOf] as const;
}

/**
 * Evidencia durable de la cadena para la cuenta activa.
 *
 * Se habilita solo cuando hay cuenta y parte (`asOf`), de modo que abrir el panel no lanza
 * una consulta que nadie va a leer. `staleTime` alto: los hechos durables no cambian por
 * navegar; se invalida al terminar un job.
 */
export function useEstudioChain(asOf: string | null) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery({
    queryKey: estudioChainQueryKey(effectiveAccountId, asOf),
    queryFn: () => api.getAutoEstudioChain({ limit: 200 }),
    enabled: Boolean(effectiveAccountId && asOf),
    staleTime: 30_000,
    retry: false,
  });
}

/** Índice `instrumentId → evidencia del valor`. Un valor ausente queda sin entrada. */
export function indexChainValuesByInstrument(
  chain: EstudioChainResponseV1 | null | undefined,
): Map<string, EstudioChainValueV1> {
  const out = new Map<string, EstudioChainValueV1>();
  for (const value of chain?.values ?? []) {
    const id = value.instrumentId?.trim();
    if (id) out.set(id, value);
  }
  return out;
}

/**
 * Normaliza la respuesta del endpoint antes de leerla.
 *
 * Un `{ data: [] }` (fallback de un mock, un proxy o una versión antigua del servidor) NO es un
 * `EstudioChainResponseV1`: si se usara tal cual, `chain.available` sería `undefined` y leer
 * `chain.notes.join(...)` tumbaría la ficha entera. Aquí se declara el hueco (`null`) y se
 * conserva el objeto sólo si tiene forma de respuesta.
 */
export function normalizeEstudioChain(
  raw: EstudioChainResponseV1 | null | undefined,
): EstudioChainResponseV1 | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const candidate = raw as EstudioChainResponseV1;
  return Array.isArray(candidate.values)
    ? candidate
    : { ...candidate, values: [] };
}

/**
 * Día del DÍA-D del valor: `entryDay` del ciclo más reciente si existe; si no, la vela del
 * parte. Devuelve también de dónde salió para que la UI lo declare (no se adivina).
 */
export function diaDValueDay(input: {
  chainValue: EstudioChainValueV1 | undefined;
  barDate: string | null;
}): { day: string | null; source: "cycle" | "bar" | "none" } {
  const cycles = input.chainValue?.cycles ?? [];
  const withDay = cycles
    .map((cycle) => cycle.entryDay ?? null)
    .filter((entry): entry is string => Boolean(entry && entry.trim()));
  if (withDay.length > 0) {
    return { day: withDay[withDay.length - 1] as string, source: "cycle" };
  }
  const bar = (input.barDate ?? "").trim();
  if (bar) return { day: bar, source: "bar" };
  return { day: null, source: "none" };
}

/** Frase obligatoria: la cadena es histórica del valor salvo identidad estable. */
export const CHAIN_NOT_ATTRIBUTED_LABEL =
  "Cadena histórica del valor; no atribuida a esta señal";

/** `CONFIRMED` no se emite nunca desde esta superficie. */
export const CHAIN_CONFIRMED_FORBIDDEN = "CONFIRMED";
