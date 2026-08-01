/**
 * Host CORE-R cron shell — ticks mientras la app está abierta (PlatformShell).
 * v1.6–v1.7: toast si encola; acción **Abrir Monitor**.
 * No pisa TOP · no auto-paper D. Cola localStorage.
 */

import { useEffect } from 'react';
import {
  CORE_R_SCHEDULER_EVENT,
  loadCoreRSchedulerPrefs,
  type CoreRSchedulerTickDetail,
} from '@/features/backtests/core-r-scheduler';
import { runCoreRSchedulerTick } from '@/features/backtests/core-r-scheduler-tick';
import { formatCoreREnqueueToast } from '@/features/backtests/core-r-status';
import { useAlertsStore } from '@/stores/alerts-store';

const POLL_MS = 60_000;

export function CoreRSchedulerHost() {
  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      if (cancelled) return;
      const prefs = loadCoreRSchedulerPrefs();
      if (!prefs.enabled || prefs.scope !== 'shell') return;
      void runCoreRSchedulerTick({ scopeFilter: 'shell' });
    };
    tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    function onTick(event: Event) {
      const detail = (event as CustomEvent<CoreRSchedulerTickDetail>).detail;
      if (!detail) return;
      const msg = formatCoreREnqueueToast(detail.added);
      if (!msg) return;
      useAlertsStore.getState().pushToast(msg, {
        action: {
          type: 'open_help_backtesting_monitor',
          label: 'Abrir Monitor',
        },
      });
    }
    window.addEventListener(CORE_R_SCHEDULER_EVENT, onTick);
    return () => window.removeEventListener(CORE_R_SCHEDULER_EVENT, onTick);
  }, []);

  return null;
}
