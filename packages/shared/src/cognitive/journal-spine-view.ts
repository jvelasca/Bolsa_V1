/**
 * V2.27 — Journal spine + RESULTADO metrics (display-only).
 * SoT = decision_sessions · TradeStory stamps · optional PositionState.
 * No second ledger. returnPct ≠ Final R. Trailing hint ≠ TRAILING.
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  inferMfeMaeSource,
  type MfeMaeSourceV1,
  type MfeMaeStatusV1,
  type MfeMaeV1,
  type MfeMaeWhyV1,
} from "./mfe-mae.js";
import type { PositionStateV1, PositionStatusV1 } from "./position-state.js";
import type { SessionOutcomeVerdict } from "./decision-session.js";
import type {
  TradeStoryEventKindV1,
  TradeStoryEventV1,
  TradeStoryV1,
} from "./trade-story.js";

export type JournalSpineStepIdV1 =
  | "tesis"
  | "decision"
  | "entrada"
  | "riesgo"
  | "t1"
  | "t2"
  | "trailing"
  | "exit"
  | "resultado";

export type JournalSpineStepStateV1 =
  | "done"
  | "current"
  | "pending"
  | "unknown";

export type JournalSpineStepV1 = {
  id: JournalSpineStepIdV1;
  label: string;
  state: JournalSpineStepStateV1;
  asOf: string | null;
  detail: string | null;
};

export type JournalResultMetricsV1 = {
  /** Study/plan Initial Risk in R (session SoT). */
  initialRiskR: number | null;
  /** Position realized R — only when PositionState supplies it. */
  realizedR: number | null;
  /**
   * Alias of realizedR when position is CLOSED.
   * Never SessionOutcome.returnPct.
   */
  finalR: number | null;
  /** Session runtime.mfeMae eco (advisory ≥0). Prefer over signed mark peaks. */
  mfeMae: MfeMaeV1 | null;
  /** Thesis learning verdict — not Final R. */
  learningVerdict: SessionOutcomeVerdict | null;
};

export type JournalSpineViewV1 = {
  steps: JournalSpineStepV1[];
  result: JournalResultMetricsV1;
};

export const JOURNAL_SPINE_STEP_ORDER: readonly JournalSpineStepIdV1[] = [
  "tesis",
  "decision",
  "entrada",
  "riesgo",
  "t1",
  "t2",
  "trailing",
  "exit",
  "resultado",
] as const;

export const JOURNAL_SPINE_STEP_LABELS: Record<JournalSpineStepIdV1, string> = {
  tesis: "TESIS",
  decision: "DECISIÓN",
  entrada: "ENTRADA",
  riesgo: "RIESGO",
  t1: "T1",
  t2: "T2",
  trailing: "TRAILING",
  exit: "EXIT",
  resultado: "RESULTADO",
};

