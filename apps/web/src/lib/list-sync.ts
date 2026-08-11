import type { InstrumentListSummaryDto, ListPanelConfig } from "@bolsa/shared";
import {
  CATALOG_IBEX_LIST_ID,
  isVirtualListId,
  VIRTUAL_LIST_LABELS,
  VIRTUAL_LIST_PORTFOLIO,
} from "@bolsa/shared";
import type { QueryClient } from "@tanstack/react-query";

/** ID de lista activo válido (virtual o existente en API). */
export function resolveSelectedListId(
  apiListId: string | undefined,
  apiLists: InstrumentListSummaryDto[],
): string {
  if (apiListId && isVirtualListId(apiListId)) return apiListId;
  if (apiListId && apiLists.some((list) => list.id === apiListId))
    return apiListId;
  return (
    apiLists.find((list) => list.id === CATALOG_IBEX_LIST_ID)?.id ??
    apiLists.find((list) => list.name === "IBEX 35")?.id ??
    apiLists.find((list) => list.source === "catalog")?.id ??
    apiLists[0]?.id ??
    VIRTUAL_LIST_PORTFOLIO
  );
}

export function pruneCarouselListIds(
  carouselListIds: string[] | undefined,
  apiLists: InstrumentListSummaryDto[],
): string[] {
  if (apiLists.length === 0) return carouselListIds ?? [];
  const apiIds = new Set(apiLists.map((list) => list.id));
  return (carouselListIds ?? []).filter(
    (id) => !isVirtualListId(id) && apiIds.has(id),
  );
}

/**
 * Mantiene el carrusel tras reinicios: resuelve por nombre y recupera IBEX si el ID quedó obsoleto.
 * No poda cuando `apiLists` está vacío (la API aún no respondió).
 */
export function reconcileCarouselListIds(
  carouselListIds: string[] | undefined,
  carouselPinnedListNames: string[] | undefined,
  apiLists: InstrumentListSummaryDto[],
): string[] {
  if (apiLists.length === 0) return carouselListIds ?? [];

  const apiById = new Map(apiLists.map((list) => [list.id, list]));
  const apiByName = new Map(apiLists.map((list) => [list.name, list]));
  const pinned = (carouselListIds ?? []).filter((id) => !isVirtualListId(id));

  const targetNames = new Set(carouselPinnedListNames ?? []);
  for (const id of pinned) {
    const list = apiById.get(id);
    if (list) targetNames.add(list.name);
  }

  const next: string[] = [];
  const seen = new Set<string>();

  for (const name of targetNames) {
    const list = apiByName.get(name);
    if (list && !seen.has(list.id)) {
      seen.add(list.id);
      next.push(list.id);
    }
  }

  for (const id of pinned) {
    if (apiById.has(id) && !seen.has(id)) {
      seen.add(id);
      next.push(id);
    }
  }

  // Compat: solo IDs obsoletos sin nombres guardados (p. ej. IBEX tras reseed de BD).
  if (next.length === 0 && pinned.length > 0) {
    const ibex =
      apiById.get(CATALOG_IBEX_LIST_ID) ??
      apiLists.find((list) => list.name === "IBEX 35");
    if (ibex) next.push(ibex.id);
  }

  return next;
}

export function carouselPinnedNamesForIds(
  carouselListIds: string[] | undefined,
  apiLists: InstrumentListSummaryDto[],
): string[] {
  const apiById = new Map(apiLists.map((list) => [list.id, list]));
  const names: string[] = [];
  const seen = new Set<string>();
  for (const id of carouselListIds ?? []) {
    if (isVirtualListId(id)) continue;
    const name = apiById.get(id)?.name;
    if (name && !seen.has(name)) {
      seen.add(name);
      names.push(name);
    }
  }
  return names;
}

export function pickFallbackListId(
  apiLists: InstrumentListSummaryDto[],
  excludeId?: string,
): string {
  const candidates = apiLists.filter((list) => list.id !== excludeId);
  const catalog = candidates.find((list) => list.source === "catalog");
  if (catalog) return catalog.id;
  if (candidates[0]) return candidates[0].id;
  return VIRTUAL_LIST_PORTFOLIO;
}

export function listConfigForSelection(
  listId: string,
  apiLists: InstrumentListSummaryDto[],
): Pick<ListPanelConfig, "apiListId" | "name" | "source"> {
  if (isVirtualListId(listId)) {
    return {
      apiListId: listId,
      name: VIRTUAL_LIST_LABELS[listId],
      source: "virtual",
    };
  }
  const list = apiLists.find((item) => item.id === listId);
  if (!list) {
    return {
      apiListId: VIRTUAL_LIST_PORTFOLIO,
      name: VIRTUAL_LIST_LABELS[VIRTUAL_LIST_PORTFOLIO],
      source: "virtual",
    };
  }
  return { apiListId: list.id, name: list.name, source: "api" };
}

/** Tras borrar una lista API: cache, carrusel y selección activa. */
export function syncAfterListDeleted(
  queryClient: QueryClient,
  listId: string,
  listConfig: ListPanelConfig,
): Pick<
  ListPanelConfig,
  | "apiListId"
  | "name"
  | "source"
  | "carouselListIds"
  | "carouselPinnedListNames"
> {
  const oldLists =
    queryClient.getQueryData<{ data: InstrumentListSummaryDto[] }>(["lists"])
      ?.data ?? [];
  const deletedName = oldLists.find((list) => list.id === listId)?.name;

  queryClient.setQueryData<{ data: InstrumentListSummaryDto[] }>(
    ["lists"],
    (old) => ({
      data: (old?.data ?? []).filter((list) => list.id !== listId),
    }),
  );
  queryClient.removeQueries({ queryKey: ["list-quotes", listId] });
  queryClient.removeQueries({ queryKey: ["list", listId] });

  const apiLists =
    queryClient.getQueryData<{ data: InstrumentListSummaryDto[] }>(["lists"])
      ?.data ?? [];
  const carouselListIds = pruneCarouselListIds(
    (listConfig.carouselListIds ?? []).filter((id) => id !== listId),
    apiLists,
  );
  const carouselPinnedListNames = (
    listConfig.carouselPinnedListNames ?? []
  ).filter((name) => name !== deletedName);
  const fallbackId = pickFallbackListId(apiLists, listId);
  const selection = listConfigForSelection(
    listConfig.apiListId === listId
      ? fallbackId
      : (listConfig.apiListId ?? fallbackId),
    apiLists,
  );

  return { ...selection, carouselListIds, carouselPinnedListNames };
}
