/**
 * Quotes por lote: `POST /api/instruments/quotes` acepta como máximo 200 ids
 * (`InstrumentQuotesRequestDto.ids.max_length`). Visualizados puede superarlo con
 * facilidad (una pestaña abierta = un id), así que se trocea antes de llamar.
 *
 * Fusión todo-o-nada: si un lote falla, la consulta entera falla y la UI muestra
 * «Precios no actualizados». Una fusión parcial presentaría datos incompletos como
 * si estuvieran al día. Los ids se deduplican y se devuelven en el orden pedido,
 * sin repetidos aunque dos lotes devolvieran el mismo instrumento.
 *
 * @see packages/shared/src/batch-limits.ts
 */
import type { InstrumentWithMetaDto } from "@bolsa/shared";
import { chunkIds, INSTRUMENT_QUOTES_BATCH_LIMIT } from "@bolsa/shared";

import { api } from "@/lib/api";

export async function fetchInstrumentQuotesChunked(
  ids: string[],
): Promise<InstrumentWithMetaDto[]> {
  const unique = [...new Set(ids.filter(Boolean))];
  if (unique.length === 0) return [];

  const chunks = chunkIds(unique, INSTRUMENT_QUOTES_BATCH_LIMIT);
  // `Promise.all` rechaza si cualquier lote falla: nunca se devuelve una mezcla
  // de datos frescos y antiguos como si fuera una respuesta completa.
  const parts = await Promise.all(
    chunks.map((chunk) => api.getInstrumentQuotes(chunk)),
  );

  const byId = new Map<string, InstrumentWithMetaDto>();
  for (const part of parts) {
    for (const item of part.data ?? []) {
      if (!byId.has(item.id)) byId.set(item.id, item);
    }
  }

  return unique
    .map((id) => byId.get(id))
    .filter((item): item is InstrumentWithMetaDto => Boolean(item));
}
