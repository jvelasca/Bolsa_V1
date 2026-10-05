/**
 * AUTO Operational Monitor — timeline de ciclo (§13): `SIGNAL → … → CYCLE CLOSED`.
 *
 * Reutiliza el patrón visual del journal (`<ol>` + `border-l-2` + dots de estado). La UI
 * pinta los pasos en el orden que trae el DTO y rotula los huecos como `NO MEDIDO`.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  AutoMonitorCycleViewV1,
  AutoMonitorStepViewV1,
} from "@bolsa/shared";
import { formatMeasurementLabel, formatMonitorFactValue } from "@bolsa/shared";
import { cn } from "@/lib/utils";

function StepRow({ step }: { step: AutoMonitorStepViewV1 }) {
  return (
    <li
      data-testid="auto-monitor-step"
      data-step-id={step.id}
      data-step-state={step.state}
      data-step-measurement={step.measurement}
      className="relative border-l-2 border-border/60 pl-4 pb-3 last:pb-0"
    >
      <span
        className={cn(
          "absolute -left-[5px] top-1 h-2 w-2 rounded-full",
          step.dotTone,
        )}
        aria-hidden
      />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold">{step.label}</span>
        <span
          className={cn(
            "text-[10px] font-semibold uppercase tracking-wide",
            step.tone,
          )}
          data-testid="auto-monitor-step-state"
        >
          {step.stateLabel}
        </span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
            step.measurement === "UNKNOWN"
              ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
              : "bg-muted text-muted-foreground",
          )}
        >
          {step.measurementLabel}
        </span>
        {step.at ? (
          <span className="text-[10px] tabular-nums text-muted-foreground">
            {step.at}
          </span>
        ) : null}
      </div>
      {step.note ? (
        <p
          className="mt-1 text-[10px] text-muted-foreground"
          data-testid="auto-monitor-step-note"
        >
          {step.note}
        </p>
      ) : null}
      {step.facts.length > 0 ? (
        <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
          {step.facts.map((fact) => (
            <div key={fact.key} className="flex items-baseline gap-1">
              <dt className="text-muted-foreground">{fact.key}:</dt>
              <dd className="tabular-nums text-foreground/80">
                {formatMonitorFactValue(fact.value, fact.measurement)}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </li>
  );
}

function CycleCard({ cycle }: { cycle: AutoMonitorCycleViewV1 }) {
  const closedAsserted =
    cycle.closed !== null &&
    cycle.closed !== undefined &&
    (cycle.closedMeasurement ?? "COMPLETE") === "COMPLETE";
  // La cifra de PnL hereda la medición del cierre: con un cierre no afirmable (`PARTIAL`/
  // `UNKNOWN`) NO se presenta el número como medido — se rotula la medición. El valor se
  // publica sólo con evidencia `COMPLETE` (regla de la casa: un hueco nunca es una cifra).
  const pnl = cycle.result?.pnl;
  const pnlMeasurement = cycle.closedMeasurement ?? "UNKNOWN";
  return (
    <Card
      className="rounded-xl border border-border bg-card"
      data-testid="auto-monitor-cycle"
      data-cycle-id={cycle.cycleId}
      data-cycle-closed={
        closedAsserted ? (cycle.closed ? "true" : "false") : "unknown"
      }
    >
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-sm">
            {cycle.instrumentId ?? cycle.cycleId}
            <span className="ml-2 text-[10px] font-normal text-muted-foreground">
              {cycle.strategyVersion ?? "sin versión"}
            </span>
          </CardTitle>
          <div className="flex items-center gap-2 text-[10px]">
            <span className="rounded bg-muted px-1.5 py-0.5 uppercase tracking-wide text-muted-foreground">
              {cycle.directionLabel}
            </span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 font-semibold uppercase tracking-wide",
                !closedAsserted
                  ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                  : cycle.closed
                    ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                    : "bg-muted text-muted-foreground",
              )}
            >
              {cycle.statusLabel}
            </span>
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground">
          <code>{cycle.cycleId}</code>
          {pnl !== null && pnl !== undefined ? (
            <span
              className="ml-2 tabular-nums"
              data-testid="auto-monitor-cycle-pnl"
              data-pnl-measurement={pnlMeasurement}
            >
              PnL:{" "}
              {pnlMeasurement === "COMPLETE"
                ? formatMonitorFactValue(pnl, "COMPLETE")
                : formatMeasurementLabel(pnlMeasurement)}
            </span>
          ) : null}
        </p>
      </CardHeader>
      <CardContent>
        <ol className="space-y-0" data-testid="auto-monitor-timeline">
          {cycle.steps.map((step) => (
            <StepRow key={`${cycle.cycleId}-${step.id}`} step={step} />
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

export function AutoCycleTimeline({
  cycles,
}: {
  cycles: AutoMonitorCycleViewV1[];
}) {
  if (cycles.length === 0) {
    return (
      <Card className="rounded-xl border border-border bg-card">
        <CardContent className="py-6">
          <p
            className="text-xs text-muted-foreground"
            data-testid="auto-monitor-empty"
          >
            Sin ciclos durables en la ventana.
          </p>
        </CardContent>
      </Card>
    );
  }
  return (
    <div className="space-y-3" data-testid="auto-monitor-cycles">
      {cycles.map((cycle) => (
        <CycleCard key={cycle.cycleId} cycle={cycle} />
      ))}
    </div>
  );
}
