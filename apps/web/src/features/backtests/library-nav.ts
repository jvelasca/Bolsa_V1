/**
 * Deep-links Biblioteca (Backtesting → Estrategias).
 *
 * /backtests?tab=strategies&library=mine|optimized|generics&strategyId=<id>
 */

import {
  normalizeStrategiesListFilter,
  type StrategiesListFilter,
} from "@/features/backtests/library-strategy-buckets";

export type LibraryFilterParam = StrategiesListFilter;

export type LibraryNavTarget = {
  library: LibraryFilterParam;
  strategyId?: string;
  preset?: string;
  q?: string;
};

export function parseLibraryFilterParam(
  raw: string | null | undefined,
): LibraryFilterParam | null {
  if (raw == null || raw === "") return null;
  const n = normalizeStrategiesListFilter(raw);
  // normalize maps unknown → all; only accept exact known tokens
  if (
    raw === "all" ||
    raw === "generics" ||
    raw === "optimized" ||
    raw === "mine" ||
    raw === "finalists"
  ) {
    return n;
  }
  return null;
}

/** Href relativo para abrir/enfocar una estrategia en Biblioteca. */
export function backtestLibraryHref(target: LibraryNavTarget): string {
  const params = new URLSearchParams();
  params.set("tab", "strategies");
  params.set("library", target.library);
  if (target.strategyId) params.set("strategyId", target.strategyId);
  if (target.preset) params.set("preset", target.preset);
  if (target.q?.trim()) params.set("q", target.q.trim());
  return `/backtests?${params.toString()}`;
}

export function libraryHrefForSavedStrategy(
  strategyId: string,
  library: "mine" | "optimized" = "mine",
): string {
  return backtestLibraryHref({ library, strategyId });
}

export function libraryHrefForOptimizedStrategy(strategyId: string): string {
  return backtestLibraryHref({ library: "optimized", strategyId });
}

export function libraryHrefForPreset(presetKey: string): string {
  return backtestLibraryHref({ library: "generics", preset: presetKey });
}

export function parseLibraryNavFromSearch(
  searchParams: URLSearchParams,
): LibraryNavTarget | null {
  if (searchParams.get("tab") !== "strategies") return null;
  const library = parseLibraryFilterParam(searchParams.get("library")) ?? "all";
  const strategyId = searchParams.get("strategyId") ?? undefined;
  const preset = searchParams.get("preset") ?? undefined;
  const q = searchParams.get("q") ?? undefined;
  return {
    library,
    strategyId: strategyId || undefined,
    preset: preset || undefined,
    q: q || undefined,
  };
}
