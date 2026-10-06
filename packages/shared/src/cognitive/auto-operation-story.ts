/**
 * AUTO UI REFACTOR 1.0 — "operación única": pliega los DTO existentes en UNA historia.
 *
 * Read-only y PURO: NO re-deriva cifras ni inventa pasos. Cada etapa o bien se copia de un
 * paso durable del monitor (con su medición) o se declara `NOT_MEASURED` cuando no existe traza
 * por ciclo. Regla intacta: un valor NO MEDIDO nunca es `0`.
 *
 * Modelo semántico (`docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md`): cada concepto
 * declara su `kind` (hecho / derivada / contexto / explicación) y su `group`. Los 14 conceptos del
 * modelo son `OPPORTUNITY → SIGNAL → SELECTION → DECISION → RISK → RESERVATION → ORDER → FILL →
 * POSITION → PROTECTION → EXIT → SETTLEMENT → RESULT → EXPLANATION`; `OPPORTUNITY` es CONTEXTO
 * (no un hecho de la operación) y `SELECTION` (TOP-N) es distinto de `DECISION` (cartera).
 *
 * @see packages/py/application/src/bolsa_application/auto_operational_monitor.py
 */

import {
  NO_MEASUREMENT_LABEL,
  type AutoMonitorCycleV1,
  type AutoMonitorStepV1,
} from "./auto-operational-monitor.js";

export const AUTO_OPERATION_STORY_ORDER = [
  "OPPORTUNITY",
  "SIGNAL",
  "SELECTION",
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

/** Qué ES la etapa (criterio de admisión del modelo semántico). */
export type AutoOperationStoryKind =
  | "FACT"
  | "DERIVED"
  | "CONTEXT"
  | "EXPLANATION";

/**
 * Bloque al que pertenece. `OPERATION` = hechos de esta operación; `CONTEXT` = lo que la originó;
 * `EXPLANATION` = conocimiento cross-ciclo (DÍA-D/OOS), que **no** es un hecho del ciclo y por eso
 * no vive dentro de `OPERATION` (spec AUTO UI REFACTOR 3.0 §3.1).
 */
export type AutoOperationStoryGroup = "OPERATION" | "CONTEXT" | "EXPLANATION";

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
  /** Valor CRUDO: el formateo honesto (y su medición) lo aplica la capa de UI. */
  value: unknown;
  measurement: string;
};

export type AutoOperationStoryStage = {
  id: AutoOperationStoryStageId;
  /** Posición en la historia (0-based): la UI no re-ordena. */
  index: number;
  label: string;
  /** Qué ES la etapa: hecho durable / derivada / contexto / explicación. */
  kind: AutoOperationStoryKind;
  /** Bloque: hechos de la operación (`OPERATION`) o contexto (`CONTEXT`). */
  group: AutoOperationStoryGroup;
  /** Paso durable del que se copia la etapa (``null`` = etapa derivada/contextual). */
  sourceStepId: string | null;
  /**
   * Etapa en la que esta se PLIEGA visualmente (``null`` = fila propia). `EXIT` se pliega en
   * `SETTLEMENT` mientras no exista una traza durable propia de intención de salida: la UI no
   * pinta dos filas `REACHED` a partir del MISMO hecho financiero (spec §4.2).
   */
  foldedInto: AutoOperationStoryStageId | null;
  state: AutoOperationStoryState;
  stateLabel: string;
  tone: string;
  dotTone: string;
  at: string | null;
  measurement: string;
  facts: AutoOperationStoryFact[];
  note: string | null;
};

/**
 * Identidad de la explicación: a QUÉ operación responde. Hoy el artefacto DÍA-D sólo materializa
 * `instrument`, así que `cycleId` y los demás ejes se copian del ciclo y los que el artefacto no
 * expone (`timeframe`, `regime`) se declaran `null` (⇒ `NO MEDIDO`). La clave primaria objetivo es
 * `cycleId` + ejes de desambiguación (spec §6); migrar el contrato es deuda declarada.
 */
export type AutoOperationStoryExplanationIdentity = {
  cycleId: string | null;
  instrument: string | null;
  strategyVersion: string | null;
  direction: string | null;
  entryDay: string | null;
  timeframe: string | null;
  regime: string | null;
};

/**
 * Cómo se resolvió la explicación de ESTA operación: por su clave de ciclo (exacta) o por
 * instrumento (fallback parcial). El veredicto OOS es AGREGADO por instrumento; `resolution`
 * declara si el artefacto pudo atar la explicación al `cycleId` o sólo al símbolo.
 */
export type AutoOperationStoryExplanationResolution = "cycleId" | "instrument";

/** Explicación OOS/DÍA-D del instrumento (se copia tal cual: NO se re-deriva). */
export type AutoOperationStoryExplanationInput = {
  verdict: string;
  verdictReason?: string | null;
  evidenceQuality: string;
  expectancyR?: number | null;
  hitRate?: number | null;
  measuredCycles?: number | null;
  errorTotal?: number | null;
  /** Ejes que desambiguan a qué operación responde la explicación. */
  identity?: AutoOperationStoryExplanationIdentity | null;
  /** Si el artefacto ató la explicación al `cycleId` o sólo al instrumento (fallback). */
  resolution?: AutoOperationStoryExplanationResolution | null;
};

