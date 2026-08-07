/**
 * Sellos locales por instrumento × capa (vigilia / frescura / redisc.).
 *
 * Complementa Finalists freshness y cola CORE-R cuando el juicio no encola nada
 * (p. ej. «Actualizar» deja Vigilia en verde sin ítem en cola).
 *
 * Persistencia: `localStorage` `bolsa-estudio-lane-stamps-v1`.
 * Evento UI: `bolsa-estudio-lane-stamps` tras cada touch.
 *
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 * @see docs/adr/024-estudio-supervision-universe.md
 */

import type { EstudioProcessLaneId } from '@/features/trading/estudio-process-status';

export const ESTUDIO_LANE_STAMPS_KEY = 'bolsa-estudio-lane-stamps-v1';
export const ESTUDIO_LANE_STAMPS_EVENT = 'bolsa-estudio-lane-stamps';

export type EstudioLaneStampsMap = Record<
  string,
  Partial<Record<EstudioProcessLaneId, string>>
>;

export function loadEstudioLaneStamps(): EstudioLaneStampsMap {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(ESTUDIO_LANE_STAMPS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as EstudioLaneStampsMap;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function saveEstudioLaneStamps(map: EstudioLaneStampsMap): void {
  try {
    localStorage.setItem(ESTUDIO_LANE_STAMPS_KEY, JSON.stringify(map));
  } catch {
    // quota
  }
}

function emitEstudioLaneStampsChanged(): void {
  try {
    window.dispatchEvent(new CustomEvent(ESTUDIO_LANE_STAMPS_EVENT));
  } catch {
    // SSR / tests
  }
}

export function touchEstudioLaneStamp(
  instrumentId: string,
  lane: EstudioProcessLaneId,
  at = new Date().toISOString(),
): void {
  if (!instrumentId) return;
  const map = loadEstudioLaneStamps();
  map[instrumentId] = { ...map[instrumentId], [lane]: at };
  saveEstudioLaneStamps(map);
  emitEstudioLaneStampsChanged();
}

export function touchEstudioLaneStamps(
  instrumentIds: ReadonlyArray<string>,
  lane: EstudioProcessLaneId,
  at = new Date().toISOString(),
): void {
  const map = loadEstudioLaneStamps();
  for (const id of instrumentIds) {
    if (!id) continue;
    map[id] = { ...map[id], [lane]: at };
  }
  saveEstudioLaneStamps(map);
  emitEstudioLaneStampsChanged();
}

export function readEstudioLaneStamp(
  instrumentId: string,
  lane: EstudioProcessLaneId,
): string | null {
  const at = loadEstudioLaneStamps()[instrumentId]?.[lane];
  return typeof at === 'string' && at ? at : null;
}

/** El más reciente entre dos ISO. */
export function maxIso(a: string | null, b: string | null): string | null {
  if (!a) return b;
  if (!b) return a;
  return Date.parse(a) >= Date.parse(b) ? a : b;
}
