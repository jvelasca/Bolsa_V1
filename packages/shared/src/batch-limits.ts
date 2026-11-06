/**
 * Topes de lote de los endpoints batch (`max_length` de los DTOs de FastAPI).
 *
 * Fuente única backend ↔ frontend: si el API cambia un tope, se cambia aquí y los
 * consumidores trocean con `chunkIds` en vez de recibir un 422 silencioso.
 *
 * @see apps/api-python/src/bolsa_api/schemas/instruments.py (InstrumentQuotesRequestDto)
 * @see apps/api-python/src/bolsa_api/schemas/instrument_daily_opinions.py (QueryInstrumentDailyOpinionsDto)
 * @see apps/api-python/src/bolsa_api/schemas/fundamental_card.py (QueryInstrumentFundamentalsDto)
 * @see apps/api-python/src/bolsa_api/schemas/composite_card.py (QueryInstrumentCompositeDto)
 */

/** `POST /api/instruments/quotes` — `ids` (máx. 200). */
export const INSTRUMENT_QUOTES_BATCH_LIMIT = 200;

/** `POST /api/instrument-daily-opinions/query` — `instrumentIds` (máx. 200). */
export const DAILY_OPINIONS_BATCH_LIMIT = 200;

/** `POST /api/instruments/fundamentals/query` — `instrumentIds` (máx. 80). */
export const FUNDAMENTALS_BATCH_LIMIT = 80;

/** `POST /api/instruments/composite/query` — `instrumentIds` (máx. 40). */
export const COMPOSITE_BATCH_LIMIT = 40;

/** Trocea una lista de ids en lotes del tamaño indicado (nunca devuelve lotes vacíos). */
export function chunkIds(ids: string[], size: number): string[][] {
  if (size <= 0) return ids.length > 0 ? [ids] : [];
  const out: string[][] = [];
  for (let i = 0; i < ids.length; i += size) {
    out.push(ids.slice(i, i + size));
  }
  return out;
}
