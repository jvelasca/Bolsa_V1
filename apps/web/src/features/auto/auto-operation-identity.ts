/**
 * AUTO UI REFACTOR (F2) — identidad legible de una operación (helper puro).
 *
 * Convierte un ciclo del monitor en una etiqueta humana y estable, sin re-derivar nada:
 * `AAPL · 03 Oct · Largo · Precio aplicado`. Resuelve el problema de que dos ciclos del mismo símbolo
 * (p. ej. dos operaciones de AAPL en días distintos) eran indistinguibles por `instrumentId`.
 *
 * Invariantes:
 * - `entryDay` se **copia** del sello de la etapa `SIGNAL` (`steps[].at`); no se recalcula.
 * - `directionLabel`/`statusLabel` vienen del view model de `@bolsa/shared`; se usan literalmente.
 * - Un dato ausente se declara `NO MEDIDO`, nunca se inventa ni se cae a `cycleId` como texto humano.
 * - `cycleId` NO se usa como identidad visible (es identificador técnico → `data-cycle-id`).
 *
 * @see docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md §F2
 * @see packages/shared/src/cognitive/auto-operational-monitor.ts
 */

import {
  NO_MEASUREMENT_LABEL,
  type AutoMonitorCycleViewV1,
} from "@bolsa/shared";

const MONTHS_ES = [
  "ene",
  "feb",
  "mar",
  "abr",
  "may",
  "jun",
  "jul",
  "ago",
  "sep",
  "oct",
  "nov",
  "dic",
] as const;

export type AutoOperationIdentityV1 = {
  /** Identidad humana: `SÍMBOLO · DD MMM · Dirección · Estado`. */
  label: string;
  /** Día de entrada copiado de la señal (`DD MMM`) o `NO MEDIDO`. */
  entryDay: string;
};

/**
 * Formatea el sello de entrada a `DD MMM` de forma determinista (sin `Date`/zona horaria):
 * se lee la parte de fecha del ISO. Un valor ausente o ilegible se declara `NO MEDIDO`.
 */
export function formatEntryDay(at: string | null | undefined): string {
  if (!at) return NO_MEASUREMENT_LABEL;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(at);
  if (!match) return NO_MEASUREMENT_LABEL;
  const month = Number(match[2]);
  if (month < 1 || month > 12) return NO_MEASUREMENT_LABEL;
  return `${match[3]} ${MONTHS_ES[month - 1]}`;
}

export function buildOperationIdentity(
  cycle: Pick<AutoMonitorCycleViewV1, "instrumentId"> &
    Partial<
      Pick<AutoMonitorCycleViewV1, "directionLabel" | "statusLabel" | "steps">
    >,
): AutoOperationIdentityV1 {
  const steps = cycle.steps ?? [];
  const entryDay = formatEntryDay(
    steps.find((step) => step.id === "SIGNAL")?.at,
  );
  const label = [
    cycle.instrumentId ?? NO_MEASUREMENT_LABEL,
    entryDay,
    cycle.directionLabel ?? NO_MEASUREMENT_LABEL,
    cycle.statusLabel ?? NO_MEASUREMENT_LABEL,
  ].join(" · ");
  return { label, entryDay };
}
