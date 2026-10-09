/**
 * S4-agregador-evidencia — read-model PURO de las cuatro capas de evidencia DÍA-D
 * (PROJECT_PREMISES §5.2). Compone VENTANA + RECONCILIACIÓN + EVIDENCIA OOS + EVIDENCIA PAPER
 * y concluye SIEMPRE `NO_CONFIRMED`: la capa PAPER está reservada y hoy no se emite.
 *
 * Invariantes (falsables):
 * - **Nunca se emite la confirmación reservada.** `verdict` es un tipo literal
 *   `"NO_CONFIRMED"`, el input no admite la capa PAPER y no existe ninguna rama que la mida.
 * - **Ninguna capa promociona a la siguiente** (`READY`, `MATCH` y `OOS_SUPPORTED` NO confirman).
 *   El agregado reporta la capa más fuerte medida y lo declara con su nota de no promoción.
 * - **`UNKNOWN ≠ 0`.** Un hueco es la variante `gap` con el rótulo de `absent-data`
 *   («Sin dato todavía»); jamás se colapsa a 0 ni a un veredicto afirmado.
 * - **El rollup OOS exige los tres recuentos medidos.** Un contador ausente (o evidencia sin
 *   medir) no se interpreta como 0: la capa se declara hueco en vez de afirmar `OOS_SUPPORTED`.
 *
 * No toca motor, contrato HTTP ni almacenamiento: es UI pura (`Δ motor = 0`).
 *
 * @see docs/PROJECT_PREMISES.md §5.2 (cuatro capas · no equivalencias)
 * @see apps/web/src/features/auto/auto-no-trade-explanation.ts (precedente de read-model puro)
 */

import { absentDataLabel, type AbsentDataKind } from "@/components/absent-data";
import {
  DIA_D_EVIDENCE_GLOBAL_VERDICT_LABEL,
  DIA_D_EVIDENCE_LAYER_COPY,
  DIA_D_EVIDENCE_NON_PROMOTION_NOTE,
  DIA_D_EVIDENCE_OOS_EMPTY_REASON,
  DIA_D_EVIDENCE_OOS_INSUFFICIENT_COUNTERS_REASON,
  DIA_D_EVIDENCE_OOS_NOT_MEASURED_REASON,
  DIA_D_EVIDENCE_OPEN_SUBVIEW_REASON,
  DIA_D_EVIDENCE_PAPER_REASON,
  OOS_VERDICT_LABELS,
  RECONCILIATION_VERDICT_LABELS,
  WINDOW_VERDICT_LABELS,
} from "./dia-d-evidence-aggregate-labels";

/** Capas semánticas, de la más débil a la más fuerte. `paper` es hueco estructural hoy. */
export type DiaDEvidenceLayerId = "window" | "reconciliation" | "oos" | "paper";

/** Capas que hoy pueden llegar a medirse (PAPER queda reservada). */
export type DiaDMeasurableLayerId = Exclude<DiaDEvidenceLayerId, "paper">;

export type DiaDEvidenceWindowFacts = {
  loaded: boolean;
  verdict: string | null;
  days: number | null;
  episodes: number | null;
  cycles: number | null;
};

export type DiaDEvidenceReconciliationFacts = {
  loaded: boolean;
  verdict: string | null;
  match: number | null;
  divergent: number | null;
  notMeasured: number | null;
};

export type DiaDEvidenceOosFacts = {
  loaded: boolean;
  oosSupported: number | null;
  mixed: number | null;
  refuted: number | null;
  notMeasured: number | null;
};

/**
 * Entradas normalizadas. Deliberadamente NO existe campo `paper`: la confirmación PAPER es un
 * hueco por contrato, no una fuente que este módulo pueda medir.
 */
export type DiaDEvidenceAggregateInput = {
  window: DiaDEvidenceWindowFacts | null;
  reconciliation: DiaDEvidenceReconciliationFacts | null;
  oos: DiaDEvidenceOosFacts | null;
};

type DiaDEvidenceLayerBaseV1 = {
  id: DiaDEvidenceLayerId;
  title: string;
  honestyNote: string;
  sourceLabel: string;
  /** Medición humanizada de primer nivel (o `null` si no aplica). */
  measurement: string | null;
  /** Medición cruda de nivel 3 (solo dentro del detalle técnico). */
  measurementToken: string | null;
  reason: string | null;
};

export type DiaDEvidenceMeasuredLayerV1 = DiaDEvidenceLayerBaseV1 & {
  state: "measured";
  /** Token crudo de la capa (nivel 3). Nunca se pinta en primer nivel. */
  verdictToken: string;
  /** Rótulo humanizado de primer nivel. */
  verdictLabel: string;
};

