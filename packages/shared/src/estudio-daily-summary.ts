/**
 * `deriveValueSummary` — resumen legible de UN valor del parte diario ESTUDIO.
 *
 * Función PURA (sin React, sin red, sin relojes): recibe lo que el servidor ya declaró y
 * devuelve las CUATRO respuestas que la ficha debe dar de un vistazo, junto a las
 * etiquetas SEPARADAS de clasificación y validación.
 *
 * Doctrina «Sin dato todavía»: un hueco viaja `null` y la frase lo dice; nunca se convierte
 * un «no consta» en «no validada» afirmado. La validación estadística NO se infiere del
 * parte: se pasa aparte (`validation`) o queda como hueco declarado.
 *
 * Separación de conceptos (la que el dictamen exige):
 *   - CLASIFICACIÓN del selector ≠ VALIDACIÓN estadística.
 *   - «Mejor puntuada» solo existe dentro del ranking del día (la foto), nunca como
 *     sinónimo de «validada» ni de «rentable».
 */

import type {
  EstudioChainAttributionV1,
  EstudioChainCycleV1,
  EstudioDailyValueV1,
} from "./estudio-daily-ops.js";

export type SummaryMeasurement = "COMPLETE" | "PARTIAL" | "UNKNOWN";

export type SummarySection = {
  /** Frase principal (una línea, sin jerga). */
  headline: string;
  /** Detalle opcional (motivo ya declarado o cifras que el servidor publicó). */
  detail: string | null;
  measurement: SummaryMeasurement;
};

export type ValueSummaryValidationInput = {
  /** Ops evaluadas K (audit OOS). `null` ⇒ no medido (nunca `0` de relleno). */
  k?: number | null;
  /** Objetivo K declarado por la ventana. `null` ⇒ no declarado. */
  target?: number | null;
  /** Veredicto de la ventana (`INCONCLUSIVE`, `PASS`, …). `null` ⇒ no declarada. */
  windowVerdict?: string | null;
  /** ¿La validación está aprobada? Solo `true` si el servidor lo declara. */
  validated?: boolean | null;
};

export type ValueSummaryChainInput = {
  cycles?: EstudioChainCycleV1[];
} | null;

export type ValueSummary = {
  /** 1 · «¿Qué propone?» */
  proposal: SummarySection;
  /** 2 · «¿Por qué?» */
  why: SummarySection;
  /** 3 · «¿Qué falta para actuar?» */
  missing: SummarySection;
  /** 4 · «¿Está validada?» — SIEMPRE separada de la clasificación. */
  validation: SummarySection & { validated: boolean | null };
  /** Clasificación del selector: es un ranking, NO una validación. */
  classification: SummarySection & {
    rank: number | null;
    runId: string | null;
    bar: string | null;
  };
  /** Datos técnicos que solo deben verse tras el desplegable. */
  technical: {
    instrumentId: string;
    status: string;
    signalId: string | null;
    planId: string | null;
    selectorRunId: string | null;
    asOfBarDate: string | null;
    cycleIds: string[];
    attribution: EstudioChainAttributionV1 | null;
    /** Estado de atribución legible, ya traducido (sin jerga). */
    attributionLabel: string;
  };
};

const num = (value: number | null | undefined): string =>
  value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : String(Number(value.toFixed(4)));

const ATTRIBUTION_LABELS: Record<string, string> = {
  exact:
    "Cadena atribuida: la señal y el plan del parte son los del ciclo ejecutado.",
  mismatch:
    "Cadena NO atribuida: el ciclo ejecutado declara otra señal/plan que el parte.",
  not_proposed:
    "Sin atribución al parte: el ciclo nació sin una propuesta adoptada.",
  unmeasured:
    "Atribución no medible: falta la identidad de una de las dos partes.",
  ambiguous: "Atribución ambigua: más de una propuesta reclama el mismo ciclo.",
};

/** Traduce el estado de atribución a una frase; un hueco se declara, no se disfraza. */
export const describeAttribution = (
  attribution: EstudioChainAttributionV1 | null | undefined,
): string => {
  if (!attribution || !attribution.state) {
    return "Sin dato de atribución en este parte.";
  }
  return (
    ATTRIBUTION_LABELS[attribution.state] ??
    `Atribución declarada: ${attribution.state}.`
  );
};

