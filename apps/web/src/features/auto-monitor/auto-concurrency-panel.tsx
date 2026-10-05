/**
 * AUTO Operational Monitor — panel de concurrencia (§15).
 *
 * Los conteos que hoy NO tienen productor durable (claims duplicados, carreras de reserva,
 * reconciliaciones y ventanas de gracia) viajan `null` + `UNKNOWN` y la UI los rotula
 * `NO MEDIDO`. `forcedReleases` sí se mide desde las reservas durables. Con `M2` el resto
 * pasa a datos reales del spine.
 *
 * Todo valor con su medición se pinta con `MeasurementValue`: un `PARTIAL` (suelo medido, no
 * total) se distingue de un `COMPLETE` y un hueco se rotula, nunca se finge `0`.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MeasurementValue } from "@/components/measurement-value";
import {
  formatLastConflict,
  type AutoMonitorConcurrencyV1,
} from "@bolsa/shared";

function Metric({
  label,
  value,
  measurement,
  testId,
}: {
  label: string;
  value: number | null | undefined;
  measurement: string;
  testId: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border/40 py-1 last:border-b-0">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <MeasurementValue
        testId={testId}
        value={value}
        measurement={measurement}
        className="text-xs font-medium"
      />
    </div>
  );
}

export function AutoConcurrencyPanel({
  concurrency,
}: {
  concurrency: AutoMonitorConcurrencyV1;
}) {
  return (
    <Card
      className="rounded-xl border border-border bg-card"
      data-testid="auto-monitor-concurrency"
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Concurrencia</CardTitle>
      </CardHeader>
      <CardContent>
        <Metric
          label="Sesiones activas (spine)"
          value={concurrency.activeSessions}
          measurement={concurrency.activeSessionsMeasurement}
          testId="auto-monitor-active-sessions"
        />
        <Metric
          label="Heartbeats persistidos"
          value={concurrency.heartbeatsPersisted}
          measurement="COMPLETE"
          testId="auto-monitor-concurrency-ticks"
        />
        <Metric
          label="Claims intentados"
          value={concurrency.claimAttempts}
          measurement={concurrency.claimAttemptsMeasurement}
          testId="auto-monitor-claim-attempts"
        />
        <Metric
          label="Claims ganados"
          value={concurrency.successfulClaims}
          measurement={concurrency.successfulClaimsMeasurement}
          testId="auto-monitor-successful-claims"
        />
        <Metric
          label="Claims perdidos"
          value={concurrency.lostClaims}
          measurement={concurrency.lostClaimsMeasurement}
          testId="auto-monitor-lost-claims"
        />
        <Metric
          label="Conflictos de carrera"
          value={concurrency.raceConflicts}
          measurement={concurrency.raceConflictsMeasurement}
          testId="auto-monitor-race-conflicts"
        />
        <Metric
          label="Reconciliaciones"
          value={concurrency.reconciliations}
          measurement={concurrency.reconciliationsMeasurement}
          testId="auto-monitor-reconciliations"
        />
        <Metric
          label="Ventanas de gracia"
          value={concurrency.graceWindowKeeps}
          measurement={concurrency.graceWindowKeepsMeasurement}
          testId="auto-monitor-grace-keeps"
        />
        <Metric
          label="Liberaciones forzadas"
          value={concurrency.forcedReleases}
          measurement={concurrency.forcedReleasesMeasurement}
          testId="auto-monitor-forced-releases"
        />
        <div className="flex items-baseline justify-between gap-2 border-b border-border/40 py-1 last:border-b-0">
          <span className="text-[11px] text-muted-foreground">
            Último conflicto
          </span>
          <MeasurementValue
            testId="auto-monitor-last-conflict"
            value={concurrency.lastConflict}
            measurement={concurrency.lastConflictMeasurement}
            formatValue={(value) =>
              formatLastConflict(value, concurrency.lastConflictMeasurement)
            }
            className="text-xs font-medium"
          />
        </div>
      </CardContent>
    </Card>
  );
}
