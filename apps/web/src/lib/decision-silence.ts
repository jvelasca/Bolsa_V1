import { isWarmupInsufficientReason } from "@bolsa/shared";

/**
 * Bloque funcional posterior a `v2.88.165-beta` (sello `.168`) — «no evaluable» ≠ «sin señal».
 *
 * El monitor publica los HOLD de la ACTIVE con su motivo (`signalHolds[].reason`, el literal del
 * vocabulario cerrado `ACTIVE_HOLD_REASONS`). Antes de esto la UI solo veía `action: "HOLD"`: un
 * HOLD porque *el motor no llegó a evaluar* y un HOLD porque *evaluó y no había señal* se
 * pintaban igual, y el operador no podía saber si el silencio era una decisión o un hueco.
 *
 * Tres reglas, y ninguna adorna el dato:
 *
 * 1. La clasificación es por el **literal exacto** del vocabulario, no por prosa: un prefijo a
 *    mitad de frase no clasifica (`"warmup_insufficient"` sí; `"warmup"` no).
 * 2. Ausente / vacío ⇒ `unmeasured`: no se evaluó nada y **no** se puede afirmar «sin señal».
 * 3. `not_evaluable` significa que el motor NO pudo decidir (falta de datos, warmup no medible,
 *    libro ilegible). Es un hueco a resolver, no una conclusión de mercado.
 */

/**
 * Causas de silencio de una decisión. `not_evaluable` **no** es `no_signal`:
 * la primera es un hueco del motor, la segunda un hecho del mercado.
 */
export type DecisionSilenceCause =
  | "not_evaluable"
  | "no_signal"
  | "disabled"
  | "not_executable"
  | "unmeasured";

/** Motivos en los que el motor **no llegó a decidir** (ADR-048 incluye el libro ilegible). */
const NOT_EVALUABLE_REASONS = new Set([
  "warmup_unmeasurable",
  "no_snapshot",
  "evaluation_failed",
  // ADR-048 — el libro no se pudo leer: no se sabe si había posición, así que no se decidió.
  "gated_unavailable",
]);

/** Motivos que declaran una **decisión** de no operar (no un hueco de datos). */
const NO_SIGNAL_REASONS = new Set(["no_signal"]);

const DISABLED_REASONS = new Set(["active_signal_disabled"]);
const NOT_EXECUTABLE_REASONS = new Set(["no_executable"]);

/**
 * Clasifica el motivo de un HOLD declarado por la ACTIVE.
 *
 * `warmup_insufficient` se reconoce por el **prefijo estable** exportado por `@bolsa/shared`
 * (`isWarmupInsufficientReason`), porque su texto lo completa el evaluador del scan con la serie
 * y las barras que faltan. El resto son literales exactos del vocabulario cerrado.
 */
export function decisionSilenceCause(
  reason: string | null | undefined,
): DecisionSilenceCause {
  const value = (reason ?? "").trim();
  if (!value) return "unmeasured";
  if (NOT_EVALUABLE_REASONS.has(value)) return "not_evaluable";
  if (isWarmupInsufficientReason(value)) return "not_evaluable";
  if (NO_SIGNAL_REASONS.has(value)) return "no_signal";
  if (DISABLED_REASONS.has(value)) return "disabled";
  if (NOT_EXECUTABLE_REASONS.has(value)) return "not_executable";
  // Un motivo fuera del vocabulario cerrado NO se presenta como una causa conocida: se declara
  // que no se pudo medir la causa (la ausencia de medición es información, no un relleno).
  return "unmeasured";
}

export interface DecisionSilenceBreakdown {
  /** HOLD en los que el motor **no** pudo decidir. */
  notEvaluable: number;
  /** HOLD en los que evaluó y no había señal. */
  noSignal: number;
  /** HOLD con la señal apagada por configuración. */
  disabled: number;
  /** HOLD sin definición ejecutable. */
  notExecutable: number;
  /** Declaraciones cuyo motivo no se pudo medir (ausente o fuera del vocabulario). */
  unmeasured: number;
}

export const EMPTY_DECISION_SILENCE: DecisionSilenceBreakdown = {
  notEvaluable: 0,
  noSignal: 0,
  disabled: 0,
  notExecutable: 0,
  unmeasured: 0,
};

/** Agrega los HOLD declarados por causa. Entrada vacía ⇒ todo a cero (no se inventa nada). */
export function decisionSilenceBreakdown(
  holds: ReadonlyArray<{ reason?: string | null }>,
): DecisionSilenceBreakdown {
  const breakdown: DecisionSilenceBreakdown = { ...EMPTY_DECISION_SILENCE };
  for (const hold of holds) {
    switch (decisionSilenceCause(hold.reason)) {
      case "not_evaluable":
        breakdown.notEvaluable += 1;
        break;
      case "no_signal":
        breakdown.noSignal += 1;
        break;
      case "disabled":
        breakdown.disabled += 1;
        break;
      case "not_executable":
        breakdown.notExecutable += 1;
        break;
      default:
        breakdown.unmeasured += 1;
    }
  }
  return breakdown;
}

