/**
 * AUTO UI REFACTOR 4.0 (P1) — Centro de actividad (read-model puro).
 *
 * Fusiona en **una sola línea temporal** los hechos que hoy hay que reconstruir saltando entre
 * el monitor, el journal y el libro: los pasos ya alcanzados de cada ciclo (`steps[].at`) y el
 * reloj de decisión de la cabecera (`lastDecisionAt`). No ejecuta, no escribe y no re-deriva:
 * copia los sellos y las etiquetas humanas ya producidas.
 *
 * Invariantes:
 * - **No re-deriva.** El sello `at` se copia; la etiqueta sale de `plainStageLabel`.
 * - **`UNKNOWN ≠ 0`.** Un paso sin sello no produce fila (no se inventa una hora).
 * - **Una operación = una historia.** El `cycleId` viaja en `data` y en el deep-link.
 * - Fail-closed: sin hechos, la superficie declara «Sin actividad registrada todavía»; nunca
 *   presenta el hueco como si AUTO no hubiera hecho nada.
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §2
 */

import { plainStageLabel } from "@/features/auto/auto-story-plain-labels";

export const AUTO_ACTIVITY_EMPTY_LABEL = "Sin actividad registrada todavía.";
export const AUTO_ACTIVITY_TICK_LABEL = "AUTO revisó el mercado";

export type AutoActivityKind =
  | "analysis"
  | "signal"
  | "selection"
  | "decision"
  | "reservation"
  | "order"
  | "fill"
  | "settlement"
  | "other";

export type AutoActivityEntryV1 = {
  /** Identidad estable para React (no visible). */
  id: string;
  /** Sello ISO copiado, o `null` si el hecho no trae hora. */
  at: string | null;
  /** `HH:mm` de forma determinista, o `Sin dato todavía`. */
  atLabel: string;
  kind: AutoActivityKind;
  /** Frase de primer nivel ya traducida. */
  label: string;
  /** Símbolo del ciclo, si el hecho pertenece a una operación. */
  symbol: string | null;
  /** `cycleId` para el deep-link a la historia; `null` para el latido del mercado. */
  cycleId: string | null;
};

export type AutoActivityFeedInput = {
  header?: {
    lastDecisionAt?: string | null;
    /** El latido no es una decisión; sólo se usa el sello de decisión. */
    asOf?: string | null;
  } | null;
  cycles?: readonly {
    cycleId: string;
    instrumentId?: string | null;
    steps?: readonly {
      id: string;
      state: string;
      at?: string | null;
      /** Etiqueta técnica de la etapa (fallback si el id es desconocido). */
      label?: string | null;
    }[];
  }[];
};

export type AutoActivityFeedV1 = {
  entries: AutoActivityEntryV1[];
  hasEntries: boolean;
  /** Etiqueta de vacío honesta (sin hechos registrados). */
  emptyLabel: string;
};

const KIND_BY_STEP: Record<string, AutoActivityKind> = {
  SIGNAL: "signal",
  SELECTION: "selection",
  DECISION: "decision",
  RESERVATION: "reservation",
  ORDER: "order",
  FILL: "fill",
  SETTLEMENT: "settlement",
  RESULT: "settlement",
};

/** `HH:mm` determinista desde un ISO; sin `Date`/zona horaria. */
export function activityClockLabel(at: string | null | undefined): string {
  if (!at) return "Sin dato todavía";
  const match = /T(\d{2}):(\d{2})/.exec(at);
  return match ? `${match[1]}:${match[2]}` : at;
}

function kindOf(stepId: string): AutoActivityKind {
  return KIND_BY_STEP[stepId] ?? "other";
}

/** Ordena por sello descendente; los hechos sin hora van al final, en orden estable. */
function sortEntries(entries: AutoActivityEntryV1[]): AutoActivityEntryV1[] {
  return [...entries].sort((a, b) => {
    if (a.at === b.at) return 0;
    if (a.at === null) return 1;
    if (b.at === null) return -1;
    return a.at < b.at ? 1 : -1;
  });
}

export function buildAutoActivityFeed(
  input: AutoActivityFeedInput,
  options?: { limit?: number },
): AutoActivityFeedV1 {
  const entries: AutoActivityEntryV1[] = [];
  const cycles = input.cycles ?? [];

  for (const cycle of cycles) {
    const symbol = cycle.instrumentId?.trim() ? cycle.instrumentId : null;
    for (const step of cycle.steps ?? []) {
      if (step.state !== "reached") continue;
      // Un hecho sin sello no produce fila: no se inventa una hora.
      if (step.at == null || step.at === "") continue;
      entries.push({
        id: `${cycle.cycleId}:${step.id}`,
        at: step.at,
        atLabel: activityClockLabel(step.at),
        kind: kindOf(step.id),
        label: plainStageLabel(step.id, step.label ?? step.id),
        symbol,
        cycleId: cycle.cycleId,
      });
    }
  }

  const tickAt = input.header?.lastDecisionAt ?? null;
  if (tickAt) {
    entries.push({
      id: "market-tick",
      at: tickAt,
      atLabel: activityClockLabel(tickAt),
      kind: "analysis",
      label: AUTO_ACTIVITY_TICK_LABEL,
      symbol: null,
      cycleId: null,
    });
  }

  const sorted = sortEntries(entries);
  const limit = options?.limit;
  const limited =
    typeof limit === "number" && limit > 0 ? sorted.slice(0, limit) : sorted;

  return {
    entries: limited,
    hasEntries: limited.length > 0,
    emptyLabel: AUTO_ACTIVITY_EMPTY_LABEL,
  };
}
