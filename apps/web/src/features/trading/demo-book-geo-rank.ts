/**
 * Ranker geográfico suave del libro DEMO (óptimo → país → EU → mundo).
 *
 * Nunca filtra candidatos: solo ordena. Preferencia en `demo-book-prefs.countryPrefer`.
 *
 * @see docs/engineering/demo-operating-modes-brief-2026-08-03.md §4
 */

import type { DemoBookCountryPrefer } from "@/features/trading/demo-book-prefs";

/** Países / mercados tratados como Europa para preferencia suave. */
export const EUROPE_COUNTRIES: ReadonlySet<string> = new Set([
  "ES",
  "DE",
  "FR",
  "IT",
  "PT",
  "NL",
  "BE",
  "AT",
  "IE",
  "FI",
  "SE",
  "DK",
  "NO",
  "CH",
  "GB",
  "PL",
  "LU",
  "GR",
]);

export type GeoTier = 0 | 1 | 2;

export type GeoRankable = {
  instrumentId: string;
  /** Score óptimo (combined / TA / conviction). Mayor = mejor. */
  optimalScore: number;
  country?: string | null;
  /** Desempate estable (p. ej. enqueuedAt ISO). */
  tieBreak?: string;
};

export type GeoRankContext = {
  prefer: DemoBookCountryPrefer;
  homeCountry: string;
  countryByInstrumentId?: ReadonlyMap<string, string>;
};

/** Inferencia v1: EUR → ES; USD → US; GBP → GB; resto → ES (producto IBEX-first). */
export function inferHomeCountry(opts: {
  accountCurrency?: string | null;
  positionCountries?: readonly string[] | null;
}): string {
  const fromPositions = modeCountry(opts.positionCountries);
  if (fromPositions) return fromPositions;
  const ccy = (opts.accountCurrency ?? "").trim().toUpperCase();
  if (ccy === "EUR") return "ES";
  if (ccy === "USD") return "US";
  if (ccy === "GBP") return "GB";
  if (ccy === "CHF") return "CH";
  return "ES";
}

function modeCountry(
  list: readonly string[] | null | undefined,
): string | null {
  if (!list?.length) return null;
  const counts = new Map<string, number>();
  for (const raw of list) {
    const c = normalizeCountry(raw);
    if (!c) continue;
    counts.set(c, (counts.get(c) ?? 0) + 1);
  }
  let best: string | null = null;
  let n = 0;
  for (const [c, v] of counts) {
    if (v > n) {
      best = c;
      n = v;
    }
  }
  return best;
}

export function normalizeCountry(
  raw: string | null | undefined,
): string | null {
  if (raw == null) return null;
  const c = raw.trim().toUpperCase();
  return c.length >= 2 ? c.slice(0, 2) : null;
}

/**
 * 0 = home (o EU si europe_first), 1 = Europa, 2 = mundo.
 * `global_ok` → siempre 0 (geo no discrimina).
 */
export function geoTier(
  country: string | null | undefined,
  homeCountry: string,
  prefer: DemoBookCountryPrefer,
): GeoTier {
  if (prefer === "global_ok") return 0;
  const c = normalizeCountry(country);
  const home = normalizeCountry(homeCountry) ?? "ES";
  if (!c) return 2;
  if (prefer === "europe_first") {
    if (EUROPE_COUNTRIES.has(c)) return 0;
    return 2;
  }
  // home_first
  if (c === home) return 0;
  if (EUROPE_COUNTRIES.has(c)) return 1;
  return 2;
}

function resolveCountry(item: GeoRankable, ctx: GeoRankContext): string | null {
  return (
    normalizeCountry(item.country) ??
    normalizeCountry(ctx.countryByInstrumentId?.get(item.instrumentId)) ??
    null
  );
}

/** Comparador: score óptimo ↓, luego geo tier ↑, luego tieBreak ↑. */
export function compareByOptimalThenGeo(
  a: GeoRankable,
  b: GeoRankable,
  ctx: GeoRankContext,
): number {
  const scoreDiff = (b.optimalScore ?? 0) - (a.optimalScore ?? 0);
  if (Math.abs(scoreDiff) > 1e-9) return scoreDiff;
  const ta = geoTier(resolveCountry(a, ctx), ctx.homeCountry, ctx.prefer);
  const tb = geoTier(resolveCountry(b, ctx), ctx.homeCountry, ctx.prefer);
  if (ta !== tb) return ta - tb;
  return (a.tieBreak ?? "").localeCompare(b.tieBreak ?? "");
}

/** Copia ordenada; no muta ni filtra. */
export function rankByOptimalThenGeo<T extends GeoRankable>(
  items: readonly T[],
  ctx: GeoRankContext,
): T[] {
  return [...items].sort((a, b) => compareByOptimalThenGeo(a, b, ctx));
}

/** Extrae score óptimo de un payload F3 / Recommendation. */
export function optimalScoreFromPayload(payload: {
  combinedScore?: number | null;
  scoreTa?: number | null;
  metrics?: { conviction?: number | null } | null;
}): number {
  if (
    typeof payload.combinedScore === "number" &&
    Number.isFinite(payload.combinedScore)
  ) {
    return payload.combinedScore;
  }
  if (typeof payload.scoreTa === "number" && Number.isFinite(payload.scoreTa)) {
    return payload.scoreTa;
  }
  const c = payload.metrics?.conviction;
  if (typeof c === "number" && Number.isFinite(c)) return c;
  return 0;
}
