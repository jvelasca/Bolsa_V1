import type { ExternalInstrumentSearchHitDto } from "@bolsa/shared";
import { normalizeIsin } from "@bolsa/shared";

const PREFERRED_EXCHANGES = [
  "NMS",
  "NYQ",
  "NASDAQ",
  "NYSE",
  "NGM",
  "BME",
  "MCE",
  "MAD",
];
export function rankCatalogInstrument(
  item: {
    symbol: string;
    yahooSymbol: string;
    name: string;
    isin?: string | null;
  },
  query: string,
): number {
  const q = query.trim().toLowerCase();
  const qIsin = normalizeIsin(query);
  let score = 0;
  if (item.isin && normalizeIsin(item.isin) === qIsin && qIsin.length >= 10)
    score += 200;
  else if (
    item.isin &&
    normalizeIsin(item.isin).includes(qIsin) &&
    qIsin.length >= 4
  )
    score += 120;
  if (item.symbol.toLowerCase() === q) score += 120;
  if (item.yahooSymbol.toLowerCase() === q) score += 110;
  if (item.symbol.toLowerCase().startsWith(q)) score += 40;
  if (item.name.toLowerCase().includes(q)) score += 20;
  return score;
}

/** Ordena hits Yahoo: coincidencia exacta y mercados principales primero. */
export function rankExternalSearchHit(
  hit: ExternalInstrumentSearchHitDto,
  query: string,
): number {
  const q = query.trim().toLowerCase();
  let score = 0;

  if (hit.symbol.toLowerCase() === q) score += 120;
  if (hit.yahooSymbol.toLowerCase() === q) score += 110;
  if (hit.symbol.toLowerCase().startsWith(q)) score += 40;
  if (!hit.yahooSymbol.includes(".")) score += 25;

  const exchange = hit.exchange.toUpperCase();
  const exchangeRank = PREFERRED_EXCHANGES.findIndex(
    (label) => exchange.includes(label) || label.includes(exchange),
  );
  if (exchangeRank >= 0) score += 60 - exchangeRank * 5;

  if (hit.currency === "USD" && exchangeRank <= 3) score += 15;

  return score;
}

export function sortExternalSearchHits(
  hits: ExternalInstrumentSearchHitDto[],
  query: string,
): ExternalInstrumentSearchHitDto[] {
  return [...hits].sort(
    (a, b) => rankExternalSearchHit(b, query) - rankExternalSearchHit(a, query),
  );
}
