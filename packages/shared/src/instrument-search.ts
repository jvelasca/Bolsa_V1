export interface SearchableInstrument {
  symbol: string;
  name: string;
  yahooSymbol: string;
  isin?: string | null;
}

/** Normaliza ISIN: mayúsculas y sin espacios ni guiones. */
export function normalizeIsin(value: string): string {
  return value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
}

export function looksLikeIsinQuery(query: string): boolean {
  const normalized = normalizeIsin(query);
  return normalized.length >= 10 && /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(normalized);
}

export function instrumentMatchesSearchQuery(
  item: SearchableInstrument,
  query: string,
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;

  const qIsin = normalizeIsin(query);
  if (item.isin) {
    const itemIsin = normalizeIsin(item.isin);
    if (item.isin.toLowerCase().includes(q) || itemIsin.includes(qIsin)) {
      return true;
    }
  }

  return (
    item.symbol.toLowerCase().includes(q) ||
    item.name.toLowerCase().includes(q) ||
    item.yahooSymbol.toLowerCase().includes(q)
  );
}
