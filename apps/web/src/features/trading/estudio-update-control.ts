/**
 * Control de pausa suave para Actualizar/alta Estudio y puente a Lista AUTO.
 *
 * - Actualizar/alta: termina el valor en curso → queda en pausa con checkpoint (▶ reanuda).
 * - Lista AUTO (Lab): evento → BacktestsPage pause/resume de campaña.
 *
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 */

import { ESTUDIO_LIST_ID } from "@bolsa/shared";
import { useListAutoActivityStore } from "@/stores/list-auto-activity-store";

export const LIST_AUTO_SOFT_PAUSE_EVENT = "bolsa-list-auto-soft-pause";
export const LIST_AUTO_SOFT_RESUME_EVENT = "bolsa-list-auto-soft-resume";
/** Reanudar Actualizar/alta pausado (checkpoint local). */
export const ESTUDIO_UPDATE_RESUME_EVENT = "bolsa-estudio-update-resume";

export type EstudioUpdatePauseCheckpoint = {
  /** Lista completa del lote. */
  ids: string[];
  /** Siguiente índice a sincronizar (ids.length = sync hecho; falta vigilia/Lab). */
  nextIndex: number;
  rediscover: boolean;
  phaseLabel: string;
  symbols: Record<string, string>;
};

let softStopRequested = false;
let pauseCheckpoint: EstudioUpdatePauseCheckpoint | null = null;

export function beginEstudioUpdateRun(): void {
  softStopRequested = false;
  pauseCheckpoint = null;
}

export function clearEstudioUpdateSoftStop(): void {
  softStopRequested = false;
}

export function isEstudioUpdateSoftStopRequested(): boolean {
  return softStopRequested;
}

export function getEstudioUpdatePauseCheckpoint(): EstudioUpdatePauseCheckpoint | null {
  return pauseCheckpoint;
}

export function clearEstudioUpdatePauseCheckpoint(): void {
  pauseCheckpoint = null;
}

export function hasEstudioUpdatePauseCheckpoint(): boolean {
  return pauseCheckpoint != null && pauseCheckpoint.ids.length > 0;
}

/** Pide parar tras el valor en curso. Devuelve el símbolo anunciado. */
export function requestEstudioUpdateSoftStop(): { symbol: string } {
  softStopRequested = true;
  const symbol = useListAutoActivityStore.getState().symbol || "…";
  return { symbol };
}

/**
 * Persiste pausa tras terminar el valor en curso.
 * Mantiene la barra activa con ▶ para reanudar.
 */
export function settleEstudioUpdatePause(opts: {
  ids: readonly string[];
  nextIndex: number;
  rediscover: boolean;
  phaseLabel: string;
  symbolOf: (id: string) => string;
}): void {
  const ids = [...opts.ids];
  const nextIndex = Math.max(0, Math.min(opts.nextIndex, ids.length));
  const symbols: Record<string, string> = {};
  for (const id of ids) symbols[id] = opts.symbolOf(id);

  pauseCheckpoint = {
    ids,
    nextIndex,
    rediscover: opts.rediscover,
    phaseLabel: opts.phaseLabel,
    symbols,
  };
  softStopRequested = false;

  const remaining = Math.max(0, ids.length - nextIndex);
  const nextId = ids[nextIndex] ?? ids[nextIndex - 1] ?? ids[0];
  const symbol = nextId ? opts.symbolOf(nextId) : "…";
  const label =
    remaining > 0
      ? `Pausa · ${symbol} · quedan ${remaining}`
      : `Pausa · ${symbol} · falta Lab`;

  useListAutoActivityStore.getState().publish({
    active: true,
    paused: true,
    listId: ESTUDIO_LIST_ID,
    listName: "Estudio",
    index: Math.max(0, nextIndex - 1),
    total: Math.max(ids.length, 1),
    symbol,
    detail: label,
  });
}

export function requestListAutoSoftPause(): void {
  try {
    window.dispatchEvent(new CustomEvent(LIST_AUTO_SOFT_PAUSE_EVENT));
  } catch {
    // SSR / tests
  }
}

export function requestListAutoSoftResume(): void {
  try {
    window.dispatchEvent(new CustomEvent(LIST_AUTO_SOFT_RESUME_EVENT));
  } catch {
    // SSR / tests
  }
}

export function requestEstudioUpdateResume(): void {
  try {
    window.dispatchEvent(new CustomEvent(ESTUDIO_UPDATE_RESUME_EVENT));
  } catch {
    // SSR / tests
  }
}

/**
 * Pausa suave desde el banner Estudio:
 * - si hay Actualizar/alta en curso → soft-stop cooperativo
 * - si no, pausa Lista AUTO (Lab)
 */
export function requestEstudioBannerSoftPause(): {
  mode: "update" | "list_auto";
  symbol: string;
} {
  const snap = useListAutoActivityStore.getState();
  const detail = snap.detail ?? "";
  const isLocalUpdate =
    snap.active &&
    !snap.paused &&
    (detail.startsWith("Actualizar") ||
      detail.startsWith("Redescubrir") ||
      detail.startsWith("Alta Estudio") ||
      detail.startsWith("Termina "));

  if (isLocalUpdate) {
    const { symbol } = requestEstudioUpdateSoftStop();
    const announce = `Termina ${symbol} y para…`;
    snap.publish({
      active: true,
      paused: true,
      listId: snap.listId,
      listName: snap.listName,
      index: snap.index,
      total: snap.total,
      symbol,
      detail: announce,
    });
    return { mode: "update", symbol };
  }

  const symbol = snap.symbol || "…";
  requestListAutoSoftPause();
  if (snap.active) {
    snap.publish({
      ...snap,
      active: true,
      paused: true,
      detail: `Termina ${symbol} y para…`,
      symbol,
    });
  }
  return { mode: "list_auto", symbol };
}

/** Reanudar: checkpoint Actualizar o Lista AUTO. */
export function requestEstudioBannerSoftResume(): {
  mode: "update" | "list_auto";
} {
  if (hasEstudioUpdatePauseCheckpoint()) {
    requestEstudioUpdateResume();
    return { mode: "update" };
  }
  requestListAutoSoftResume();
  return { mode: "list_auto" };
}
