/**
 * AUTO Operational Monitor — panel de concurrencia (§15).
 *
 * Los conteos que hoy NO tienen productor durable (claims duplicados, carreras de reserva,
 * reconciliaciones y ventanas de gracia) viajan `null` + `UNKNOWN` y la UI los rotula
 * `NO MEDIDO`. `forcedReleases` sí se mide desde las reservas durables. Con `M2` el resto
 * pasa a datos reales del spine.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  formatLastConflict,
  formatMeasurementLabel,
  type AutoMonitorConcurrencyV1,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";

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
  const measured = value !== null && value !== undefined;
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border/40 py-1 last:border-b-0">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span
        data-testid={testId}
        data-measurement={measurement}
        className={cn(
          "text-xs font-medium tabular-nums",
          measured
            ? "text-foreground/80"
            : "text-amber-600 dark:text-amber-400",
        )}
      >
        {measured ? value : formatMeasurementLabel(measurement)}
      </span>
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
          label="Ticks duros"
          value={concurrency.ticks}
          measurement="COMPLETE"
          testId="auto-monitor-concurrency-ticks"
        />
        <Metric
          label="Claims duplicados"
          value={concurrency.duplicateClaims}
          measurement={concurrency.duplicateClaimsMeasurement}
          testId="auto-monitor-duplicate-claims"
        />
        <Metric
          label="Carreras de reserva"
          value={concurrency.reservationRaces}
          measurement={concurrency.reservationRacesMeasurement}
          testId="auto-monitor-reservation-races"
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
          <span
            data-testid="auto-monitor-last-conflict"
            data-measurement={concurrency.lastConflictMeasurement}
            className={cn(
              "text-xs font-medium",
              concurrency.lastConflict == null
                ? "text-amber-600 dark:text-amber-400"
                : "text-foreground/80",
            )}
          >
            {formatLastConflict(
              concurrency.lastConflict,
              concurrency.lastConflictMeasurement,
            )}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
