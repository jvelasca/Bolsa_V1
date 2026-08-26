/**
 * ADR-036 Evolución — diff honesto entre snapshots propose consecutivos.
 * Solo lectura; no inventa causas fuera del ViewModel.
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_STATUS_LABELS,
  type JournalStudyOpinion,
  type JournalStudyUserStatus,
} from "./decision-journal-study.js";

export const FIRST_THESIS_COPY = "Primera tesis registrada." as const;
export const EMPTY_DELTA_COPY =
  "Sin cambios materializados en el snapshot." as const;

export type JournalStudyDeltaBucket = "motor" | "plan" | "health";

export const JOURNAL_STUDY_DELTA_BUCKET_LABELS: Record<
  JournalStudyDeltaBucket,
  string
> = {
  motor: "Análisis IA",
  plan: "Plan",
  health: "Salud de tesis",
};

export type JournalStudyDeltaFieldV1 = {
  bucket: JournalStudyDeltaBucket;
  label: string;
  before: string;
  after: string;
};

export type JournalStudyDeltaV1 = {
  prevSessionId: string | null;
  nextSessionId: string;
  isFirst: boolean;
  isEmpty: boolean;
  summary: string;
  fields: JournalStudyDeltaFieldV1[];
};

export type DecisionJournalStudyHistoryV1 = {
  accountId: string;
  instrumentId: string;
  symbol: string | null;
  name: string | null;
  studies: DecisionJournalStudyViewV1[];
  total: number;
  limit: number;
  offset: number;
};

export type DecisionJournalStudyHistoryResponseV1 = {
  data: DecisionJournalStudyHistoryV1;
};

function labelOpinion(value: string | null): string {
  if (!value) return "—";
  return JOURNAL_STUDY_OPINION_LABELS[value as JournalStudyOpinion] ?? value;
}

function labelStatus(value: string): string {
  return JOURNAL_STUDY_STATUS_LABELS[value as JournalStudyUserStatus] ?? value;
}

function fmtNum(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function fmtStrength(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(1);
}

function pushField(
  fields: JournalStudyDeltaFieldV1[],
  field: JournalStudyDeltaFieldV1,
): void {
  if (field.before === field.after) return;
  fields.push(field);
}

function diffInvalidation(
  prev: string[],
  next: string[],
): JournalStudyDeltaFieldV1 | null {
  const prevKey = prev.join("|");
  const nextKey = next.join("|");
  if (prevKey === nextKey) return null;
  return {
    bucket: "health",
    label: "Invalidación",
    before: prev.length > 0 ? prev.join(" · ") : "—",
    after: next.length > 0 ? next.join(" · ") : "—",
  };
}

/** Diff N vs N-1 (prev = older, next = newer). */
export function mapJournalStudyDelta(
  prev: DecisionJournalStudyViewV1 | null,
  next: DecisionJournalStudyViewV1,
): JournalStudyDeltaV1 {
  if (prev == null) {
    return {
      prevSessionId: null,
      nextSessionId: next.sessionId,
      isFirst: true,
      isEmpty: true,
      summary: FIRST_THESIS_COPY,
      fields: [],
    };
  }

  const fields: JournalStudyDeltaFieldV1[] = [];

  pushField(fields, {
    bucket: "motor",
    label: "Opinión",
    before: labelOpinion(prev.opinion),
    after: labelOpinion(next.opinion),
  });
  pushField(fields, {
    bucket: "motor",
    label: "Fuerza",
    before: fmtStrength(prev.strength),
    after: fmtStrength(next.strength),
  });
  pushField(fields, {
    bucket: "motor",
    label: "Estado",
    before: labelStatus(prev.status),
    after: labelStatus(next.status),
  });

  if (prev.hasOperationalPlan || next.hasOperationalPlan) {
    pushField(fields, {
      bucket: "plan",
      label: "Entrada",
      before: prev.hasOperationalPlan ? fmtNum(prev.entry) : "—",
      after: next.hasOperationalPlan ? fmtNum(next.entry) : "—",
    });
    pushField(fields, {
      bucket: "plan",
      label: "Stop",
      before: prev.hasOperationalPlan ? fmtNum(prev.stop) : "—",
      after: next.hasOperationalPlan ? fmtNum(next.stop) : "—",
    });
    pushField(fields, {
      bucket: "plan",
      label: "Objetivo 1",
      before: prev.hasOperationalPlan ? fmtNum(prev.target1) : "—",
      after: next.hasOperationalPlan ? fmtNum(next.target1) : "—",
    });
  } else if (prev.hasOperationalPlan !== next.hasOperationalPlan) {
    pushField(fields, {
      bucket: "plan",
      label: "Plan operativo",
      before: prev.hasOperationalPlan ? "Sí" : "No",
      after: next.hasOperationalPlan ? "Sí" : "No",
    });
  }

  const invalidation = diffInvalidation(prev.invalidation, next.invalidation);
  if (invalidation) fields.push(invalidation);

  const isEmpty = fields.length === 0;

  return {
    prevSessionId: prev.sessionId,
    nextSessionId: next.sessionId,
    isFirst: false,
    isEmpty,
    summary: isEmpty ? EMPTY_DELTA_COPY : `${fields.length} cambio(s)`,
    fields,
  };
}

export type JournalStudySparkPointV1 = {
  studiedAt: string;
  strength: number | null;
  opinion: JournalStudyOpinion | null;
};

/** Puntos para sparkline (orden cronológico ascendente). */
export function buildJournalStudySparklinePoints(
  studies: DecisionJournalStudyViewV1[],
): JournalStudySparkPointV1[] {
  return [...studies]
    .sort(
      (a, b) =>
        new Date(a.studiedAt).getTime() - new Date(b.studiedAt).getTime(),
    )
    .map((study) => ({
      studiedAt: study.studiedAt,
      strength: study.strength,
      opinion: study.opinion,
    }));
}

export function buildJournalStudySparklinePath(
  points: JournalStudySparkPointV1[],
  width: number,
  height: number,
  pad = 4,
): { line: string; dots: Array<{ x: number; y: number }> } {
  if (!points.length) return { line: "", dots: [] };
  const w = Math.max(1, width - pad * 2);
  const h = Math.max(1, height - pad * 2);
  const strengths = points.map((p) =>
    p.strength != null && Number.isFinite(p.strength) ? p.strength : 0,
  );
  const max = Math.max(10, ...strengths);
  const min = 0;
  const n = points.length;
  const dots = points.map((p, i) => {
    const x = pad + (n === 1 ? w / 2 : (i / (n - 1)) * w);
    const value =
      p.strength != null && Number.isFinite(p.strength) ? p.strength : min;
    const y = pad + h - ((value - min) / (max - min || 1)) * h;
    return { x, y };
  });
  const line = dots
    .map((d, i) => `${i === 0 ? "M" : "L"}${d.x.toFixed(1)},${d.y.toFixed(1)}`)
    .join(" ");
  return { line, dots };
}
