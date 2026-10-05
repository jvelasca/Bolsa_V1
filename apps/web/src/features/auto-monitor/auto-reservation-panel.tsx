/**
 * AUTO Operational Monitor — ownership de reservas (§14).
 *
 * En `M1` la sesión dueña NO es durable: viaja `ownerSession = null` con
 * `ownerMeasurement = UNKNOWN` y la UI lo rotula `NO MEDIDO`. Con `M2` (sumidero de
 * auditoría) el panel pasa a datos reales sin cambiar el DTO.
 *
 * Todo valor con su medición se pinta con `MeasurementValue`: un hueco se rotula, nunca se
 * degrada a `?` ni a una cifra fingida.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MeasurementValue } from "@/components/measurement-value";
import type { AutoMonitorReservationV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";

function ReservationRow({
  reservation,
}: {
  reservation: AutoMonitorReservationV1;
}) {
  return (
    <li
      data-testid="auto-monitor-reservation"
      data-reservation-id={reservation.reservationId}
      data-owner-measurement={reservation.ownerMeasurement}
      className="rounded-lg border border-border/60 p-2.5 text-[11px]"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">
          {reservation.instrumentId ?? reservation.reservationId}
          {reservation.side ? (
            <span className="ml-1 uppercase text-muted-foreground">
              {reservation.side}
            </span>
          ) : null}
        </span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
            reservation.state === "LIVE"
              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
              : "bg-muted text-muted-foreground",
          )}
        >
          {reservation.state}
        </span>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-muted-foreground sm:grid-cols-3">
        <span data-testid="auto-monitor-reservation-owner">
          owner:{" "}
          <MeasurementValue
            value={reservation.ownerSession}
            measurement={reservation.ownerMeasurement}
          />
        </span>
        <span>
          qty:{" "}
          <MeasurementValue
            value={reservation.quantity}
            measurement="COMPLETE"
          />
        </span>
        <span>
          fill:{" "}
          <MeasurementValue
            value={reservation.fillProgress.filled}
            measurement={reservation.fillProgress.measurement}
          />{" "}
          /{" "}
          <MeasurementValue
            value={reservation.quantity}
            measurement="COMPLETE"
          />
        </span>
        <span>
          created:{" "}
          <MeasurementValue
            value={reservation.created}
            measurement={reservation.created ? "COMPLETE" : "UNKNOWN"}
          />
        </span>
        <span>
          expira:{" "}
          <MeasurementValue
            value={reservation.expires}
            measurement={reservation.expiresMeasurement}
          />
        </span>
        <span>
          liberación:{" "}
          <MeasurementValue
            value={reservation.releaseReason}
            measurement={reservation.releaseReasonMeasurement}
          />
        </span>
      </div>
      {reservation.reconciliations.length > 0 ? (
        <details className="mt-1">
          <summary className="cursor-pointer text-[10px] text-foreground/60">
            Reconciliaciones ({reservation.reconciliations.length})
          </summary>
          <ul className="mt-1 space-y-0.5 text-[10px] text-muted-foreground">
            {reservation.reconciliations.map((row, index) => (
              <li key={`${reservation.reservationId}-recon-${index}`}>
                <MeasurementValue
                  value={row.decision}
                  measurement={row.reconciliationMeasurement ?? "UNKNOWN"}
                />{" "}
                ·{" "}
                <MeasurementValue
                  value={row.reason}
                  measurement={row.reasonMeasurement ?? "UNKNOWN"}
                />{" "}
                · caller{" "}
                <MeasurementValue
                  value={row.caller}
                  measurement={row.callerMeasurement ?? "UNKNOWN"}
                />{" "}
                · aged{" "}
                <MeasurementValue
                  value={row.aged}
                  measurement={row.agedMeasurement ?? "UNKNOWN"}
                />{" "}
                · gracia{" "}
                <MeasurementValue
                  value={row.graceWindowSeconds}
                  measurement={row.graceWindowMeasurement ?? "UNKNOWN"}
                />
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </li>
  );
}

export function AutoReservationPanel({
  reservations,
}: {
  reservations: AutoMonitorReservationV1[];
}) {
  return (
    <Card
      className="rounded-xl border border-border bg-card"
      data-testid="auto-monitor-reservations"
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Ownership de reservas</CardTitle>
      </CardHeader>
      <CardContent>
        {reservations.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Sin reservas durables en la ventana.
          </p>
        ) : (
          <ul className="space-y-2">
            {reservations.map((reservation) => (
              <ReservationRow
                key={reservation.reservationId}
                reservation={reservation}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