export type DiaDEvidenceGapLayerV1 = DiaDEvidenceLayerBaseV1 & {
  state: "gap";
  gap: AbsentDataKind;
  gapLabel: string;
};

export type DiaDEvidenceLayerV1 =
  | DiaDEvidenceMeasuredLayerV1
  | DiaDEvidenceGapLayerV1;

export type DiaDEvidenceAggregateV1 = {
  schemaVersion: "dia_d_evidence_aggregate_v1";
  /** Tipo LITERAL: es el único veredicto que este constructor puede devolver. */
  verdict: "NO_CONFIRMED";
  verdictLabel: string;
  summary: string;
  /** Orden fijo: window · reconciliation · oos · paper. */
  layers: readonly [
    DiaDEvidenceLayerV1,
    DiaDEvidenceLayerV1,
    DiaDEvidenceLayerV1,
    DiaDEvidenceLayerV1,
  ];
  maxLayerReached: DiaDMeasurableLayerId | null;
  maxLayerReachedLabel: string;
  confirmationBlockedReason: string;
  gapLayerIds: readonly DiaDEvidenceLayerId[];
};

/** Eco máquina-legible de §5.2: alcanzar una capa no confirma la siguiente. */
export const AGGREGATE_NON_PROMOTION_NOTE = DIA_D_EVIDENCE_NON_PROMOTION_NOTE;