const statusHeadline = (value: EstudioDailyValueV1): SummarySection => {
  const status = String(value.status ?? "");
  if (status === "ok") {
    return {
      headline: "El parte propone una entrada.",
      detail: null,
      measurement: "COMPLETE",
    };
  }
  if (status === "no_signal") {
    return {
      headline: "El parte no propone entrada: no hay señal de apertura.",
      detail: value.reason ?? null,
      measurement: "COMPLETE",
    };
  }
  if (status === "no_plan") {
    return {
      headline: "Hay señal, pero el plan no dispara.",
      detail: value.reason ?? null,
      measurement: "COMPLETE",
    };
  }
  if (status === "error") {
    return {
      headline: "Este valor no se pudo medir.",
      detail: value.reason ?? null,
      measurement: "UNKNOWN",
    };
  }
  return {
    headline: "Sin estado declarado para este valor.",
    detail: null,
    measurement: "UNKNOWN",
  };
};

const proposalSection = (value: EstudioDailyValueV1): SummarySection => {
  const plan = value.plan;
  if (!plan || String(plan.status ?? "") !== "TRIGGERED") {
    return statusHeadline(value);
  }
  const direction = String(plan.direction ?? "").toUpperCase();
  const side =
    direction === "SHORT" || direction === "SELL" || direction === "BEAR"
      ? "venta"
      : "compra";
  return {
    headline: `Propone una ${side} en ${num(plan.entry)}.`,
    detail: `Stop ${num(plan.structuralStop)} · objetivo 1 ${num(plan.target1)} · objetivo 2 ${num(plan.target2)}`,
    measurement: "COMPLETE",
  };
};

const whySection = (value: EstudioDailyValueV1): SummarySection => {
  const opinion = value.opinion;
  const reasons = (opinion?.reasons ?? []).filter(Boolean);
  if (!opinion || (!opinion.stance && reasons.length === 0)) {
    return {
      headline: "El motivo no consta en este parte.",
      detail: null,
      measurement: "UNKNOWN",
    };
  }
  const stars =
    opinion.dictamenStars === null || opinion.dictamenStars === undefined
      ? null
      : opinion.dictamenStars;
  const stance = opinion.stance
    ? `Dictamen ${opinion.stance}`
    : "Dictamen sin postura";
  return {
    headline: stars === null ? stance : `${stance} · ${stars}★`,
    detail: reasons.length > 0 ? reasons.slice(0, 3).join(" · ") : null,
    measurement: reasons.length > 0 ? "COMPLETE" : "PARTIAL",
  };
};

const missingSection = (
  value: EstudioDailyValueV1,
  chain: ValueSummaryChainInput,
): SummarySection => {
  const status = String(value.status ?? "");
  if (status === "error") {
    return {
      headline: "Falta que el cálculo de este valor se pueda leer.",
      detail: value.reason ?? null,
      measurement: "UNKNOWN",
    };
  }
  if (status === "no_signal") {
    return {
      headline: "Falta una señal de apertura para poder planificar.",
      detail: value.reason ?? null,
      measurement: "COMPLETE",
    };
  }
  if (status === "no_plan") {
    const why = value.whyNot?.[0] ?? value.plan?.whyNot?.[0] ?? null;
    return {
      headline: "Falta que el plan supere sus condiciones de disparo.",
      detail: why,
      measurement: why === null ? "PARTIAL" : "COMPLETE",
    };
  }
  if (status !== "ok") {
    return {
      headline: "Sin estado declarado: no se puede decir qué falta.",
      detail: null,
      measurement: "UNKNOWN",
    };
  }
  const cycles = chain?.cycles ?? [];
  if (cycles.length === 0) {
    return {
      headline:
        "Falta que el motor AUTO adopte esta propuesta y la ejecute en PAPER.",
      detail:
        "El parte es una propuesta: no hay un ciclo durable de ejecución para este valor.",
      measurement: "COMPLETE",
    };
  }
  const closed = cycles.filter((cycle) => cycle.closed === true).length;
  return {
    headline: "Nada pendiente: el motor ya ejecutó esta propuesta.",
    detail: `${cycles.length} ciclo(s) durables · ${closed} cerrado(s).`,
    measurement: "COMPLETE",
  };
};

