/**
 * Host de cadencias Estudio (capas media / lenta).
 * Vigilia (CORE-R) sigue en CoreRSchedulerHost.
 *
 * Emite `ESTUDIO_LANE_TICK_EVENT` cuando toca frescura o rediscubrimiento.
 * BacktestsPage (keep-alive si Supervisión ON) consume el tick.
 */

import { useEffect } from 'react';
import { ESTUDIO_LIST_ID } from '@bolsa/shared';
import { api } from '@/lib/api';
import {
  ESTUDIO_SUPERVISION_EVENT,
  emitEstudioLaneTick,
  estudioFreshnessDue,
  estudioRediscoverDue,
  loadEstudioSupervisionPrefs,
  markEstudioFreshnessTick,
  markEstudioRediscoverTick,
  sliceRediscoverBudget,
} from '@/features/trading/estudio-supervision';

const POLL_MS = 60_000;

export function EstudioSupervisionHost() {
  useEffect(() => {
    let cancelled = false;
    let running = false;

    const tick = async () => {
      if (cancelled || running) return;
      const prefs = loadEstudioSupervisionPrefs();
      if (!prefs.enabled) return;

      running = true;
      try {
        const now = Date.now();
        const listId = ESTUDIO_LIST_ID;

        // Rediscover tiene prioridad si ambos vencen: es el más raro y acotado.
        if (estudioRediscoverDue(prefs, now)) {
          let instrumentIds: string[] = [];
          try {
            const detail = await api.getList(listId);
            instrumentIds = detail.data.instrumentIds ?? [];
          } catch {
            instrumentIds = [];
          }
          const { ids, nextCursor } = sliceRediscoverBudget(
            instrumentIds,
            prefs.rediscoverCursor,
            prefs.rediscoverBudgetPerTick,
          );
          const at = new Date().toISOString();
          markEstudioRediscoverTick(prefs, { cursor: nextCursor, at });
          if (ids.length > 0) {
            emitEstudioLaneTick({
              listId,
              lane: 'rediscover',
              forceRescan: true,
              skipConfirm: true,
              instrumentIds: ids,
              at,
            });
          }
          return;
        }

        if (estudioFreshnessDue(prefs, now)) {
          const at = new Date().toISOString();
          markEstudioFreshnessTick(prefs, at);
          emitEstudioLaneTick({
            listId,
            lane: 'freshness',
            forceRescan: false,
            skipConfirm: true,
            instrumentIds: null,
            at,
          });
        }
      } finally {
        running = false;
      }
    };

    void tick();
    const id = window.setInterval(() => {
      void tick();
    }, POLL_MS);

    const onSupervision = () => {
      void tick();
    };
    window.addEventListener(ESTUDIO_SUPERVISION_EVENT, onSupervision);

    return () => {
      cancelled = true;
      window.clearInterval(id);
      window.removeEventListener(ESTUDIO_SUPERVISION_EVENT, onSupervision);
    };
  }, []);

  return null;
}
