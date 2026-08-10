/** Filtros Biblioteca · Mis estrategias (alcance S3 + búsqueda). */

import type { StrategyOrigin } from "@bolsa/shared";

export type MineStrategyScopeFilter =
  | "all"
  | "reusable"
  | "fitted"
  | "fitted_current";

export type MineStrategiesFilterState = {
  query: string;
  timeframe: string;
  origin: string;
  scope: MineStrategyScopeFilter;
  /** Filtro por instrumento ajustado (id). Vacío = todos. */
  instrumentId: string;
};

export type MineStrategyFilterable = {
  id: string;
  name: string;
  presetKey?: string | null;
  kind: string;
  timeframe: string;
  origin: string;
  instrumentIds?: string[] | null;
};

export const MINE_STRATEGY_ORIGIN_LABELS: Record<StrategyOrigin, string> = {
  manual: "Manual",
  assisted: "Asistida",
  ai_generated: "Prompt IA",
  imported: "Importada",
  preset: "Optimizada",
};

export function defaultMineStrategiesFilters(): MineStrategiesFilterState {
  return {
    query: "",
    timeframe: "",
    origin: "",
    scope: "all",
    instrumentId: "",
  };
}

export function strategyScopeKind(
  instrumentIds: string[] | undefined | null,
): "reusable" | "fitted" {
  return !instrumentIds || instrumentIds.length === 0 ? "reusable" : "fitted";
}

export function isMineStrategiesFilterActive(
  filters: MineStrategiesFilterState,
): boolean {
  return Boolean(
    filters.query.trim() ||
    filters.timeframe ||
    filters.origin ||
    filters.instrumentId ||
    filters.scope !== "all",
  );
}

export function filterMineStrategies<T extends MineStrategyFilterable>(
  strategies: T[],
  filters: MineStrategiesFilterState,
  opts?: {
    currentInstrumentId?: string | null;
    /** Para buscar por ticker (VIS, ACS…) además del id. */
    symbolById?: ReadonlyMap<string, string>;
  },
): T[] {
  const q = filters.query.trim().toLowerCase();
  const currentId = opts?.currentInstrumentId ?? null;
  const symbolById = opts?.symbolById;

  return strategies.filter((s) => {
    if (filters.timeframe && s.timeframe !== filters.timeframe) return false;
    if (filters.origin && s.origin !== filters.origin) return false;
    if (filters.instrumentId) {
      if (!(s.instrumentIds ?? []).includes(filters.instrumentId)) return false;
    }

    const scope = strategyScopeKind(s.instrumentIds);
    if (filters.scope === "reusable" && scope !== "reusable") return false;
    if (filters.scope === "fitted" && scope !== "fitted") return false;
    if (filters.scope === "fitted_current") {
      if (!currentId || !(s.instrumentIds ?? []).includes(currentId))
        return false;
    }

    if (!q) return true;
    const symbolLabels = (s.instrumentIds ?? [])
      .map((id) => symbolById?.get(id) ?? "")
      .filter(Boolean);
    const haystack = [
      s.name,
      s.kind,
      s.timeframe,
      s.origin,
      s.presetKey ?? "",
      ...symbolLabels,
      ...(s.instrumentIds ?? []),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}

/** Badge de alcance: Reutilizable | Ajuste · SYM | Ajuste · N valores */
export function formatStrategyScopeBadge(
  instrumentIds: string[] | undefined | null,
  symbolById: Map<string, string>,
): string {
  if (!instrumentIds?.length) return "Reutilizable";
  const labels = instrumentIds.map(
    (id) => symbolById.get(id) ?? id.slice(0, 8),
  );
  if (labels.length === 1) return `Ajuste · ${labels[0]}`;
  return `Ajuste · ${labels.length} valores`;
}

export function uniqueSortedValues(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "es"),
  );
}
