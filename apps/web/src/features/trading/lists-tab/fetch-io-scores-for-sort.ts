/**
 * Carga IO para ordenar Visualizados sin tumbar la API.
 * - Reutiliza chips en caché React Query (Operativa / hub).
 * - FA en un batch; Composite en trozos pequeños y secuenciales.
 */

import type { QueryClient } from "@tanstack/react-query";
import type { CompositeChipDto, FundamentalChipDto } from "@bolsa/shared";

import {
  chunkIds,
  indexFaScores,
  indexTaScores,
  type HubFaScore,
  type HubTaScore,
} from "@/features/instruments/instruments-hub-scores";
import { ioFromCompositeAndFa } from "@/features/trading/lists-tab/sort-visualizados-by-io";

/** Trozo pequeño: cada chip Composite puede ser caro (OHLCV + rating). */
export const IO_SORT_COMPOSITE_CHUNK = 4;
export const IO_SORT_FA_CHUNK = 40;

export type IoScoreFetchDeps = {
  queryFundamentals: (
    instrumentIds: string[],
  ) => Promise<{ data: FundamentalChipDto[] }>;
  queryComposite: (
    instrumentIds: string[],
  ) => Promise<{ data: CompositeChipDto[] }>;
  /** Opcional: ceder el event loop entre trozos. */
  yieldBetweenChunks?: () => Promise<void>;
};

export function collectCachedFaScores(
  queryClient: QueryClient,
): Map<string, HubFaScore> {
  const map = new Map<string, HubFaScore>();
  for (const [, data] of queryClient.getQueriesData<FundamentalChipDto[]>({
    queryKey: ["instrument-fundamentals-batch"],
  })) {
    if (!Array.isArray(data)) continue;
    for (const [id, score] of indexFaScores(data)) {
      map.set(id, score);
    }
  }
  return map;
}

export function collectCachedTaScores(
  queryClient: QueryClient,
): Map<string, HubTaScore> {
  const map = new Map<string, HubTaScore>();
  for (const [, data] of queryClient.getQueriesData<CompositeChipDto[]>({
    queryKey: ["instrument-composite-batch"],
  })) {
    if (!Array.isArray(data)) continue;
    for (const [id, score] of indexTaScores(data)) {
      map.set(id, score);
    }
  }
  return map;
}

async function defaultYield(): Promise<void> {
  await new Promise<void>((resolve) => {
    window.setTimeout(resolve, 0);
  });
}

/**
 * Devuelve Map instrumentId → IO (null si no hay score).
 * Nunca lanza por un trozo fallido: sigue con el resto.
 */
export async function fetchIoByInstrumentIds(
  instrumentIds: ReadonlyArray<string>,
  deps: IoScoreFetchDeps,
  seed?: {
    fa?: ReadonlyMap<string, HubFaScore>;
    ta?: ReadonlyMap<string, HubTaScore>;
  },
): Promise<Map<string, number | null>> {
  const ids = [...new Set(instrumentIds.filter(Boolean))];
  const faById = new Map<string, HubFaScore>(seed?.fa ?? []);
  const taById = new Map<string, HubTaScore>(seed?.ta ?? []);
  const yieldChunk = deps.yieldBetweenChunks ?? defaultYield;

  const missingFa = ids.filter((id) => !faById.has(id));
  for (const chunk of chunkIds(missingFa, IO_SORT_FA_CHUNK)) {
    if (chunk.length === 0) continue;
    try {
      const res = await deps.queryFundamentals(chunk);
      for (const [id, score] of indexFaScores(res.data ?? [])) {
        faById.set(id, score);
      }
    } catch {
      // FA opcional para el suelo distress; seguimos.
    }
    await yieldChunk();
  }

  const missingTa = ids.filter((id) => !taById.has(id));
  for (const chunk of chunkIds(missingTa, IO_SORT_COMPOSITE_CHUNK)) {
    if (chunk.length === 0) continue;
    try {
      const res = await deps.queryComposite(chunk);
      for (const [id, score] of indexTaScores(res.data ?? [])) {
        taById.set(id, score);
      }
    } catch {
      // Si el trozo falla, intenta 1×1 para no perder el resto.
      for (const id of chunk) {
        try {
          const res = await deps.queryComposite([id]);
          for (const [chipId, score] of indexTaScores(res.data ?? [])) {
            taById.set(chipId, score);
          }
        } catch {
          // IO null para este id
        }
        await yieldChunk();
      }
    }
    await yieldChunk();
  }

  const out = new Map<string, number | null>();
  for (const id of ids) {
    const fa = faById.get(id);
    const ta = taById.get(id);
    out.set(
      id,
      ioFromCompositeAndFa({
        compositeDisplay100: ta?.compositeDisplay100,
        distress: fa?.distress,
      }),
    );
  }
  return out;
}
