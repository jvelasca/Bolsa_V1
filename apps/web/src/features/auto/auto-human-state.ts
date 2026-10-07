/**
 * AUTO UI REFACTOR 4.0 (P1) — estado humano unificado + frase-resumen (helper puro).
 *
 * El backend expone muchos estados internos válidos (`RUNNING`, `PAUSED`, `DEGRADED`,
 * `BLOCKED`, `REQUIRES_ATTENTION`, `ANALYZING`, `WAITING_SIGNAL`, `PREPARING_OPERATION`,
 * `WAITING_EXECUTION`, `APPLYING_RESULT`, `NO_ACTIVITY`). El usuario básico no debe
 * aprendérselos: este helper los colapsa a **cinco** estados humanos y produce una única
 * frase que cuenta qué está pasando.
 *
 * Invariantes:
 * - **No re-deriva.** Copia los hechos ya producidos por `auto-home-summary`
 *   (`engineStateLabel`, `activityLabel`) y sólo los agrupa.
 * - **Fail-closed.** Sin cabecera, o con un token fuera del conjunto cerrado, el estado es
 *   «Sin dato todavía»; nunca se inventa «Funcionando».
 * - **`UNKNOWN ≠ 0`.** Un hueco se declara; no se colapsa a un estado verde.
 * - **No operar ≠ no funcionar.** `ESPERANDO` explica que AUTO trabaja aunque no haya operación.
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §1.7 §1.8
 */

import {
  AUTO_HOME_NO_DATA_LABEL,
  activityLabel,
  engineStateLabel,
  isActivityStale,
  type AutoHomeHeaderFacts,
  type AutoHomeRiskTone,
} from "@/features/auto/auto-home-summary";

export type AutoHumanStateId =
  | "working"
  | "analyzing"
  | "waiting"
  | "attention"
  | "stopped";

/** Tono visual del estado humano: verde, informativo, espera, atención, detenido. */
export type AutoHumanTone = "ok" | "info" | "wait" | "attention" | "stop";

export const AUTO_HUMAN_STATE_LABEL: Record<AutoHumanStateId, string> = {
  working: "FUNCIONANDO",
  analyzing: "ANALIZANDO",
  waiting: "ESPERANDO",
  attention: "ATENCIÓN",
  stopped: "DETENIDO",
};

/** Frase que acompaña al estado. Lenguaje de usuario, no de ingeniería. */
export const AUTO_HUMAN_STATE_SENTENCE: Record<AutoHumanStateId, string> = {
  working:
    "AUTO está funcionando correctamente. Ahora mismo no hay ninguna operación en curso.",
  analyzing: "AUTO está analizando el mercado y evaluando oportunidades.",
  waiting:
    "AUTO está esperando una oportunidad suficientemente buena. No operar no significa que esté parado.",
  attention:
    "AUTO necesita atención. Revisa el estado del sistema antes de confiar en nuevas entradas.",
  stopped: "AUTO está detenido. No se están evaluando nuevas oportunidades.",
};

export type AutoHumanStateV1 = {
  /** `true` = la lectura está disponible (aunque el estado sea un hueco declarado). */
  ready: boolean;
  isLoading: boolean;
  isError: boolean;
  /** `null` = hueco (cargando/error/sin dato): no se afirma un estado humano. */
  id: AutoHumanStateId | null;
  /** `FUNCIONANDO` … o `Sin dato todavía`. */
  label: string;
  tone: AutoHumanTone;
  /** Frase-resumen de primer nivel. */
  sentence: string;
};

export type AutoHumanStateInput = {
  header?: AutoHomeHeaderFacts | null;
  /** `operationalState` de la integridad financiera (`OK` | `DEGRADED` | `BLOCKED`). */
  riskOperationalState?: string | null;
  isLoading?: boolean;
  isError?: boolean;
};

const TONE_BY_ID: Record<AutoHumanStateId, AutoHumanTone> = {
  working: "ok",
  analyzing: "info",
  waiting: "wait",
  attention: "attention",
  stopped: "stop",
};

/** Actividades que significan «AUTO está trabajando ahora mismo». */
const ANALYZING_ACTIVITIES = new Set([
  "Analizando",
  "Preparando operación",
  "Esperando ejecución",
  "Aplicando resultado",
]);

/** Estados de motor que requieren revisión del usuario. */
const ATTENTION_ENGINE_LABELS = new Set([
  "Funcionamiento limitado",
  "Bloqueado",
  "Atención requerida",
]);

function riskNeedsAttention(tone: AutoHomeRiskTone): boolean {
  return tone === "attention" || tone === "blocked";
}

/**
 * Estado humano + frase. `null` cuando no hay lectura (cargando/error/sin cabecera).
 * No deriva de `RUNNING` una actividad concreta: usa la fase medida, si existe.
 */
export function buildAutoHumanState(
  input: AutoHumanStateInput,
): AutoHumanStateV1 {
  const isLoading = input.isLoading === true;
  const isError = input.isError === true;
  const header = input.header ?? null;
  const loaded = !isLoading && !isError && header !== null;

  const riskTone = riskToneFromOperationalState(input.riskOperationalState);

  if (!loaded) {
    return {
      ready: false,
      isLoading,
      isError,
      id: null,
      label: AUTO_HOME_NO_DATA_LABEL,
      tone: "wait",
      sentence: isError
        ? "No se pudo leer el estado de AUTO. La información puede estar incompleta."
        : "Todavía no hay una lectura del estado de AUTO.",
    };
  }

  const engine = engineStateLabel(header.state);
  const activity = isActivityStale(
    header.currentActivityAt,
    header.asOf,
    header.currentActivityAtMeasurement,
  )
    ? AUTO_HOME_NO_DATA_LABEL
    : activityLabel(header.currentActivity, header.currentActivityMeasurement);

  let id: AutoHumanStateId;
  if (riskNeedsAttention(riskTone) || ATTENTION_ENGINE_LABELS.has(engine)) {
    id = "attention";
  } else if (engine === "Detenido") {
    id = "stopped";
  } else if (engine === AUTO_HOME_NO_DATA_LABEL) {
    // Motor no medido: no se afirma funcionamiento. Es un hueco, no un verde.
    return {
      ready: false,
      isLoading,
      isError,
      id: null,
      label: AUTO_HOME_NO_DATA_LABEL,
      tone: "wait",
      sentence: "No hay una lectura medible del motor de AUTO todavía.",
    };
  } else if (ANALYZING_ACTIVITIES.has(activity)) {
    id = "analyzing";
  } else if (activity === "Esperando señal") {
    id = "waiting";
  } else {
    id = "working";
  }

  return {
    ready: true,
    isLoading,
    isError,
    id,
    label: AUTO_HUMAN_STATE_LABEL[id],
    tone: TONE_BY_ID[id],
    sentence: AUTO_HUMAN_STATE_SENTENCE[id],
  };
}

function riskToneFromOperationalState(
  state: string | null | undefined,
): AutoHomeRiskTone {
  switch (state) {
    case "OK":
      return "ok";
    case "DEGRADED":
      return "attention";
    case "BLOCKED":
      return "blocked";
    default:
      return "unknown";
  }
}
