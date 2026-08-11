/**
 * Ordenación de filas de lista incluyendo columnas de recomendación (IO/TA/FA/★/postura).
 */

import type {
  InstrumentWithMetaDto,
  ListColumnId,
  ListSortState,
} from "@bolsa/shared";
import { RECOMMENDATION_OPTIONAL_LIST_COLUMNS } from "@bolsa/shared";

import { sortInstrumentList } from "@/lib/list-utils";
import type { ListRecommendationRow } from "@/features/trading/lists-tab/list-recommendation-scores-context";

export function isRecommendationSortColumn(columnId: ListColumnId): boolean {
  return (RECOMMENDATION_OPTIONAL_LIST_COLUMNS as readonly string[]).includes(
    columnId,
  );
}

function recommendationSortValue(
  row: ListRecommendationRow | undefined,
  column: ListColumnId,
): string | number {
  if (!row) {
    if (column === "recStance") return "";
    return Number.NEGATIVE_INFINITY;
  }
  switch (column) {
    case "ioScore":
      return row.io ?? Number.NEGATIVE_INFINITY;
    case "taScore":
      return row.ta ?? Number.NEGATIVE_INFINITY;
    case "faScore":
      return row.fa ?? Number.NEGATIVE_INFINITY;
    case "dictamenStars":
      return row.dictamenStars ?? Number.NEGATIVE_INFINITY;
    case "recStance":
      return (row.stanceLabel ?? row.stance ?? "").toLowerCase();
    default:
      return Number.NEGATIVE_INFINITY;
  }
}

export function sortInstrumentListWithRecommendation(
  items: InstrumentWithMetaDto[],
  sort: ListSortState | undefined,
  scores?: ReadonlyMap<string, ListRecommendationRow>,
): InstrumentWithMetaDto[] {
  if (!sort) return items;
  if (!isRecommendationSortColumn(sort.column) || !scores) {
    return sortInstrumentList(items, sort);
  }
  const factor = sort.direction === "asc" ? 1 : -1;
  return [...items].sort((a, b) => {
    const va = recommendationSortValue(scores.get(a.id), sort.column);
    const vb = recommendationSortValue(scores.get(b.id), sort.column);
    if (typeof va === "number" && typeof vb === "number") {
      if (va !== vb) return (va - vb) * factor;
      return a.symbol.localeCompare(b.symbol, "es");
    }
    const cmp = String(va).localeCompare(String(vb), "es") * factor;
    return cmp !== 0 ? cmp : a.symbol.localeCompare(b.symbol, "es");
  });
}