/** Contexto que ORIGINÓ la operación (no es un hecho del ciclo). */
export type AutoOperationStoryContextItem = {
  id: string;
  label: string;
  value: string;
  measurement: string;
  note: string | null;
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
  /** Los 14 conceptos del modelo, con su `kind`/`group` (la UI no re-ordena). */
  stages: AutoOperationStoryStage[];
  /** Contexto que originó la operación (universo PIT, estrategia, régimen, …). */
  context: AutoOperationStoryContextItem[];
  result: AutoOperationStoryResult | null;
  notes: string[];
};

type StageSpec = {
  id: AutoOperationStoryStageId;
  label: string;
  kind: AutoOperationStoryKind;
  group: AutoOperationStoryGroup;
  sourceStepId: string | null;
  derivedNote?: string;
  /** Etapa que absorbe esta fila en la vista (mientras no tenga traza propia). */
  foldedInto?: AutoOperationStoryStageId | null;
};

/** Mapa explícito etapa → paso durable (o ``null`` si la etapa no tiene traza por ciclo). */
const STORY_STAGE_SPECS: readonly StageSpec[] = [
  {
    id: "OPPORTUNITY",
    label: "Oportunidad",
    kind: "CONTEXT",
    group: "CONTEXT",
    sourceStepId: null,
    derivedNote: "la oportunidad (watch PIT) no se materializa por ciclo",
  },
  {
    id: "SIGNAL",
    label: "Señal",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "SIGNAL",
  },
  {
    id: "SELECTION",
    label: "Selección · TOP-N",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "TOP_N",
  },
  {
    // `TOP_N` NO es la decisión de cartera: es la SELECCIÓN/ranking del instrumento.
    id: "DECISION",
    label: "Decisión",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: null,
    derivedNote: "no hay traza durable de decisión de cartera",
  },
  {
    id: "RISK",
    label: "Riesgo",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "RISK",
  },
  {
    id: "RESERVATION",
    label: "Reserva",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "RESERVATION",
  },
  {
    id: "ORDER",
    label: "Orden",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "ORDER",
  },
  {
    id: "FILL",
    label: "Fill",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "FILL",
  },
  {
    id: "POSITION",
    label: "Posición",
    kind: "DERIVED",
    group: "OPERATION",
    sourceStepId: "FILL",
    derivedNote: "posición derivada de los fills (no hay paso durable propio)",
  },
  {
    id: "PROTECTION",
    label: "Protección",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "PROTECTION",
  },
  {
    // SALIDA = intención/motivo; el hecho financiero durable es la LIQUIDACIÓN. Mientras no
    // exista traza propia de salida, esta fila se PLIEGA en `SETTLEMENT` (no se duplica el hecho).
    id: "EXIT",
    label: "Salida",
    kind: "DERIVED",
    group: "OPERATION",
    sourceStepId: "SETTLEMENT",
    foldedInto: "SETTLEMENT",
    derivedNote:
      "salida = intención/motivo; el hecho durable es la liquidación",
  },
  {
    id: "SETTLEMENT",
    label: "Liquidación",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "SETTLEMENT",
  },
  {
    id: "RESULT",
    label: "Resultado",
    kind: "FACT",
    group: "OPERATION",
    sourceStepId: "CYCLE_CLOSED",
  },
  {
    // `EXPLANATION` es conocimiento cross-ciclo (DÍA-D/OOS): NO es un hecho de este ciclo, así que
    // tiene grupo propio y no se pinta dentro de la historia de la operación (spec 3.0 §3.1).
    id: "EXPLANATION",
    label: "Explicación",
    kind: "EXPLANATION",
    group: "EXPLANATION",
    sourceStepId: null,
  },
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
    kind: spec.kind,
    group: spec.group,
    sourceStepId: spec.sourceStepId,
    foldedInto: spec.foldedInto ?? null,
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
  return {
    label,
    value: measured ? value : null,
    measurement: measured ? "COMPLETE" : "UNKNOWN",
  };
}

/** Ejes de identidad de la explicación: los que el artefacto no materializa se declaran `NO MEDIDO`. */
function buildExplanationIdentityFacts(
  identity: AutoOperationStoryExplanationIdentity | null | undefined,
): AutoOperationStoryFact[] {
  if (!identity) return [];
  return [
    measuredFact("cycleId", identity.cycleId),
    measuredFact("instrumento", identity.instrument),
    measuredFact("estrategia", identity.strategyVersion),
    measuredFact("dirección", identity.direction),
    measuredFact("día entrada", identity.entryDay),
    measuredFact("timeframe", identity.timeframe),
    measuredFact("régimen", identity.regime),
  ];
}

/** Etiqueta legible de la resolución; `null` si el artefacto no la declara (⇒ NO MEDIDO). */
function explanationResolutionLabel(
  resolution: AutoOperationStoryExplanationResolution | null | undefined,
): string | null {
  if (resolution === "cycleId") return "por ciclo (cycleId)";
  if (resolution === "instrument") return "por instrumento (parcial)";
  return null;
}

