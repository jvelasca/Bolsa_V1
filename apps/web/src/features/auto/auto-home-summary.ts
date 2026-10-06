/**
 * AUTO UI REFACTOR 3.0 (S1) — resumen de la HOME / cockpit (helper puro).
 *
 * La HOME responde en 5 s las preguntas del usuario básico. Este módulo es **puro**, read-only y
 * determinista: no lee de red ni de storage, y **no re-deriva** ninguna cifra. Copia los hechos
 * ya producidos (estado del motor, sellos de decisión, cierres de ciclo, integridad operativa) y
 * los traduce a lenguaje de usuario (nivel 1 del modelo de tres niveles).
 *
 * Invariantes:
 * - Un hueco (`null`/ausente/`UNKNOWN`) se declara «Sin dato todavía»; NUNCA se rellena con `0`.
 * - El contador sólo incluye ciclos en «Precio aplicado» (`FILL` alcanzado y no cerrados, con
 *   medición `COMPLETE`). Una reserva, una orden o un cierre no medido no cuentan.
 * - El estado del motor se traduce solo si el token pertenece al conjunto cerrado que el monitor
 *   copia (`RUNNING`, `PAUSED`, `BLOCKED`, `DEGRADED`, `REQUIRES_ATTENTION`). Cualquier otro
 *   token es «Sin dato todavía». Conocer el estado no significa que funcione correctamente.
 *   El valor crudo queda para el detalle técnico.
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §2
 */

import { CYCLE_STATUS_PRICE_APPLIED, cycleStatusLabel } from "@bolsa/shared";

export const AUTO_HOME_NO_DATA_LABEL = "Sin dato todavía";

/** Estados de integridad operativa del backend (`Literal["OK","DEGRADED","BLOCKED"]`). */
export type AutoHomeRiskTone = "ok" | "attention" | "blocked" | "unknown";

export type AutoHomeCycleFacts = {
  cycleId: string;
  closed?: boolean | null;
  closedMeasurement?: string | null;
  steps?: readonly { id: string; state: string }[] | null;
};

export type AutoHomeHeaderFacts = {
  state?: string | null;
  lastDecisionAt?: string | null;
  lastHeartbeatAt?: string | null;
  nextDecisionAt?: string | null;
};

export type AutoHomeSummaryInput = {
  header?: AutoHomeHeaderFacts | null;
  cycles?: readonly AutoHomeCycleFacts[] | null;
  /** `operationalState` de la integridad financiera (`OK` | `DEGRADED` | `BLOCKED`). */
  riskOperationalState?: string | null;
  /** `true`/`false`; `null`/`undefined` = no medido. */
  isLoading?: boolean;
  isError?: boolean;
};

export type AutoHomeSummaryV1 = {
  /** `true` = el monitor respondió (aunque sea vacío). */
  loaded: boolean;
  /** Estado de sustitución a pintar cuando la query no está disponible aún. */
  isLoading: boolean;
  isError: boolean;
  /**
   * Traducción del estado del motor, o `Sin dato todavía`.
   * Misma frase que `statusLabel`.
   */
  autoLabel: string;
  /**
   * Traducción del estado del motor, o `Sin dato todavía`.
   * Misma frase que `autoLabel`.
   */
  statusLabel: string;
  /** Sello `HH:mm` de la última decisión/heartbeat, o `Sin dato todavía`. */
  lastActivityLabel: string;
  /** `Próximo análisis: HH:mm` | `Esperando nueva señal` | `Sin dato todavía`. */
  nextStepLabel: string;
  openOperationsCount: number;
  /** `3 abiertas` | `1 abierta` | `Sin operaciones abiertas`. */
  openOperationsLabel: string;
  hasOpenOperations: boolean;
  riskTone: AutoHomeRiskTone;
  /** `Normal` | `Atención` | `Bloqueado` | `Sin dato todavía`. */
  riskLabel: string;
};

/** `true` sólo si el ciclo está en «Precio aplicado» (fill alcanzado, no cerrado, medición completa). */
export function isOperationOpen(cycle: AutoHomeCycleFacts): boolean {
  return cycleStatusLabel(cycle) === CYCLE_STATUS_PRICE_APPLIED;
}

/**
 * Conjunto cerrado que el monitor copia de `AutoEngineState`.
 * Un token fuera de esta tabla no se presenta como funcionamiento correcto.
 */
const ENGINE_STATE_LABELS: Readonly<Record<string, string>> = {
  RUNNING: "Funcionando",
  PAUSED: "Detenido",
  DEGRADED: "Funcionamiento limitado",
  BLOCKED: "Bloqueado",
  REQUIRES_ATTENTION: "Atención requerida",
};

/** Traduce `header.state` solo si el token está en el conjunto cerrado del motor. */
export function engineStateLabel(state: string | null | undefined): string {
  if (state == null) return AUTO_HOME_NO_DATA_LABEL;
  return (
    ENGINE_STATE_LABELS[state.trim().toUpperCase()] ?? AUTO_HOME_NO_DATA_LABEL
  );
}

/**
 * Hora del sello ISO (`HH:mm`) de forma determinista (sin `Date`/zona horaria): se lee la parte
 * horaria del ISO. Un valor ausente o ilegible se declara «Sin dato todavía».
 */
export function formatActivityTime(value: string | null | undefined): string {
  if (!value) return AUTO_HOME_NO_DATA_LABEL;
  const match = /T(\d{2}):(\d{2})/.exec(value);
  if (match) return `${match[1]}:${match[2]}`;
  return value;
}

function riskFromOperationalState(state: string | null | undefined): {
  tone: AutoHomeRiskTone;
  label: string;
} {
  switch (state) {
    case "OK":
      return { tone: "ok", label: "Normal" };
    case "DEGRADED":
      return { tone: "attention", label: "Atención" };
    case "BLOCKED":
      return { tone: "blocked", label: "Bloqueado" };
    default:
      return { tone: "unknown", label: AUTO_HOME_NO_DATA_LABEL };
  }
}

function openOperationsLabel(count: number): string {
  if (count === 0) return "Sin operaciones abiertas";
  return count === 1 ? "1 abierta" : `${count} abiertas`;
}

export function buildAutoHomeSummary(
  input: AutoHomeSummaryInput,
): AutoHomeSummaryV1 {
  const header = input.header ?? null;
  const isLoading = input.isLoading === true;
  const isError = input.isError === true;
  const loaded = !isLoading && !isError && header !== null;

  const engineLabel = loaded
    ? engineStateLabel(header?.state)
    : AUTO_HOME_NO_DATA_LABEL;
  const lastActivityRaw =
    header?.lastDecisionAt ?? header?.lastHeartbeatAt ?? null;

  const openOperationsCount = (input.cycles ?? []).filter(
    isOperationOpen,
  ).length;

  const risk = riskFromOperationalState(input.riskOperationalState);

  return {
    loaded,
    isLoading,
    isError,
    autoLabel: engineLabel,
    statusLabel: engineLabel,
    lastActivityLabel: lastActivityRaw
      ? formatActivityTime(lastActivityRaw)
      : AUTO_HOME_NO_DATA_LABEL,
    nextStepLabel:
      loaded && header?.nextDecisionAt
        ? `Próximo análisis: ${formatActivityTime(header.nextDecisionAt)}`
        : loaded
          ? "Esperando nueva señal"
          : AUTO_HOME_NO_DATA_LABEL,
    openOperationsCount,
    openOperationsLabel: openOperationsLabel(openOperationsCount),
    hasOpenOperations: openOperationsCount > 0,
    riskTone: risk.tone,
    riskLabel: risk.label,
  };
}
