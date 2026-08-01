/**
 * Enriquecimiento hub Instrumentos I1 — listas (inverso) + posición cuenta activa.
 *
 * @see docs/engineering/instruments-hub-2026-07-31.md
 */

import type { PositionDto } from '@bolsa/shared';

export type HubListMembership = {
  listId: string;
  listName: string;
  source: string;
};

export type ListDetailForHub = {
  id: string;
  name: string;
  source: string;
  instrumentIds: string[];
};

/** Invierte detalle de listas → membresías por instrumentId (sin virtuales). */
export function invertListMemberships(
  lists: ListDetailForHub[],
): Map<string, HubListMembership[]> {
  const map = new Map<string, HubListMembership[]>();
  for (const list of lists) {
    const ref: HubListMembership = {
      listId: list.id,
      listName: list.name,
      source: list.source,
    };
    for (const instrumentId of list.instrumentIds) {
      const prev = map.get(instrumentId);
      if (prev) prev.push(ref);
      else map.set(instrumentId, [ref]);
    }
  }
  for (const [, refs] of map) {
    refs.sort((a, b) => a.listName.localeCompare(b.listName, undefined, { sensitivity: 'base' }));
  }
  return map;
}

export function indexPositionsByInstrument(
  positions: PositionDto[],
): Map<string, PositionDto> {
  const map = new Map<string, PositionDto>();
  for (const pos of positions) {
    if (pos.quantity === 0) continue;
    map.set(pos.instrumentId, pos);
  }
  return map;
}

export function membershipsForInstrument(
  map: Map<string, HubListMembership[]>,
  instrumentId: string,
): HubListMembership[] {
  return map.get(instrumentId) ?? [];
}

export function positionForInstrument(
  map: Map<string, PositionDto>,
  instrumentId: string,
): PositionDto | null {
  return map.get(instrumentId) ?? null;
}

/** Chips visibles + resto (orden: custom primero, luego nombre). */
export function pickListChips(
  memberships: HubListMembership[],
  maxVisible = 2,
): { visible: HubListMembership[]; overflow: number } {
  const ordered = [...memberships].sort((a, b) => {
    const ac = a.source === 'custom' ? 0 : 1;
    const bc = b.source === 'custom' ? 0 : 1;
    if (ac !== bc) return ac - bc;
    return a.listName.localeCompare(b.listName, undefined, { sensitivity: 'base' });
  });
  if (ordered.length <= maxVisible) return { visible: ordered, overflow: 0 };
  return {
    visible: ordered.slice(0, maxVisible),
    overflow: ordered.length - maxVisible,
  };
}
