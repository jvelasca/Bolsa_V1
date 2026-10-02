/**
 * AUTO Operational Monitor (M1) — view model puro del DTO canónico.
 *
 * La UI NO re-ordena ni completa pasos: pinta el DTO tal cual. Este módulo sólo aporta
 * etiquetas, tonos y formateo honesto (un valor no medido viaja `null` + `measurement`;
 * la UI lo rotula "NO MEDIDO", nunca lo muestra como `0`).
 *
 * Camino: `DOMAIN EVENT → PERSISTED OPERATIONAL STATE → CANONICAL DTO → UI`.
 *
 * @see packages/py/application/src/bolsa_application/auto_operational_monitor.py
 */

export const AUTO_MONITOR_STEP_ORDER = [
  "SIGNAL",
  "TOP_N",
  "RISK",
  "RESERVATION",
  "ORDER",
  "FILL",
  "PROTECTION",
  "SETTLEMENT",
  "CYCLE_CLOSED",
] as const;

export type AutoMonitorStepId = (typeof AUTO_MONITOR_STEP_ORDER)[number];

export type AutoMonitorStepState = "reached" | "pending" | "absent" | "unknown";
export type AutoMonitorMeasurement = "COMPLETE" | "PARTIAL" | "UNKNOWN";

export const AUTO_MONITOR_STEP_LABELS: Record<string, string> = {
  SIGNAL: "Señal",
  TOP_N: "TOP-N",
  RISK: "Riesgo",
  RESERVATION: "Reserva",
  ORDER: "Orden",
  FILL: "Fill",
  PROTECTION: "Protección",
  SETTLEMENT: "Liquidación",
  CYCLE_CLOSED: "Ciclo cerrado",
};

const STEP_STATE_LABELS: Record<AutoMonitorStepState, string> = {
  reached: "alcanzado",
  pending: "pendiente",
  absent: "ausente",
  unknown: "no medido",
};

const STEP_STATE_TONES: Record<AutoMonitorStepState, string> = {
  reached: "text-emerald-600 dark:text-emerald-400",
  pending: "text-muted-foreground",
  absent: "text-destructive",
  unknown: "text-amber-600 dark:text-amber-400",
};

const DOT_TONES: Record<AutoMonitorStepState, string> = {
  reached: "bg-emerald-500",
  pending: "bg-muted-foreground/40",
  absent: "bg-destructive",
  unknown: "bg-amber-500",
};

export const NO_MEASUREMENT_LABEL = "NO MEDIDO";

export type AutoMonitorFactV1 = {
  key: string;
  value: unknown;
  measurement: string;
};

export type AutoMonitorStepV1 = {
  id: string;
  state: string;
  at?: string | null;
  measurement: string;
  facts: AutoMonitorFactV1[];
  note?: string | null;
};

export type AutoMonitorCycleV1 = {
  cycleId: string;
  instrumentId?: string | null;
  strategyVersion?: string | null;
  direction?: string;
  closed?: boolean;
  steps: AutoMonitorStepV1[];
  result?: { pnl?: unknown; closedAt?: string | null } | null;
  notes?: string[];
};

export type AutoMonitorReservationV1 = {
  reservationId: string;
  instrumentId?: string | null;
  side?: string | null;
  quantity?: unknown;
  remainingQty?: unknown;
  ownerSession?: string | null;
  ownerMeasurement: string;
  created?: string | null;
  expires?: string | null;
  expiresMeasurement: string;
  state: string;
  releaseReason?: string | null;
  releaseReasonMeasurement: string;
  fillProgress: { filled?: unknown; requested?: unknown; measurement: string };
  reconciliations: Array<{
    at?: string | null;
    caller?: string | null;
    decision?: string | null;
    reason?: string | null;
    aged?: unknown;
    graceWindowSeconds?: unknown;
  }>;
};

export type AutoMonitorConcurrencyV1 = {
  activeSessions?: number | null;
  activeSessionsMeasurement: string;
  heartbeatsPersisted: number;
  claimAttempts?: number | null;
  claimAttemptsMeasurement: string;
  successfulClaims?: number | null;
  successfulClaimsMeasurement: string;
  lostClaims?: number | null;
  lostClaimsMeasurement: string;
  raceConflicts?: number | null;
  raceConflictsMeasurement: string;
  reconciliations?: number | null;
  reconciliationsMeasurement: string;
  graceWindowKeeps?: number | null;
  graceWindowKeepsMeasurement: string;
  forcedReleases: number;
  forcedReleasesMeasurement: string;
  lastConflict?: unknown;
  lastConflictMeasurement: string;
};

export type AutoMonitorHeaderV1 = {
  engineId?: string | null;
  state: string;
  venue: string;
  granularity?: Record<string, unknown>;
  decisionClock: string;
  executionDeclared?: string | null;
  executionEnabled?: boolean | null;
  protectionModel?: string | null;
  heartbeatSeconds?: number | null;
  graceSeconds?: number | null;
  lastHeartbeatAt?: string | null;
  lastHeartbeatMeasurement: string;
  lastDecisionAt?: string | null;
  lastDecisionMeasurement: string;
  nextDecisionAt?: string | null;
  realPriceEnabled: boolean;
  heartbeatsPersisted: number;
  asOf: string;
};

