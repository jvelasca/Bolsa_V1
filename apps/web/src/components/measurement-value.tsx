/**
 * AUTO UI REFACTOR 1.0 — representación ÚNICA de un valor con su medición.
 *
 * Un valor sin muestra NUNCA se pinta como un número afirmado: si no hay valor se rotula la
 * medición (`NO MEDIDO`/`PARCIAL`) y, si el valor no es afirmable, se puede retener la cifra
 * (`incomplete="withhold"`). Esto hace imposible por accidente el bug del PnL de `v2.88.50`
 * (una cifra presentada como medida junto a un cierre `PARTIAL`).
 *
 * Todo el formateo se delega en `@bolsa/shared` (`formatMonitorFactValue`,
 * `formatMeasurementLabel`): la UI no re-implementa la regla de medición.
 */

import { cn } from "@/lib/utils";
import { formatMeasurementLabel, formatMonitorFactValue } from "@bolsa/shared";

/** Tono de honestidad: sólo una medición `COMPLETE` se pinta como afirmada. */
export function measurementTone(measurement: string): string {
  return measurement === "COMPLETE"
    ? "text-foreground/80"
    : "text-amber-600 dark:text-amber-400";
}

/**
 * Cómo tratar un valor con medición distinta de `COMPLETE`:
 * - `annotate` (defecto): `valor · PARCIAL` (el valor es un suelo MEDIDO, pero no un total).
 * - `withhold`: se muestra SÓLO la medición (el valor no es afirmable junto a su contexto).
 */
export type MeasurementIncompleteMode = "annotate" | "withhold";

export type MeasurementValueProps = {
  value: unknown;
  measurement: string;
  incomplete?: MeasurementIncompleteMode;
  /** Formateador del valor cuando SÍ se muestra (por defecto, el honesto de `@bolsa/shared`). */
  formatValue?: (value: unknown) => string;
  className?: string;
  testId?: string;
};

export function MeasurementValue({
  value,
  measurement,
  incomplete = "annotate",
  formatValue,
  className,
  testId,
}: MeasurementValueProps) {
  const measured = value !== null && value !== undefined;
  const complete = measurement === "COMPLETE";
  const showValue = measured && (complete || incomplete === "annotate");

  const text = !measured
    ? // Sin valor, el formateador de `@bolsa/shared` degrada `COMPLETE` a `NO MEDIDO`: un hueco
      // NUNCA se presenta como medido.
      formatMonitorFactValue(null, measurement)
    : showValue
      ? formatValue
        ? formatValue(value)
        : formatMonitorFactValue(value, measurement)
      : formatMeasurementLabel(measurement);
  const annotation =
    measured && !complete && incomplete === "annotate"
      ? ` · ${formatMeasurementLabel(measurement)}`
      : "";

  return (
    <span
      data-testid={testId}
      data-measurement={measurement}
      data-measured={measured ? "true" : "false"}
      className={cn("tabular-nums", measurementTone(measurement), className)}
    >
      {text}
      {annotation}
    </span>
  );
}

/** Sólo la medición, sin valor: para badges de cabecera/paso. */
export function MeasurementBadge({
  measurement,
  className,
  testId,
}: {
  measurement: string;
  className?: string;
  testId?: string;
}) {
  const complete = measurement === "COMPLETE";
  return (
    <span
      data-testid={testId}
      data-measurement={measurement}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        complete
          ? "bg-muted text-muted-foreground"
          : "bg-amber-500/15 text-amber-600 dark:text-amber-400",
        className,
      )}
    >
      {formatMeasurementLabel(measurement)}
    </span>
  );
}
