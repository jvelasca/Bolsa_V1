import type { InstrumentListSummaryDto, ListPanelConfig } from "@bolsa/shared";
import { isVirtualListId } from "@bolsa/shared";

export function isListPinnedInCarousel(
  listId: string,
  listConfig: ListPanelConfig,
): boolean {
  if (isVirtualListId(listId)) {
    return !(listConfig.carouselHiddenListIds ?? []).includes(listId);
  }
  return (listConfig.carouselListIds ?? []).includes(listId);
}

export function patchToggleCarouselList(
  listId: string,
  listConfig: ListPanelConfig,
  apiLists: InstrumentListSummaryDto[],
): Partial<ListPanelConfig> {
  if (isVirtualListId(listId)) {
    const hidden = new Set(listConfig.carouselHiddenListIds ?? []);
    if (hidden.has(listId)) hidden.delete(listId);
    else hidden.add(listId);
    return { carouselHiddenListIds: [...hidden], carouselInitialized: true };
  }

  const list = apiLists.find((entry) => entry.id === listId);
  const pinnedIds = new Set(listConfig.carouselListIds ?? []);
  const pinnedNames = new Set(listConfig.carouselPinnedListNames ?? []);

  if (pinnedIds.has(listId)) {
    pinnedIds.delete(listId);
    if (list?.name) pinnedNames.delete(list.name);
  } else {
    pinnedIds.add(listId);
    if (list?.name) pinnedNames.add(list.name);
  }

  return {
    carouselListIds: [...pinnedIds],
    carouselPinnedListNames: [...pinnedNames],
    carouselInitialized: true,
  };
}
