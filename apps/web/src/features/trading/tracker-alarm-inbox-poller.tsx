/**
 * Poller global: jobs de rastreador completados → inbox alarmas (on_bar_close u otros).
 * Montado en PlatformShell para no depender de Screeners.
 *
 * @see docs/engineering/research-radar-unification-2026-07-31.md §3b / B1.2
 */

import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { isAlarmSafeMode } from "@/features/screeners/tracker-alarms";
import { useAlertsStore } from "@/stores/alerts-store";
import { useTrackerAlarmInboxStore } from "@/stores/tracker-alarm-inbox-store";

const POLL_MS = 12_000;

export function TrackerAlarmInboxPoller() {
  const { effectiveAccountId } = useActiveAccount();
  const pushFromScan = useTrackerAlarmInboxStore((s) => s.pushFromScan);
  const pushToast = useAlertsStore((s) => s.pushToast);
  const lastNotifiedScanRef = useRef<string | null>(null);

  const jobsQuery = useQuery({
    queryKey: ["scan-jobs", "alarm-inbox"],
    queryFn: api.getScanJobs,
    refetchInterval: POLL_MS,
    staleTime: POLL_MS / 2,
  });

  useEffect(() => {
    if (!effectiveAccountId || !jobsQuery.data?.data) return;
    const jobs = jobsQuery.data.data;
    for (const job of jobs) {
      if (job.status !== "completed") continue;
      if (!job.trackerDefinitionId) continue;
      const result = job.result;
      if (!result?.scanId || !result.alarmRoute) continue;
      if (!isAlarmSafeMode(result.alarmRoute.mode)) continue;
      if (!(result.alarmRoute.actions?.length ?? 0)) continue;

      const n = pushFromScan(result, effectiveAccountId, {
        listId: result.listId ?? null,
      });
      if (n > 0 && lastNotifiedScanRef.current !== result.scanId) {
        lastNotifiedScanRef.current = result.scanId;
        pushToast(
          `Radar · ${n} alarma${n === 1 ? "" : "s"} (scan programado) → inbox Trading`,
        );
      }
    }
  }, [jobsQuery.data, effectiveAccountId, pushFromScan, pushToast]);

  return null;
}