const MFE_STATUSES = new Set<MfeMaeStatusV1>([
  "none",
  "observe",
  "favorable",
  "adverse",
]);
const MFE_WHYS = new Set<MfeMaeWhyV1>([
  "peak_from_bars",
  "close_proxy",
  "mae_ge_1r",
  "mfe_ge_1_5r",
  "missing_inputs",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === "object" && !Array.isArray(value);
}

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/** Fail-soft wire parse — same shape as Hoy `asMfeMae`. */
export function parseMfeMaeWire(value: unknown): MfeMaeV1 | null {
  if (!isRecord(value)) return null;
  const status = value.status;
  if (
    typeof status !== "string" ||
    !MFE_STATUSES.has(status as MfeMaeStatusV1)
  ) {
    return null;
  }
  const whyRaw = value.why;
  const why: MfeMaeWhyV1[] = Array.isArray(whyRaw)
    ? whyRaw.filter(
        (code): code is MfeMaeWhyV1 =>
          typeof code === "string" && MFE_WHYS.has(code as MfeMaeWhyV1),
      )
    : [];
  const numOrNull = (v: unknown): number | null =>
    typeof v === "number" && Number.isFinite(v) ? v : null;
  const source: MfeMaeSourceV1 = inferMfeMaeSource(why, value.source);
  const maeR = numOrNull(value.maeR);
  return {
    status: status as MfeMaeStatusV1,
    mfeR: numOrNull(value.mfeR),
    // Advisory display: magnitude ≥0 (do not pass signed mark mins through).
    maeR: maeR != null ? Math.abs(maeR) : null,
    currentR: numOrNull(value.currentR),
    why,
    source,
  };
}

/** Copy reference aligned with Hoy `hoy-mfe-mae` / Excursión. */
export function formatJournalMfeMaeLine(metrics: MfeMaeV1): string {
  const parts: string[] = [];
  if (metrics.mfeR != null) parts.push(`MFE ${metrics.mfeR}R`);
  if (metrics.maeR != null) parts.push(`MAE ${metrics.maeR}R`);
  if (metrics.status !== "observe" && metrics.status !== "none") {
    parts.push(metrics.status);
  }
  if (metrics.source === "close_proxy") parts.push("proxy");
  return parts.length > 0 ? parts.join(" · ") : "—";
}

export type BuildJournalSpineViewInputV1 = {
  study: Pick<
    DecisionJournalStudyViewV1,
    | "studiedAt"
    | "sessionId"
    | "decisionId"
    | "status"
    | "action"
    | "decisionSummary"
    | "initialRiskR"
    | "riskAmount"
    | "mfeMae"
    | "learningVerdict"
  >;
  tradeStory?: TradeStoryV1 | null;
  /** Only when true PositionState is available — never invent from thin DTO. */
  positionState?: Pick<
    PositionStateV1,
    "realizedR" | "status" | "initialRisk"
  > | null;
};

type Evidence = {
  asOf: string | null;
  detail: string | null;
  known: boolean;
};

function firstEvent(
  events: readonly TradeStoryEventV1[],
  kinds: readonly TradeStoryEventKindV1[],
): TradeStoryEventV1 | null {
  for (const kind of kinds) {
    const hit = events.find((e) => e.kind === kind);
    if (hit) return hit;
  }
  return null;
}

function collectEvidence(
  input: BuildJournalSpineViewInputV1,
): Record<JournalSpineStepIdV1, Evidence> {
  const study = input.study;
  const events = input.tradeStory?.events ?? [];
  const empty: Evidence = { asOf: null, detail: null, known: false };

  const estudio = firstEvent(events, ["estudio"]);
  const tesis: Evidence =
    estudio != null
      ? { asOf: estudio.asOf, detail: null, known: true }
      : study.studiedAt
        ? { asOf: study.studiedAt, detail: null, known: true }
        : empty;

  const decisionEv = firstEvent(events, ["propuesta", "confirmacion"]);
  const decision: Evidence =
    decisionEv != null
      ? {
          asOf: decisionEv.asOf,
          detail: decisionEv.label,
          known: true,
        }
      : study.action != null || study.decisionSummary != null
        ? {
            asOf: study.studiedAt ?? null,
            detail: study.action ?? null,
            known: true,
          }
        : empty;

  const fillEv = firstEvent(events, ["fill", "fill_partial"]);
  const entrada: Evidence =
    fillEv != null
      ? { asOf: fillEv.asOf, detail: fillEv.label, known: true }
      : empty;

  const riesgo: Evidence =
    entrada.known && (finite(study.initialRiskR) || finite(study.riskAmount))
      ? {
          asOf: entrada.asOf,
          detail: finite(study.initialRiskR)
            ? `Riesgo inicial ${study.initialRiskR}R`
            : null,
          known: true,
        }
      : empty;

  const t1Ev = firstEvent(events, ["t1"]);
  const t1: Evidence =
    t1Ev != null
      ? { asOf: t1Ev.asOf, detail: t1Ev.detail ?? null, known: true }
      : empty;

  const t2Ev = firstEvent(events, ["t2"]);
  const t2: Evidence =
    t2Ev != null
      ? { asOf: t2Ev.asOf, detail: t2Ev.detail ?? null, known: true }
      : empty;

  // trailing_applied only — never invent from hint / plan geometry.
  const trailEv = firstEvent(events, ["trailing_applied"]);
  const trailing: Evidence =
    trailEv != null
      ? { asOf: trailEv.asOf, detail: trailEv.detail ?? null, known: true }
      : empty;

  const cierreEv = firstEvent(events, ["cierre"]);
  const closedByStatus = study.status === "closed";
  const exit: Evidence =
    cierreEv != null
      ? { asOf: cierreEv.asOf, detail: null, known: true }
      : closedByStatus
        ? { asOf: null, detail: null, known: true }
        : empty;

  const resultado: Evidence = exit.known
    ? { asOf: exit.asOf, detail: null, known: true }
    : empty;

  return {
    tesis,
    decision,
    entrada,
    riesgo,
    t1,
    t2,
    trailing,
    exit,
    resultado,
  };
}

function assignStates(
  evidence: Record<JournalSpineStepIdV1, Evidence>,
): JournalSpineStepV1[] {
  let lastKnownIdx = -1;
  for (let i = 0; i < JOURNAL_SPINE_STEP_ORDER.length; i++) {
    if (evidence[JOURNAL_SPINE_STEP_ORDER[i]!].known) lastKnownIdx = i;
  }

  // Contiguous known prefix length (from start).
  let contiguousEnd = -1;
  for (let i = 0; i < JOURNAL_SPINE_STEP_ORDER.length; i++) {
    if (evidence[JOURNAL_SPINE_STEP_ORDER[i]!].known) contiguousEnd = i;
    else break;
  }

  const closed = evidence.resultado.known;

  return JOURNAL_SPINE_STEP_ORDER.map((id, i) => {
    const ev = evidence[id];
    let state: JournalSpineStepStateV1;

    if (ev.known) {
      if (closed) {
        state = id === "resultado" ? "current" : "done";
      } else if (i === lastKnownIdx) {
        state = "current";
      } else {
        state = "done";
      }
    } else if (i < lastKnownIdx) {
      // Stamp exists later but this step has no evidence — honesty gap.
      state = "unknown";
    } else if (i === contiguousEnd + 1 && lastKnownIdx === contiguousEnd) {
      state = "pending";
    } else {
      state = "pending";
    }

    return {
      id,
      label: JOURNAL_SPINE_STEP_LABELS[id],
      state,
      asOf: ev.asOf,
      detail: ev.detail,
    };
  });
}

function buildResultMetrics(
  input: BuildJournalSpineViewInputV1,
): JournalResultMetricsV1 {
  const study = input.study;
  const ps = input.positionState ?? null;

  const initialRiskR = finite(study.initialRiskR) ? study.initialRiskR : null;

  // Only trust PositionState.realizedR — never invent from thin DTO / returnPct.
  const realizedR = ps != null && finite(ps.realizedR) ? ps.realizedR : null;

  const closed: boolean =
    ps?.status === ("CLOSED" satisfies PositionStatusV1) ||
    study.status === "closed";

  const finalR = closed && realizedR != null ? realizedR : null;

  const mfeMae = study.mfeMae != null ? parseMfeMaeWire(study.mfeMae) : null;

  const learningVerdict =
    study.learningVerdict === "hit" ||
    study.learningVerdict === "miss" ||
    study.learningVerdict === "neutral" ||
    study.learningVerdict === "invalid" ||
    study.learningVerdict === "skipped"
      ? study.learningVerdict
      : null;

  return {
    initialRiskR,
    realizedR,
    finalR,
    mfeMae:
      mfeMae && mfeMae.status !== "none"
        ? mfeMae
        : mfeMae?.mfeR != null || mfeMae?.maeR != null
          ? mfeMae
          : null,
    learningVerdict,
  };
}

/**
 * Product spine TESIS→…→RESULTADO from TradeStory stamps + study SoT.
 * Plan geometry alone never marks T1/T2/TRAILING done.
 */
export function buildJournalSpineView(
  input: BuildJournalSpineViewInputV1,
): JournalSpineViewV1 {
  const evidence = collectEvidence(input);
  return {
    steps: assignStates(evidence),
    result: buildResultMetrics(input),
  };
}
