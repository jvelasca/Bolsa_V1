/**
 * AUTO UI REFACTOR 1.0 — "operación única": pliega los DTO existentes en UNA historia.
 *
 * Read-only y PURO: NO re-deriva cifras ni inventa pasos. Cada etapa o bien se copia de un
 * paso durable del monitor (con su medición) o se declara `NOT_MEASURED` cuando no existe traza
 * por ciclo. Regla intacta: un valor NO MEDIDO nunca es `0`.
 *
 * Orden fijo de la operación:
 *
 *   OPPORTUNITY → SIGNAL → DECISION → RISK → RESERVATION → ORDER → FILL → POSITION →
 *   PROTECTION → EXIT → SETTLEMENT → RESULT → EXPLANATION
 *
 * @see packages/py/application/src/bolsa_application/auto_operational_monitor.py
 */

import {
  formatMonitorFactValue,
  NO_MEASUREMENT_LABEL,
  type AutoMonitorCycleV1,
  type AutoMonitorStepV1,
} from "./auto-operational-monitor.js";

export const AUTO_OPERATION_STORY_ORDER = [
  "OPPORTUNITY",
  "SIGNAL",
  "DECISION",
  "RISK",
  "RESERVATION",
  "ORDER",
  "FILL",
  "POSITION",
  "PROTECTION",
  "EXIT",
  "SETTLEMENT",
  "RESULT",
  "EXPLANATION",
] as const;

export type AutoOperationStoryStageId =
  (typeof AUTO_OPERATION_STORY_ORDER)[number];

export type AutoOperationStoryState =
  | "REACHED"
  | "PENDING"
  | "ABSENT"
  | "NOT_MEASURED";

const STORY_STATE_LABELS: Record<AutoOperationStoryState, string> = {
  REACHED: "alcanzado",
  PENDING: "pendiente",
  ABSENT: "ausente",
  NOT_MEASURED: NO_MEASUREMENT_LABEL,
};

const STORY_STATE_TONES: Record<AutoOperationStoryState, string> = {
  REACHED: "text-emerald-600 dark:text-emerald-400",
  PENDING: "text-muted-foreground",
  ABSENT: "text-destructive",
  NOT_MEASURED: "text-amber-600 dark:text-amber-400",
};

const STORY_STATE_DOTS: Record<AutoOperationStoryState, string> = {
  REACHED: "bg-emerald-500",
  PENDING: "bg-muted-foreground/40",
  ABSENT: "bg-destructive",
  NOT_MEASURED: "bg-amber-500",
};

export type AutoOperationStoryFact = {
  label: string;
  value: string;
  measurement: string;
};

export type AutoOperationStoryStage = {
  id: AutoOperationStoryStageId;
  /** Posición en la historia (0-based): la UI no re-ordena. */
  index: number;
  label: string;
  /** Paso durable del que se copia la etapa (``null`` = etapa derivada/contextual). */
  sourceStepId: string | null;
  state: AutoOperationStoryState;
  stateLabel: string;
  tone: string;
  dotTone: string;
  at: string | null;
  measurement: string;
  facts: AutoOperationStoryFact[];
  note: string | null;
};

/** Explicación OOS/DÍA-D del instrumento (se copia tal cual: NO se re-deriva). */
export type AutoOperationStoryExplanationInput = {
  verdict: string;
  verdictReason?: string | null;
  evidenceQuality: string;
  expectancyR?: number | null;
  hitRate?: number | null;
  measuredCycles?: number | null;
  errorTotal?: number | null;
};

export type AutoOperationStoryResult = {
  pnl: unknown;
  closedAt: string | null;
  measurement: string;
};

export type AutoOperationStoryV1 = {
  cycleId: string | null;
  instrumentId: string | null;
  direction: string | null;
  closed: boolean | null;
  closedMeasurement: string | null;
  stages: AutoOperationStoryStage[];
  result: AutoOperationStoryResult | null;
  notes: string[];
};

type StageSpec = {
  id: AutoOperationStoryStageId;
  label: string;
  sourceStepId: string | null;
  derivedNote?: string;
};

/** Mapa explícito etapa → paso durable (o ``null`` si la etapa no tiene traza por ciclo). */
const STORY_STAGE_SPECS: readonly StageSpec[] = [
  {
    id: "OPPORTUNITY",
    label: "Oportunidad",
    sourceStepId: null,
    derivedNote: "la oportunidad (watch PIT) no se materializa por ciclo",
  },
  { id: "SIGNAL", label: "Señal", sourceStepId: "SIGNAL" },
  { id: "DECISION", label: "Decisión", sourceStepId: "TOP_N" },
  { id: "RISK", label: "Riesgo", sourceStepId: "RISK" },
  { id: "RESERVATION", label: "Reserva", sourceStepId: "RESERVATION" },
  { id: "ORDER", label: "Orden", sourceStepId: "ORDER" },
  { id: "FILL", label: "Fill", sourceStepId: "FILL" },
  {
    id: "POSITION",
    label: "Posición",
    sourceStepId: "FILL",
    derivedNote: "posición derivada de los fills (no hay paso durable propio)",
  },
  { id: "PROTECTION", label: "Protección", sourceStepId: "PROTECTION" },
  {
    id: "EXIT",
    label: "Salida",
    sourceStepId: "SETTLEMENT",
    derivedNote: "el hecho de salida es la liquidación durable",
  },
  { id: "SETTLEMENT", label: "Liquidación", sourceStepId: "SETTLEMENT" },
  { id: "RESULT", label: "Resultado", sourceStepId: "CYCLE_CLOSED" },
  { id: "EXPLANATION", label: "Explicación", sourceStepId: null },
];