/** Número medido o `null`; nunca colapsa ausencia a 0. */
function num(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function part(label: string, value: number | null): string {
  return `${label} ${value ?? absentDataLabel()}`;
}

function baseProps(id: DiaDEvidenceLayerId) {
  const copy = DIA_D_EVIDENCE_LAYER_COPY[id];
  return {
    id,
    title: copy.title,
    honestyNote: copy.honestyNote,
    sourceLabel: copy.sourceLabel,
  };
}

function gapLayer(
  id: DiaDEvidenceLayerId,
  reason: string,
  measurement: string | null = null,
): DiaDEvidenceGapLayerV1 {
  return {
    ...baseProps(id),
    state: "gap",
    measurement,
    measurementToken: null,
    reason,
    gap: "not_measured",
    gapLabel: absentDataLabel(),
  };
}

function measuredLayer(
  id: DiaDEvidenceLayerId,
  verdictToken: string,
  verdictLabel: string,
  measurement: string | null,
  measurementToken: string | null = null,
): DiaDEvidenceMeasuredLayerV1 {
  return {
    ...baseProps(id),
    state: "measured",
    measurement,
    measurementToken,
    reason: null,
    verdictToken,
    verdictLabel,
  };
}

function buildWindowLayer(
  facts: DiaDEvidenceWindowFacts | null,
): DiaDEvidenceLayerV1 {
  const token = facts?.verdict ?? null;
  if (!facts || !facts.loaded || !token || !(token in WINDOW_VERDICT_LABELS)) {
    return gapLayer(
      "window",
      facts
        ? "La ventana todavía no declara veredicto."
        : DIA_D_EVIDENCE_OPEN_SUBVIEW_REASON,
    );
  }
  const measurement = [
    part("días", num(facts.days)),
    part("episodios", num(facts.episodes)),
    part("ciclos", num(facts.cycles)),
  ].join(" · ");
  return measuredLayer(
    "window",
    token,
    WINDOW_VERDICT_LABELS[token]!,
    measurement,
    token,
  );
}

function buildReconciliationLayer(
  facts: DiaDEvidenceReconciliationFacts | null,
): DiaDEvidenceLayerV1 {
  const token = facts?.verdict ?? null;
  if (!facts || !facts.loaded || !token) {
    return gapLayer(
      "reconciliation",
      facts
        ? "El contraste declarado frente a ejecutado todavía no se ha medido."
        : DIA_D_EVIDENCE_OPEN_SUBVIEW_REASON,
    );
  }
  if (!(token in RECONCILIATION_VERDICT_LABELS)) {
    return gapLayer(
      "reconciliation",
      "El contraste declarado frente a ejecutado todavía no se ha medido.",
    );
  }
  const measurement = [
    part("coincide", num(facts.match)),
    part("discrepa", num(facts.divergent)),
    part("sin medir", num(facts.notMeasured)),
  ].join(" · ");
  return measuredLayer(
    "reconciliation",
    token,
    RECONCILIATION_VERDICT_LABELS[token]!,
    measurement,
    token,
  );
}

function buildOosLayer(
  facts: DiaDEvidenceOosFacts | null,
): DiaDEvidenceLayerV1 {
  if (!facts || !facts.loaded) {
    return gapLayer(
      "oos",
      facts
        ? DIA_D_EVIDENCE_OOS_EMPTY_REASON
        : DIA_D_EVIDENCE_OPEN_SUBVIEW_REASON,
    );
  }
  const supported = num(facts.oosSupported);
  const mixed = num(facts.mixed);
  const refuted = num(facts.refuted);
  const notMeasured = num(facts.notMeasured);
  const measurement = [
    part("soportados", supported),
    part("mixtos", mixed),
    part("refutados", refuted),
    part("sin medir", notMeasured),
  ].join(" · ");

  // `UNKNOWN ≠ 0`: para afirmar el veredicto OOS hacen falta los tres recuentos. Un contador
  // ausente NO se interpreta como 0; sin él no se puede descartar una contradicción, así que la
  // capa se declara hueco (conservando la muestra parcial) en vez de un veredicto afirmado.
  if (supported === null || mixed === null || refuted === null) {
    return gapLayer(
      "oos",
      DIA_D_EVIDENCE_OOS_INSUFFICIENT_COUNTERS_REASON,
      measurement,
    );
  }
  // Un instrumento sin medir podría ser una refutación: mientras quede muestra sin medir, el
  // veredicto no se afirma.
  if ((notMeasured ?? 0) > 0) {
    return gapLayer("oos", DIA_D_EVIDENCE_OOS_NOT_MEASURED_REASON, measurement);
  }
  if (supported + mixed + refuted <= 0) {
    return gapLayer("oos", DIA_D_EVIDENCE_OOS_EMPTY_REASON, measurement);
  }
  // Rollup con contradicción declarada: soportados y refutados a la vez ⇒ MIXED (la evidencia
  // se contradice); sólo refutados ⇒ REFUTED; sólo mixtos ⇒ MIXED; si no, OOS_SUPPORTED.
  const token =
    refuted > 0 && supported > 0
      ? "MIXED"
      : refuted > 0
        ? "REFUTED"
        : mixed > 0
          ? "MIXED"
          : "OOS_SUPPORTED";
  return measuredLayer(
    "oos",
    token,
    OOS_VERDICT_LABELS[token]!,
    measurement,
    token,
  );
}

/** La capa PAPER es, por contrato, un hueco constante: no recibe hechos ni tiene rama. */
function buildPaperLayer(): DiaDEvidenceGapLayerV1 {
  return gapLayer("paper", DIA_D_EVIDENCE_PAPER_REASON);
}

export function buildDiaDEvidenceAggregate(
  input: DiaDEvidenceAggregateInput,
): DiaDEvidenceAggregateV1 {
  const layers: readonly [
    DiaDEvidenceLayerV1,
    DiaDEvidenceLayerV1,
    DiaDEvidenceLayerV1,
    DiaDEvidenceLayerV1,
  ] = [
    buildWindowLayer(input.window),
    buildReconciliationLayer(input.reconciliation),
    buildOosLayer(input.oos),
    buildPaperLayer(),
  ];

  const order: readonly DiaDMeasurableLayerId[] = [
    "window",
    "reconciliation",
    "oos",
  ];
  let maxLayerReached: DiaDMeasurableLayerId | null = null;
  for (const id of order) {
    const layer = layers.find((item) => item.id === id);
    if (layer && layer.state === "measured") maxLayerReached = id;
  }

  const measuredTitles = layers
    .filter((layer) => layer.state === "measured")
    .map((layer) => layer.title);
  const headline =
    measuredTitles.length > 0
      ? `Capas medidas: ${measuredTitles.join(" · ")}.`
      : "Todavía no hay ninguna capa medida.";

  const strongest = maxLayerReached
    ? layers.find((layer) => layer.id === maxLayerReached)
    : null;

  return {
    schemaVersion: "dia_d_evidence_aggregate_v1",
    verdict: "NO_CONFIRMED",
    verdictLabel: DIA_D_EVIDENCE_GLOBAL_VERDICT_LABEL,
    summary: `${headline} ${AGGREGATE_NON_PROMOTION_NOTE}`
      .replace(/\s+/g, " ")
      .trim(),
    layers,
    maxLayerReached,
    maxLayerReachedLabel: strongest ? strongest.title : absentDataLabel(),
    confirmationBlockedReason: DIA_D_EVIDENCE_PAPER_REASON,
    gapLayerIds: layers
      .filter((layer) => layer.state === "gap")
      .map((layer) => layer.id),
  };
}