/**
 * Nota de honestidad: SÓLO se afirma resolución por `cycleId` si el artefacto la declara. El
 * fallback por instrumento se declara explícitamente PARCIAL (nunca se presenta como de *esa*
 * operación). Sin declaración de resolución se conserva la nota histórica.
 */
function explanationResolutionNote(
  explanation: AutoOperationStoryExplanationInput,
): string | null {
  if (explanation.resolution === "cycleId") {
    return "resuelta por cycleId (DÍA-D); el veredicto OOS es del instrumento en la ventana";
  }
  if (explanation.resolution === "instrument") {
    return "resuelta por instrumento (DÍA-D) — sin clave de ciclo en el artefacto; resolución PARCIAL";
  }
  return explanation.identity
    ? "resuelta por instrumento (DÍA-D); ejes no materiales por ciclo = NO MEDIDO"
    : null;
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
      // Cómo se resolvió (por ciclo o por instrumento): un hueco se declara NO MEDIDO.
      measuredFact(
        "resolución",
        explanationResolutionLabel(explanation.resolution),
      ),
      // A QUÉ operación responde: `cycleId` + ejes; los no materiales se declaran NO MEDIDO.
      ...buildExplanationIdentityFacts(explanation.identity),
    ],
    note: explanationResolutionNote(explanation),
  };
}

/**
 * Contexto que ORIGINÓ la operación. Instrumento/estrategia/dirección se copian del ciclo (o se
 * declaran `NO MEDIDO`); universo PIT / régimen / ranking NO se materializan por ciclo, así que
 * se declaran `NO MEDIDO` — nunca un valor de relleno.
 */
function buildContext(
  cycle: AutoMonitorCycleV1 | null,
): AutoOperationStoryContextItem[] {
  const item = (
    id: string,
    label: string,
    raw: string | null | undefined,
    note: string | null = null,
  ): AutoOperationStoryContextItem => {
    const value = raw ?? null;
    return {
      id,
      label,
      value: value ?? NO_MEASUREMENT_LABEL,
      measurement: value ? "COMPLETE" : "UNKNOWN",
      note,
    };
  };
  return [
    item("INSTRUMENT", "Instrumento", cycle?.instrumentId ?? null),
    item("STRATEGY", "Estrategia", cycle?.strategyVersion ?? null),
    item("DIRECTION", "Dirección", cycle?.direction ?? null),
    item(
      "PIT_UNIVERSE",
      "Universo PIT",
      null,
      "el watch PIT no se materializa por ciclo",
    ),
    item("REGIME", "Régimen", null, "sin régimen durable por ciclo"),
    item(
      "RANKING",
      "Motivo de selección",
      null,
      "no hay motivo de selección durable por ciclo (ver Selección · TOP-N)",
    ),
  ];
}

/**
 * Pliega un ciclo del monitor (y, si existe, su explicación OOS/DÍA-D) en la historia única.
 *
 * ``cycle`` ausente ⇒ todos los conceptos de traza quedan `NOT_MEASURED` (nunca `0`/`REACHED`).
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
    if (spec.id === "EXIT") {
      // Intención/motivo de salida: NO fabrica un hecho financiero propio. Sin traza durable de
      // salida se PLIEGA en `SETTLEMENT`; con traza propia vuelve a ser fila independiente.
      const ownExit = stepsById.get("EXIT");
      const settlement = stepsById.get("SETTLEMENT");
      const evidence = ownExit ?? settlement;
      const foldedInto: AutoOperationStoryStageId | null = ownExit
        ? null
        : "SETTLEMENT";
      return {
        ...baseStage(spec, index, mapStepState(evidence)),
        at: evidence?.at ?? null,
        measurement: evidence?.measurement ?? "UNKNOWN",
        facts: ownExit
          ? ownExit.facts.map((fact) => ({
              label: fact.key,
              value: fact.value,
              measurement: fact.measurement,
            }))
          : [],
        foldedInto,
        note: joinNote(spec.derivedNote, ownExit),
      };
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
        value: fact.value,
        measurement: fact.measurement,
      })),
      note: joinNote(spec.derivedNote, step),
    };
  });

  // Una etapa plegada deja su nota (la intención de salida) en la fila que la absorbe: una sola
  // fila `REACHED`, sin duplicar el mismo hecho (spec §4.2).
  for (const stage of stages) {
    if (stage.foldedInto === null) continue;
    const target = stages.find(
      (candidate) => candidate.id === stage.foldedInto,
    );
    if (target) {
      target.note =
        [target.note, stage.note].filter(Boolean).join(" · ") || null;
    }
  }

  return {
    cycleId: cycle?.cycleId ?? null,
    instrumentId: cycle?.instrumentId ?? null,
    direction: cycle?.direction ?? null,
    closed: cycle?.closed ?? null,
    closedMeasurement: cycle?.closedMeasurement ?? null,
    stages,
    context: buildContext(cycle),
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
