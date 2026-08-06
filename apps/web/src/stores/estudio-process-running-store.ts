/**
 * Instrumento + capa en curso (animación columna Procesos).
 * Publicado desde Lista AUTO / CORE-R / Actualizar selección.
 */

import { create } from 'zustand';
import type { EstudioProcessLaneId } from '@/features/trading/estudio-process-status';
import {
  ESTUDIO_PROCESS_RUNNING_EVENT,
  type EstudioProcessRunningDetail,
} from '@/features/trading/estudio-process-status';

type State = {
  instrumentId: string | null;
  lane: EstudioProcessLaneId | null;
  setRunning: (instrumentId: string | null, lane: EstudioProcessLaneId | null) => void;
  clear: () => void;
};

function normalizeLane(
  lane: EstudioProcessRunningDetail['lane'],
): EstudioProcessLaneId | null {
  if (lane === 'vigilance' || lane === 'freshness' || lane === 'rediscover') return lane;
  return null;
}

export const useEstudioProcessRunningStore = create<State>((set) => ({
  instrumentId: null,
  lane: null,
  setRunning: (instrumentId, lane) => set({ instrumentId, lane }),
  clear: () => set({ instrumentId: null, lane: null }),
}));

/** Suscribe el store a eventos globales (montar una vez en shell o lista). */
export function wireEstudioProcessRunningEvents(): () => void {
  const onEvent = (ev: Event) => {
    const detail = (ev as CustomEvent<EstudioProcessRunningDetail>).detail;
    if (!detail?.instrumentId || !detail.lane) {
      useEstudioProcessRunningStore.getState().clear();
      return;
    }
    const lane = normalizeLane(detail.lane);
    if (!lane) {
      useEstudioProcessRunningStore.getState().clear();
      return;
    }
    useEstudioProcessRunningStore.getState().setRunning(detail.instrumentId, lane);
  };
  window.addEventListener(ESTUDIO_PROCESS_RUNNING_EVENT, onEvent);
  return () => window.removeEventListener(ESTUDIO_PROCESS_RUNNING_EVENT, onEvent);
}
