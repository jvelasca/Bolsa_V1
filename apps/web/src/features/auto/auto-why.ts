/**
 * AUTO UI REFACTOR 4.0 (P2) — «¿Por qué?» transversal (read-model puro).
 *
 * Traduce el estado de AUTO a una explicación de primer nivel: qué se cumplió, qué no y qué no
 * se pudo medir. No inventa cifras ni recalcula nada: usa los hechos ya copiados por
 * `auto-home-summary` / `auto-human-state`.
 *
 * Invariantes:
 * - **Tri-estado.** Cada razón es `ok`, `no` o `unknown`; `unknown` no se pinta como `no`.
 * - **`UNKNOWN ≠ 0`.** Un hueco se declara «Sin dato todavía».
 * - **No operar ≠ no funcionar.** La conclusión explica que esperar es un resultado válido.
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §1.8
 */

import {
  AUTO_HOME_NO_DATA_LABEL,
  activityLabel,
  engineStateLabel,
  isActivityStale,
  type AutoHomeHeaderFacts,
} from "@/features/auto/auto-home-summary";
import type { AutoHumanStateV1 } from "@/features/auto/auto-human-state";

export type AutoWhyReasonStatus = "ok" | "no" | "unknown";

export type AutoWhyReasonV1 = {
  label: string;
  status: AutoWhyReasonStatus;
  /** Nota corta opcional (nivel 1). */
  detail: string | null;
};

export type AutoWhyV1 = {
  title: string;
  summary: string;
  reasons: AutoWhyReasonV1[];
  conclusion: string;
};

export const AUTO_WHY_TITLE = "¿Por qué AUTO está así?";
export const AUTO_WHY_NO_DATA = "Sin dato todavía";

export type AutoWhyInput = {
  state: AutoHumanStateV1;
  header?: AutoHomeHeaderFacts | null;
  /** `operationalState` de la integridad financiera (`OK` | `DEGRADED` | `BLOCKED`). */
  riskOperationalState?: string | null;
  /** ¿Hay alguna operación en curso? */
  hasOperationsInCourse?: boolean;
};

function reason(
  label: string,
  status: AutoWhyReasonStatus,
  detail: string | null = null,
): AutoWhyReasonV1 {
  return { label, status, detail };
}

/** Razón derivada de un hecho medido: presente con medición COMPLETE ⇒ ok, si no, hueco. */
function measuredReason(
  label: string,
  value: string | null | undefined,
  measurement: string | null | undefined,
): AutoWhyReasonV1 {
  if (value == null || value === "") {
    return reason(label, "unknown", AUTO_WHY_NO_DATA);
  }
  if ((measurement ?? "UNKNOWN") !== "COMPLETE") {
    return reason(label, "unknown", AUTO_WHY_NO_DATA);
  }
  return reason(label, "ok", null);
}

export function buildAutoStateWhy(input: AutoWhyInput): AutoWhyV1 {
  const header = input.header ?? null;
  const engine = engineStateLabel(header?.state);
  const activityStale = isActivityStale(
    header?.currentActivityAt,
    header?.asOf,
    header?.currentActivityAtMeasurement,
  );
  const activity = activityStale
    ? AUTO_HOME_NO_DATA_LABEL
    : activityLabel(
        header?.currentActivity,
        header?.currentActivityMeasurement,
      );

  const reasons: AutoWhyReasonV1[] = [
    engine === AUTO_HOME_NO_DATA_LABEL
      ? reason("Motor de AUTO medido", "unknown", AUTO_WHY_NO_DATA)
      : engine === "Funcionando"
        ? reason("Motor de AUTO en marcha", "ok", null)
        : reason(`Motor de AUTO: ${engine}`, "no", null),
    measuredReason(
      "Datos del mercado al día",
      header?.currentActivityAt,
      header?.currentActivityAtMeasurement,
    ),
    riskReason(input.riskOperationalState),
    activity === "Esperando señal"
      ? reason(
          "Oportunidad suficientemente buena",
          "no",
          "Todavía no hay señal",
        )
      : activity === AUTO_HOME_NO_DATA_LABEL
        ? reason(
            "Oportunidad suficientemente buena",
            "unknown",
            AUTO_WHY_NO_DATA,
          )
        : reason("Oportunidad suficientemente buena", "ok", null),
    input.hasOperationsInCourse
      ? reason("Operación en curso", "ok", null)
      : reason("Operación en curso", "no", "Ninguna todavía"),
  ];

  return {
    title: AUTO_WHY_TITLE,
    summary: input.state.sentence,
    reasons,
    conclusion:
      input.state.id === "waiting"
        ? "Resultado: esperar. Es un resultado válido, no un fallo."
        : input.state.id === null
          ? "Resultado: todavía no hay una lectura suficiente para confirmar el estado."
          : `Resultado: ${input.state.label}.`,
  };
}

function riskReason(state: string | null | undefined): AutoWhyReasonV1 {
  switch (state) {
    case "OK":
      return reason("Riesgo aceptable", "ok", null);
    case "DEGRADED":
      return reason("Riesgo aceptable", "no", "Integridad degradada");
    case "BLOCKED":
      return reason("Riesgo aceptable", "no", "Entradas bloqueadas");
    default:
      return reason("Riesgo aceptable", "unknown", AUTO_WHY_NO_DATA);
  }
}
