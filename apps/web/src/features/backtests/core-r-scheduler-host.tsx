/**
 * Host CORE-R cron shell — ticks mientras la app está abierta (PlatformShell).
 * v1.6–v1.7: toast si encola; acción **Abrir Monitor**.
 * v1.9 Q3.4: hydrate cola/informe/scheduler desde BD (multi-dispositivo).
 * v1.12: poll remoto → toast si cron servidor / otro device encoló.
 * Arranque: primer tick diferido (idle / ~4s) para no competir con listas.
 * No pisa TOP · no auto-paper D.
 */

import { useEffect } from "react";
import {
  CORE_R_SCHEDULER_EVENT,
  loadCoreRSchedulerPrefs,
  type CoreRSchedulerTickDetail,
} from "@/features/backtests/core-r-scheduler";
import { runCoreRSchedulerTick } from "@/features/backtests/core-r-scheduler-tick";
import { formatCoreREnqueueToast } from "@/features/backtests/core-r-status";
import {
  ensureCoreRHydrated,
  pollCoreRRemoteEnqueueToast,
  wireCoreRPushSubscriptions,
} from "@/features/backtests/core-r-sync";
import { useAlertsStore } from "@/stores/alerts-store";
import { useActiveAccountStore } from "@/stores/active-account-store";

const POLL_MS = 60_000;
/** Primer tick shell: tras paint / idle; la cadencia real es ≥5 min. */
const BOOT_DEFER_MS = 4_000;

export function CoreRSchedulerHost() {
  const activeAccountId = useActiveAccountStore((s) => s.activeAccountId);

  useEffect(() => {
    wireCoreRPushSubscriptions();
  }, []);

  useEffect(() => {
    if (!activeAccountId) return;
    // Hydrate también diferido: no bloquea el paint de Trading/listas.
    const t = window.setTimeout(() => {
      void ensureCoreRHydrated(activeAccountId);
    }, 1_500);
    return () => window.clearTimeout(t);
  }, [activeAccountId]);

  useEffect(() => {
    let cancelled = false;
    let intervalId: number | undefined;
    let bootTimer: number | undefined;
    let idleHandle: number | undefined;

    const tick = () => {
      if (cancelled) return;
      const prefs = loadCoreRSchedulerPrefs();
      if (!prefs.enabled || prefs.scope !== "shell") return;
      void runCoreRSchedulerTick({ scopeFilter: "shell" });
    };

    const start = () => {
      if (cancelled) return;
      tick();
      intervalId = window.setInterval(tick, POLL_MS);
    };

    if (typeof window.requestIdleCallback === "function") {
      idleHandle = window.requestIdleCallback(start, {
        timeout: BOOT_DEFER_MS,
      });
    } else {
      bootTimer = window.setTimeout(start, BOOT_DEFER_MS);
    }

    return () => {
      cancelled = true;
      if (
        idleHandle != null &&
        typeof window.cancelIdleCallback === "function"
      ) {
        window.cancelIdleCallback(idleHandle);
      }
      if (bootTimer != null) window.clearTimeout(bootTimer);
      if (intervalId != null) window.clearInterval(intervalId);
    };
  }, []);

  /** Multi-dispositivo: hidrata + toast si hay señal remota nueva. */
  useEffect(() => {
    if (!activeAccountId) return;
    let cancelled = false;
    const poll = () => {
      if (cancelled) return;
      void pollCoreRRemoteEnqueueToast(activeAccountId);
    };
    // Tras hydrate inicial, un poll corto captura encolados del cron servidor.
    const boot = window.setTimeout(poll, 2_500);
    const id = window.setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(boot);
      window.clearInterval(id);
    };
  }, [activeAccountId]);

  useEffect(() => {
    function onTick(event: Event) {
      const detail = (event as CustomEvent<CoreRSchedulerTickDetail>).detail;
      if (!detail) return;
      const msg = formatCoreREnqueueToast(detail.added);
      if (!msg) return;
      useAlertsStore.getState().pushToast(msg, {
        action: {
          type: "open_help_backtesting_monitor",
          label: "Abrir Monitor",
        },
      });
    }
    window.addEventListener(CORE_R_SCHEDULER_EVENT, onTick);
    return () => window.removeEventListener(CORE_R_SCHEDULER_EVENT, onTick);
  }, []);

  return null;
}
