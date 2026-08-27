/**
 * Alertas operativas — legacy decision alerts + unified inbox.
 */

import type { MesaDecisionAlertV1, UnifiedAlertV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";

export function MesaDecisionAlertsPanel({
  alerts,
  unifiedAlerts,
}: {
  alerts: MesaDecisionAlertV1[];
  unifiedAlerts?: UnifiedAlertV1[];
}) {
  const display = unifiedAlerts?.length ? unifiedAlerts : null;
  if (alerts.length === 0 && !display?.length) return null;

  if (display?.length) {
    return (
      <div
        className="space-y-1 rounded-md border border-border/60 bg-muted/20 px-3 py-2"
        data-testid="mesa-unified-alerts"
        role="status"
        aria-live="polite"
      >
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Alertas operativas
        </p>
        <ul className="space-y-2">
          {display.slice(0, 8).map((alert, i) => (
            <li
              key={`${alert.kind}-${alert.symbol}-${i}`}
              className={cn(
                "text-xs",
                alert.severity === "critical" &&
                  "font-medium text-rose-700 dark:text-rose-300",
                alert.severity === "warning" &&
                  "text-amber-800 dark:text-amber-200",
                alert.severity === "info" && "text-muted-foreground",
              )}
            >
              <span className="text-[10px] uppercase text-muted-foreground">
                {alert.kind}
              </span>
              {" · "}
              <span className="font-medium">{alert.symbol}</span> —{" "}
              {alert.title}: {alert.message}
              {alert.checklist?.length ? (
                <ul className="mt-0.5 flex flex-wrap gap-2 pl-0 text-[10px]">
                  {alert.checklist.map((c) => (
                    <li key={c.label}>
                      {c.label}{" "}
                      {c.status === "ok"
                        ? "OK"
                        : c.status === "warn"
                          ? "WARN"
                          : "FAIL"}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div
      className="space-y-1 rounded-md border border-border/60 bg-muted/20 px-3 py-2"
      data-testid="mesa-decision-alerts"
      role="status"
      aria-live="polite"
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Alertas operativas
      </p>
      <ul className="space-y-1">
        {alerts.slice(0, 8).map((alert, i) => (
          <li
            key={`${alert.kind}-${alert.symbol}-${i}`}
            className={cn(
              "text-xs",
              alert.severity === "critical" &&
                "font-medium text-rose-700 dark:text-rose-300",
              alert.severity === "warning" &&
                "text-amber-800 dark:text-amber-200",
              alert.severity === "info" && "text-muted-foreground",
            )}
          >
            <span className="font-medium">{alert.symbol}</span> —{" "}
            {alert.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