function mapStepState(
  step: AutoMonitorStepV1 | undefined,
): AutoOperationStoryState {
  switch (step?.state) {
    case "reached":
      return "REACHED";
    case "pending":
      return "PENDING";
    case "absent":
      return "ABSENT";
    default:
      return "NOT_MEASURED";
  }
}

function joinNote(
  derived: string | undefined,
  step: AutoMonitorStepV1 | undefined,
): string | null {
  const parts: string[] = [];
  if (step === undefined && derived === undefined) {
    parts.push("paso no materializado en el spine");
  }
  if (derived) parts.push(derived);
  if (step?.note) parts.push(step.note);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function baseStage(
  spec: StageSpec,
  index: number,
  state: AutoOperationStoryState,
): AutoOperationStoryStage {
  return {
    id: spec.id,
    index,
    label: spec.label,
    sourceStepId: spec.sourceStepId,
    state,
    stateLabel: STORY_STATE_LABELS[state],
    tone: STORY_STATE_TONES[state],
    dotTone: STORY_STATE_DOTS[state],
    at: null,
    measurement: "UNKNOWN",
    facts: [],
    note: null,
  };
}

/** Hecho cuya medición se deduce del valor: sin valor NUNCA se declara MEDIDO. */
function measuredFact(label: string, value: unknown): AutoOperationStoryFact {
  const measured = value !== null && value !== undefined;
  const measurement = measured ? "COMPLETE" : "UNKNOWN";
  return {
    label,
    value: formatMonitorFactValue(value, measurement),
    measurement,
  };
}

function buildExplanationStage(
  spec: StageSpec,
  index: number,
  explanation: AutoOperationStoryExplanationInput | null | undefined,
): AutoOperationStoryStage {
  if (!explanation) {
    const stage = baseStage(spec, index, "NOT_MEASURED");
    return { ...stage, note: "sin feedback OOS/DÍA-D para el instrumento" };
  }
  return {
    ...baseStage(spec, index, "REACHED"),
    measurement: "COMPLETE",
    facts: [
      {
        label: "veredicto",
        value: explanation.verdict,
        measurement: "COMPLETE",
      },
      measuredFact("motivo", explanation.verdictReason ?? null),
      {
        label: "evidencia",
        value: explanation.evidenceQuality,
        measurement: "COMPLETE",
      },
      measuredFact("R medio", explanation.expectancyR ?? null),
      measuredFact("hit", explanation.hitRate ?? null),
      measuredFact("n", explanation.measuredCycles ?? null),
      measuredFact("errores", explanation.errorTotal ?? null),
    ],
  };
}

/**
 * Pliega un ciclo del monitor (y, si existe, su explicación OOS/DÍA-D) en la historia única.
 *
 * ``cycle`` ausente ⇒ todas las etapas de traza quedan `NOT_MEASURED` (nunca `0`/`REACHED`).
 */
export function buildAutoOperationStory(input: {
  cycle?: AutoMonitorCycleV1 | null;
  explanation?: AutoOperationStoryExplanationInput | null;
}): AutoOperationStoryV1 {
  const cycle = input.cycle ?? null;
  const stepsById = new Map<string, AutoMonitorStepV1>(
    (cycle?.steps ?? []).map((step) => [step.id, step]),
  );

  const stages = STORY_STAGE_SPECS.map((spec, index) => {
    if (spec.id === "OPPORTUNITY") {
      return {
        ...baseStage(spec, index, "NOT_MEASURED"),
        note: spec.derivedNote ?? null,
      };
    }
    if (spec.id === "EXPLANATION") {
      return buildExplanationStage(spec, index, input.explanation ?? null);
    }
    const step = spec.sourceStepId
      ? stepsById.get(spec.sourceStepId)
      : undefined;
    const state = mapStepState(step);
    return {
      ...baseStage(spec, index, state),
      at: step?.at ?? null,
      measurement: step?.measurement ?? "UNKNOWN",
      facts: (step?.facts ?? []).map((fact) => ({
        label: fact.key,
        value: formatMonitorFactValue(fact.value, fact.measurement),
        measurement: fact.measurement,
      })),
      note: joinNote(spec.derivedNote, step),
    };
  });

  return {
    cycleId: cycle?.cycleId ?? null,
    instrumentId: cycle?.instrumentId ?? null,
    direction: cycle?.direction ?? null,
    closed: cycle?.closed ?? null,
    closedMeasurement: cycle?.closedMeasurement ?? null,
    stages,
    result: cycle?.result
      ? {
          pnl: cycle.result.pnl ?? null,
          closedAt: cycle.result.closedAt ?? null,
          measurement: cycle.closedMeasurement ?? "UNKNOWN",
        }
      : null,
    notes: cycle?.notes ?? [],
  };
}