/** Etiqueta corta de la causa, para celdas y leyendas. `null` = no se declara causa. */
export function decisionSilenceLabel(cause: DecisionSilenceCause): string {
  switch (cause) {
    case "not_evaluable":
      return "no evaluable";
    case "no_signal":
      return "sin señal";
    case "disabled":
      return "señal apagada";
    case "not_executable":
      return "sin definición ejecutable";
    default:
      return "sin dato";
  }
}

/** El motivo concreto, cuando es legible sin abrir el journal; `null` si no se midió. */
export function decisionSilenceReasonLabel(
  reason: string | null | undefined,
): string | null {
  const value = (reason ?? "").trim();
  if (!value) return null;
  if (isWarmupInsufficientReason(value)) return "warmup insuficiente";
  switch (value) {
    case "warmup_unmeasurable":
      return "warmup no medible";
    case "no_snapshot":
      return "sin barras";
    case "evaluation_failed":
      return "evaluación fallida";
    case "gated_unavailable":
      return "libro no legible";
    case "no_signal":
      return "sin señal";
    case "active_signal_disabled":
      return "señal apagada";
    case "no_executable":
      return "sin definición ejecutable";
    default:
      return null;
  }
}

export interface DecisionSilenceSummary {
  breakdown: DecisionSilenceBreakdown;
  total: number;
  headline: string;
  detail: string | null;
}

function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

/**
 * Titular honesto de los HOLD declarados.
 *
 * - Sin declaraciones: se dice que no consta, **no** «sin señal» (no hay hecho que lo afirme).
 *   `windowLabel` nombra el alcance leído (`la ventana`, `el día explicado`).
 * - Si hay no evaluables, el titular los separa del resto: «N sin señal · M no evaluables».
 * - Si **todo** lo declarado es no evaluable, el titular no menciona «sin señal».
 */
export function decisionSilenceSummary(
  holds: ReadonlyArray<{ reason?: string | null }>,
  windowLabel = "la ventana",
): DecisionSilenceSummary {
  const breakdown = decisionSilenceBreakdown(holds);
  const total = holds.length;

  if (total === 0) {
    return {
      breakdown,
      total,
      headline: `Sin HOLD declarados en ${windowLabel}`,
      detail: null,
    };
  }

  const notEvaluable =
    breakdown.notEvaluable +
    breakdown.disabled +
    breakdown.notExecutable +
    breakdown.unmeasured;

  if (breakdown.noSignal === 0 && notEvaluable > 0) {
    return {
      breakdown,
      total,
      headline: "Ningún HOLD con señal evaluada",
      detail: describeNotEvaluable(breakdown),
    };
  }

  if (notEvaluable > 0) {
    return {
      breakdown,
      total,
      headline:
        `${plural(breakdown.noSignal, "sin señal", "sin señal")} · ` +
        `${plural(notEvaluable, "HOLD no evaluable", "HOLD no evaluables")}`,
      detail: describeNotEvaluable(breakdown),
    };
  }

  return {
    breakdown,
    total,
    headline: `${plural(breakdown.noSignal, "HOLD sin señal", "HOLD sin señal")}`,
    detail: null,
  };
}

function describeNotEvaluable(
  breakdown: DecisionSilenceBreakdown,
): string | null {
  const parts: string[] = [];
  if (breakdown.notEvaluable > 0) {
    parts.push(
      `${plural(breakdown.notEvaluable, "no evaluable", "no evaluables")}: ` +
        "faltan datos, warmup no medible o libro no legible",
    );
  }
  if (breakdown.disabled > 0) {
    parts.push(
      `${plural(breakdown.disabled, "con la señal apagada", "con la señal apagada")}`,
    );
  }
  if (breakdown.notExecutable > 0) {
    parts.push(
      `${plural(breakdown.notExecutable, "sin definición ejecutable", "sin definición ejecutable")}`,
    );
  }
  if (breakdown.unmeasured > 0) {
    parts.push(
      `${plural(breakdown.unmeasured, "sin motivo medido", "sin motivo medido")}`,
    );
  }
  return parts.length ? `${parts.join(" · ")}.` : null;
}

/**
 * `true` si la causa es un hueco a resolver (`no evaluable` o `sin dato`), no una decisión.
 *
 * Fuente ÚNICA del conjunto: el panel de HOLD y el aviso ámbar lo consultan aquí en lugar de
 * declarar su propia lista, para que monitor y Actividad no discrepen sobre qué es un hueco.
 */
export function isNotEvaluableCause(cause: DecisionSilenceCause): boolean {
  return cause === "not_evaluable" || cause === "unmeasured";
}

/** Los HOLD no evaluables, para listarlos junto al titular sin abrir el journal. */
export function notEvaluableHolds<T extends { reason?: string | null }>(
  holds: readonly T[],
): T[] {
  return holds.filter((hold) =>
    isNotEvaluableCause(decisionSilenceCause(hold.reason)),
  );
}