const validationSection = (
  validation: ValueSummaryValidationInput | null | undefined,
): SummarySection & { validated: boolean | null } => {
  const k = validation?.k ?? null;
  const target = validation?.target ?? null;
  const windowVerdict = validation?.windowVerdict ?? null;
  if (k === null && target === null && windowVerdict === null) {
    return {
      headline: "Validación estadística: no medida en este parte.",
      detail:
        "El parte diario no mide OOS: la validación se lee en su propia evidencia.",
      measurement: "UNKNOWN",
      validated: validation?.validated ?? null,
    };
  }
  const validated = validation?.validated ?? false;
  const kText = k === null ? "K no medido" : `K=${k}`;
  const targetText = target === null ? "" : `/${target}`;
  const windowText = windowVerdict ? ` · ventana ${windowVerdict}` : "";
  return {
    headline: `Validación estadística: ${
      validated ? "validada" : "no validada"
    } · ${kText}${targetText}${windowText}`,
    detail: validated
      ? null
      : "Una clasificación alta NO es una validación: son ejes distintos.",
    measurement: k === null || target === null ? "PARTIAL" : "COMPLETE",
    validated,
  };
};

const classificationSection = (
  value: EstudioDailyValueV1,
): SummarySection & {
  rank: number | null;
  runId: string | null;
  bar: string | null;
} => {
  const selector = value.selector;
  if (!selector || selector.measured !== true) {
    return {
      headline: "Clasificación del selector: no medida para este día.",
      detail: selector?.reason ?? null,
      measurement: "UNKNOWN",
      rank: null,
      runId: selector?.runId ?? null,
      bar: selector?.bar ?? null,
    };
  }
  if (selector.isWinner === true) {
    return {
      headline: `Clasificación del selector: #1 de la foto — la mejor puntuada (run ${selector.runId ?? "—"}, barra ${selector.bar ?? "—"}).`,
      detail:
        "Es una clasificación del ranking del día, NO una validación ni una promesa de rentabilidad.",
      measurement: "COMPLETE",
      rank: 1,
      runId: selector.runId ?? null,
      bar: selector.bar ?? null,
    };
  }
  if (selector.isWinner === false) {
    return {
      headline: `Clasificación del selector: no fue la primera de la foto (run ${selector.runId ?? "—"}).`,
      detail: "El ranking del día no es una validación.",
      measurement: "COMPLETE",
      rank: null,
      runId: selector.runId ?? null,
      bar: selector.bar ?? null,
    };
  }
  return {
    headline:
      "Clasificación del selector: foto presente sin veredicto de puesto.",
    detail: selector.runId ? `Foto ${selector.runId}` : null,
    measurement: "PARTIAL",
    rank: null,
    runId: selector.runId ?? null,
    bar: selector.bar ?? null,
  };
};

/** Construye el resumen de cuatro preguntas de UN valor del parte (función PURA). */
export const deriveValueSummary = (
  value: EstudioDailyValueV1,
  options?: {
    chain?: ValueSummaryChainInput;
    validation?: ValueSummaryValidationInput | null;
  },
): ValueSummary => {
  const chain = options?.chain ?? null;
  const attribution = chain?.cycles?.[0]?.attribution ?? null;
  return {
    proposal: proposalSection(value),
    why: whySection(value),
    missing: missingSection(value, chain),
    validation: validationSection(options?.validation),
    classification: classificationSection(value),
    technical: {
      instrumentId: value.instrumentId,
      status: String(value.status ?? ""),
      signalId: value.strategy?.signalId ?? null,
      planId: value.strategy?.planId ?? value.plan?.decisionId ?? null,
      selectorRunId: value.selector?.runId ?? null,
      asOfBarDate: value.asOfBarDate ?? null,
      cycleIds: (chain?.cycles ?? [])
        .map((cycle) => cycle.cycleId)
        .filter((id): id is string => typeof id === "string" && id.length > 0),
      attribution,
      attributionLabel: describeAttribution(attribution),
    },
  };
};
