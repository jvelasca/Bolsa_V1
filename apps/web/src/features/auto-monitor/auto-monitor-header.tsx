/**
 * AUTO Operational Monitor — cabecera (§12): reloj de decisión, ejecución DECLARADA vs
 * HABILITADA, protección, heartbeat y precio real. Nunca simplifica a `AUTO = RUNNING`.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  executionModeLabel,
  formatMeasurementLabel,
  formatMonitorInstant,
  NO_MEASUREMENT_LABEL,
  realPriceEnabledLabel,
  type AutoMonitorHeaderV1,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";

function Field({
  label,
  value,
  tone,
  ...rest
}: {
  label: string;
  value: string;
  tone?: string;
  "data-testid"?: string;
}) {
  return (
    <div className="space-y-0.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={cn("text-xs font-medium tabular-nums", tone)} {...rest}>
        {value}
      </p>
    </div>
  );
}

export function AutoMonitorHeader({ header }: { header: AutoMonitorHeaderV1 }) {
  const execution = executionModeLabel(header);
  return (
    <Card
      className="rounded-xl border border-border bg-card"
      data-testid="auto-monitor-header"
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Motor AUTO</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Field
          label="Estado"
          value={header.state}
          data-testid="auto-monitor-state"
        />
        <Field label="Venue" value={header.venue} />
        <Field
          label="Decisión (reloj)"
          value={header.decisionClock}
          data-testid="auto-monitor-decision-clock"
        />
        <Field
          label="Granularidad"
          value={
            typeof header.granularity?.decision === "string"
              ? header.granularity.decision
              : NO_MEASUREMENT_LABEL
          }
        />
        <Field
          label="Ejecución"
          value={execution}
          tone={
            header.executionEnabled
              ? undefined
              : "text-amber-600 dark:text-amber-400"
          }
          data-testid="auto-monitor-execution"
        />
        <Field
          label="Protección"
          value={header.protectionModel ?? NO_MEASUREMENT_LABEL}
        />
        <Field
          label="Heartbeat"
          value={
            header.heartbeatSeconds === null ||
            header.heartbeatSeconds === undefined
              ? NO_MEASUREMENT_LABEL
              : `${header.heartbeatSeconds}s`
          }
        />
        <Field
          label="Ventana gracia"
          value={
            header.graceSeconds === null || header.graceSeconds === undefined
              ? NO_MEASUREMENT_LABEL
              : `${header.graceSeconds}s`
          }
        />
        <Field
          label="Último heartbeat"
          value={formatMonitorInstant(
            header.lastHeartbeatAt,
            header.lastHeartbeatMeasurement,
          )}
          data-testid="auto-monitor-last-heartbeat"
        />
        <Field
          label="Última decisión"
          value={formatMonitorInstant(
            header.lastDecisionAt,
            header.lastDecisionMeasurement,
          )}
          data-testid="auto-monitor-last-decision"
        />
        <Field
          label="Próxima decisión"
          value={formatMonitorInstant(
            header.nextDecisionAt,
            header.lastDecisionMeasurement,
          )}
          data-testid="auto-monitor-next-decision"
        />
        <Field
          label="Precio real habilitado"
          value={realPriceEnabledLabel(header.realPriceEnabled)}
          tone={
            header.realPriceEnabled
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-muted-foreground"
          }
          data-testid="auto-monitor-real-price"
        />
        <Field
          label="Heartbeats persistidos"
          value={`${header.heartbeatsPersisted} · ${formatMeasurementLabel("COMPLETE")}`}
          data-testid="auto-monitor-ticks"
        />
      </CardContent>
    </Card>
  );
}