export type AutoOperationalMonitorV1 = {
  key: string;
  readOnly: boolean;
  accountId?: string | null;
  asOf: string;
  header: AutoMonitorHeaderV1;
  cycles: AutoMonitorCycleV1[];
  reservations: AutoMonitorReservationV1[];
  concurrency: AutoMonitorConcurrencyV1;
  notes?: string[];
};

export type AutoMonitorStepViewV1 = AutoMonitorStepV1 & {
  label: string;
  stateLabel: string;
  tone: string;
  dotTone: string;
  measurementLabel: string;
};

export type AutoMonitorCycleViewV1 = Omit<AutoMonitorCycleV1, "steps"> & {
  steps: AutoMonitorStepViewV1[];
  directionLabel: string;
  statusLabel: string;
  unmeasuredStepIds: string[];
};

export type AutoOperationalMonitorViewV1 = Omit<
  AutoOperationalMonitorV1,
  "cycles"
> & {
  cycles: AutoMonitorCycleViewV1[];
};

export function stepLabel(stepId: string): string {
  return AUTO_MONITOR_STEP_LABELS[stepId] ?? stepId;
}

export function stepStateLabel(state: string): string {
  return STEP_STATE_LABELS[state as AutoMonitorStepState] ?? state;
}

export function stepStateTone(state: string): string {
  return (
    STEP_STATE_TONES[state as AutoMonitorStepState] ?? "text-muted-foreground"
  );
}

export function stepDotTone(state: string): string {
  return DOT_TONES[state as AutoMonitorStepState] ?? "bg-muted-foreground/40";
}

export function formatMeasurementLabel(measurement: string): string {
  switch (measurement) {
    case "COMPLETE":
      return "MEDIDO";
    case "PARTIAL":
      return "PARCIAL";
    default:
      return NO_MEASUREMENT_LABEL;
  }
}

/** Valor de una fila técnica con su estado de medición: un hueco se rotula, no se finge `0`. */
export function formatMonitorFactValue(
  value: unknown,
  measurement: string,
): string {
  if (value === null || value === undefined) {
    return formatMeasurementLabel(measurement);
  }
  if (typeof value === "boolean") return value ? "sí" : "no";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

/** "declarado vs habilitado": el header nunca debe simplificar a `AUTO = RUNNING`. */
export function executionModeLabel(header: AutoMonitorHeaderV1): string {
  const declared = header.executionDeclared ?? "unknown";
  const enabled = header.granularity?.execution;
  const enabledText = typeof enabled === "string" ? enabled : "unknown";
  const flag = header.executionEnabled ? "habilitado" : "NO habilitado";
  if (declared === enabledText) return `${enabledText} · ${flag}`;
  return `declarado ${declared} · en curso ${enabledText} · ${flag}`;
}

/**
 * "Precio real habilitado" es la CONFIGURACIÓN, no la fuente usada en una operación concreta.
 * La UI no debe dejar leer `ON` como "AUTO está operando con precio real".
 */
export function realPriceEnabledLabel(enabled: boolean): string {
  return enabled ? "SÍ (habilitado)" : "NO";
}

/** Instante del monitor: un hueco (sin valor) se rotula `NO MEDIDO`, nunca un `—` mudo. */
export function formatMonitorInstant(
  value: string | null | undefined,
  measurement: string,
): string {
  return value ?? formatMeasurementLabel(measurement);
}

/** Último conflicto de claim (carrera perdida) con su estado de medición, sin fingir un `0`. */
export function formatLastConflict(
  conflict: unknown,
  measurement: string,
): string {
  if (conflict === null || conflict === undefined) {
    return formatMeasurementLabel(measurement);
  }
  if (typeof conflict === "object") {
    const row = conflict as Record<string, unknown>;
    const reservationId = row.reservationId ?? "?";
    const at = row.at ?? "sin sello";
    return `${String(reservationId)} · ${String(at)}`;
  }
  return formatMonitorFactValue(conflict, measurement);
}

export function buildAutoOperationalMonitorView(
  dto: AutoOperationalMonitorV1,
): AutoOperationalMonitorViewV1 {
  return {
    ...dto,
    cycles: dto.cycles.map((cycle) => {
      const steps: AutoMonitorStepViewV1[] = cycle.steps.map((step) => ({
        ...step,
        label: stepLabel(step.id),
        stateLabel: stepStateLabel(step.state),
        tone: stepStateTone(step.state),
        dotTone: stepDotTone(step.state),
        measurementLabel: formatMeasurementLabel(step.measurement),
      }));
      return {
        ...cycle,
        steps,
        directionLabel: cycle.direction === "short" ? "Corto" : "Largo",
        statusLabel: cycle.closed ? "Cerrado" : "Abierto",
        unmeasuredStepIds: steps
          .filter((step) => step.measurement === "UNKNOWN")
          .map((step) => step.id),
      };
    }),
  };
}
