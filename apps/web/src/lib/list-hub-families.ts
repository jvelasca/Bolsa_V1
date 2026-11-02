/**
 * Familia y tipo de una lista en el hub («Listas» de Mercado).
 *
 * Fuente única para que la fila y la agrupación no se contradigan: «Estudio» es la
 * lista canónica de supervisión (ADR-024), no una lista personal del usuario.
 *
 * @see packages/shared/src/default-lists.ts (ESTUDIO_LIST_ID)
 * @see docs/adr/024-estudio-supervision-universe.md
 */
import type { InstrumentListSummaryDto } from "@bolsa/shared";
import { isEstudioListId, isVirtualListId } from "@bolsa/shared";

export type ListHubFamilyId = "sistema" | "indices" | "personales";

export const LIST_HUB_FAMILY_ORDER: ListHubFamilyId[] = [
  "sistema",
  "indices",
  "personales",
];

export const LIST_HUB_FAMILY_LABEL: Record<ListHubFamilyId, string> = {
  sistema: "Sistema",
  indices: "Índices",
  personales: "Personales",
};

export type ListHubListType = "sistema" | "índice" | "copia" | "personal";

/** ¿Lista gobernada por el sistema (virtual o universo de supervisión)? */
export function isSystemList(list: InstrumentListSummaryDto): boolean {
  return (
    isVirtualListId(list.id) ||
    isEstudioListId(list.id) ||
    list.kind === "supervision_universe"
  );
}

export function listTypeLabel(list: InstrumentListSummaryDto): ListHubListType {
  if (isSystemList(list)) return "sistema";
  if (list.source === "catalog" || list.kind === "linked_universe")
    return "índice";
  if (list.kind === "snapshot") return "copia";
  return "personal";
}

export function listHubFamily(list: InstrumentListSummaryDto): ListHubFamilyId {
  if (isSystemList(list)) return "sistema";
  if (list.source === "catalog" || list.kind === "linked_universe")
    return "indices";
  return "personales";
}

export function groupListsByFamily(
  sorted: InstrumentListSummaryDto[],
): { id: ListHubFamilyId; label: string; lists: InstrumentListSummaryDto[] }[] {
  const buckets: Record<ListHubFamilyId, InstrumentListSummaryDto[]> = {
    sistema: [],
    indices: [],
    personales: [],
  };
  for (const list of sorted) {
    buckets[listHubFamily(list)].push(list);
  }
  return LIST_HUB_FAMILY_ORDER.filter((id) => buckets[id].length > 0).map(
    (id) => ({
      id,
      label: LIST_HUB_FAMILY_LABEL[id],
      lists: buckets[id],
    }),
  );
}
