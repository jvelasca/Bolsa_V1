/**
 * V1.18 — alertas de decisión operativa en Mesa.
 */

import type { MesaDecisionAlertV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";

export function MesaDecisionAlertsPanel({
  alerts,
}: {
  alerts: MesaDecisionAlertV1[];
}) {
  if (alerts.length === 0) return null;

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
