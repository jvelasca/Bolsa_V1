/**
 * Supervisión Estudio (ADR-024) — prefs + eventos + unsubscribe.
 *
 * Supervisión ON → arma CORE-R Auto-sync + solicita Lista AUTO sobre Estudio.
 * Quitar de Estudio → dismiss colas + excluir de campaña en curso.
 */

import { ESTUDIO_LIST_ID } from '@bolsa/shared';
import {
  loadCoreRSchedulerPrefs,
  saveCoreRSchedulerPrefs,
  clampCoreRSchedulerInterval,
} from '@/features/backtests/core-r-scheduler';
import { useCoreRReviewQueueStore } from '@/stores/core-r-review-queue-store';
import { useSupervisedF3QueueStore } from '@/stores/supervised-f3-queue-store';

export const ESTUDIO_SUPERVISION_KEY = 'bolsa-estudio-supervision-v1';
export const ESTUDIO_SUPERVISION_EVENT = 'bolsa-estudio-supervision-changed';
export const ESTUDIO_UNSUBSCRIBE_EVENT = 'bolsa-estudio-unsubscribe';

export type EstudioSupervisionPrefs = {
  enabled: boolean;
  /** Minutos entre ticks CORE-R (alineado con scheduler). */
  intervalMinutes: number;
};

const DEFAULT: EstudioSupervisionPrefs = {
  enabled: false,
  intervalMinutes: 60,
};

export type EstudioSupervisionEventDetail = {
  enabled: boolean;
  listId: string;
  intervalMinutes: number;
};

export type EstudioUnsubscribeEventDetail = {
  instrumentIds: string[];
};

export function loadEstudioSupervisionPrefs(): EstudioSupervisionPrefs {
  try {
    const raw = localStorage.getItem(ESTUDIO_SUPERVISION_KEY);
    if (!raw) return { ...DEFAULT };
    const parsed = JSON.parse(raw) as Partial<EstudioSupervisionPrefs>;
    return {
      enabled: Boolean(parsed.enabled),
      intervalMinutes: clampCoreRSchedulerInterval(Number(parsed.intervalMinutes) || 60),
    };
  } catch {
    return { ...DEFAULT };
  }
}

export function saveEstudioSupervisionPrefs(prefs: EstudioSupervisionPrefs): void {
  try {
    localStorage.setItem(ESTUDIO_SUPERVISION_KEY, JSON.stringify(prefs));
  } catch {
    // quota
  }
}

export function emitEstudioSupervisionChanged(detail: EstudioSupervisionEventDetail): void {
  try {
    window.dispatchEvent(new CustomEvent(ESTUDIO_SUPERVISION_EVENT, { detail }));
  } catch {
    // SSR / tests
  }
}

export function emitEstudioUnsubscribe(instrumentIds: string[]): void {
  if (instrumentIds.length === 0) return;
  try {
    window.dispatchEvent(
      new CustomEvent(ESTUDIO_UNSUBSCRIBE_EVENT, {
        detail: { instrumentIds } satisfies EstudioUnsubscribeEventDetail,
      }),
    );
  } catch {
    // SSR / tests
  }
}

/**
 * Activa/desactiva supervisión: prefs + CORE-R Auto-sync + evento para Lista AUTO.
 */
export function setEstudioSupervisionEnabled(
  enabled: boolean,
  opts?: { listId?: string | null; intervalMinutes?: number },
): EstudioSupervisionPrefs {
  const prev = loadEstudioSupervisionPrefs();
  const intervalMinutes = clampCoreRSchedulerInterval(
    opts?.intervalMinutes ?? prev.intervalMinutes,
  );
  const next: EstudioSupervisionPrefs = { enabled, intervalMinutes };
  saveEstudioSupervisionPrefs(next);

  const listId = opts?.listId || ESTUDIO_LIST_ID;
  const sched = loadCoreRSchedulerPrefs();
  saveCoreRSchedulerPrefs({
    ...sched,
    enabled,
    intervalMinutes,
    listId: enabled ? listId : sched.listId,
    scope: 'shell',
  });

  emitEstudioSupervisionChanged({ enabled, listId, intervalMinutes });
  return next;
}

/**
 * Al quitar de Estudio: dismiss CORE-R + F3; notifica Lista AUTO para excluir.
 * No cierra mandato ni posiciones.
 */
export function unsubscribeInstrumentFromSupervision(
  instrumentIds: ReadonlyArray<string>,
): void {
  const ids = [...new Set(instrumentIds.filter(Boolean))];
  if (ids.length === 0) return;

  const coreR = useCoreRReviewQueueStore.getState();
  for (const id of ids) coreR.dismissOpenForInstrument(id);

  const f3 = useSupervisedF3QueueStore.getState();
  for (const id of ids) f3.removeForInstrument(id);

  emitEstudioUnsubscribe(ids);
}
