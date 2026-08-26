/**
 * V1.18 — cambios relevantes en Evolución (solo deltas materializados).
 */

import type {
  JournalStudyDeltaFieldV1,
  JournalStudyDeltaV1,
} from "./decision-journal-study-delta.js";
import { mapJournalStudyDelta } from "./decision-journal-study-delta.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";

const RELEVANT_LABELS = new Set([
  "Opinión",
  "Fuerza",
  "Estado",
  "Régimen",
  "Stop",
  "Objetivo 1",
  "Plan operativo",
  "Invalidación",
  "Salud de tesis",
  "Vigencia",
]);

export type RelevantJournalDeltaV1 = JournalStudyDeltaV1 & {
  relevantFields: JournalStudyDeltaFieldV1[];
  hasRelevantChange: boolean;
  conclusion: string;
};

export function filterRelevantDeltaFields(
  fields: JournalStudyDeltaFieldV1[],
): JournalStudyDeltaFieldV1[] {
  return fields.filter((f) => RELEVANT_LABELS.has(f.label));
}

export function buildRelevantJournalDelta(
  current: DecisionJournalStudyViewV1,
  previous: DecisionJournalStudyViewV1 | null,
): RelevantJournalDeltaV1 {
  const base = mapJournalStudyDelta(previous, current);
  const relevantFields = filterRelevantDeltaFields(base.fields);
  const hasRelevantChange = relevantFields.length > 0;

  let conclusion = base.summary;
  if (base.isFirst) {
    conclusion = "Primera tesis registrada.";
  } else if (!hasRelevantChange) {
    conclusion = "Sin cambios relevantes en la tesis.";
  } else {
    const opinionChange = relevantFields.find((f) => f.label === "Opinión");
    const strengthChange = relevantFields.find((f) => f.label === "Fuerza");
    const planChange = relevantFields.find((f) => f.label === "Plan operativo");
    if (opinionChange) {
      conclusion = `La opinión pasó de ${opinionChange.before} a ${opinionChange.after}.`;
    } else if (strengthChange) {
      conclusion = `La fuerza pasó de ${strengthChange.before} a ${strengthChange.after}.`;
    } else if (planChange) {
      conclusion = `El plan operativo cambió: ${planChange.before} → ${planChange.after}.`;
    } else {
      conclusion = `${relevantFields.length} cambio(s) relevante(s) detectado(s).`;
    }
  }

  return {
    ...base,
    relevantFields,
    hasRelevantChange,
    conclusion,
  };
}

export type MesaDecisionAlertKindV1 =
  | "trigger_reached"
  | "stop_near"
  | "thesis_weak"
  | "tp1_reached"
  | "protection_discrepancy"
  | "data_stale"
  | "incident";

export type MesaDecisionAlertV1 = {
  kind: MesaDecisionAlertKindV1;
  symbol: string;
  message: string;
  severity: "info" | "warning" | "critical";
};

export function buildMesaDecisionAlerts(input: {
  positions?: ReadonlyArray<{
    symbol: string;
    lastPrice?: number | null;
    operational?: {
      currentStop?: number | null;
      target1?: number | null;
      unrealizedR?: number | null;
      exitPlan?: { suggestedAction?: string | null } | null;
    } | null;
  }>;
  studies?: ReadonlyArray<{
    instrumentId: string;
    symbol?: string | null;
    strength?: number | null;
    tradePlanStatus?: string | null;
  }>;
  dataStale?: boolean;
  incidentCount?: number;
  protectionDiscrepancies?: ReadonlyArray<{ symbol: string }>;
}): MesaDecisionAlertV1[] {
  const alerts: MesaDecisionAlertV1[] = [];

  if ((input.incidentCount ?? 0) > 0) {
    alerts.push({
      kind: "incident",
      symbol: "SISTEMA",
      message: "Incidente operativo activo — nuevas entradas bloqueadas",
      severity: "critical",
    });
  }

  if (input.dataStale) {
    alerts.push({
      kind: "data_stale",
      symbol: "SISTEMA",
      message: "Datos de mercado posiblemente retrasados",
      severity: "warning",
    });
  }

  for (const d of input.protectionDiscrepancies ?? []) {
    alerts.push({
      kind: "protection_discrepancy",
      symbol: d.symbol,
      message: "Discrepancia de protección — stop no confirmado",
      severity: "critical",
    });
  }

  for (const p of input.positions ?? []) {
    const op = p.operational;
    const price = p.lastPrice;
    const stop = op?.currentStop;
    if (price != null && stop != null && price > 0) {
      const distPct = ((price - stop) / price) * 100;
      if (distPct >= 0 && distPct < 2) {
        alerts.push({
          kind: "stop_near",
          symbol: p.symbol,
          message: `Stop a ${distPct.toFixed(1)}% del precio`,
          severity: "warning",
        });
      }
    }
    const t1 = op?.target1;
    if (price != null && t1 != null && price >= t1) {
      alerts.push({
        kind: "tp1_reached",
        symbol: p.symbol,
        message: "TP1 alcanzado o superado",
        severity: "info",
      });
    }
    if (op?.exitPlan?.suggestedAction === "protect") {
      alerts.push({
        kind: "protection_discrepancy",
        symbol: p.symbol,
        message: "Protección pendiente de confirmación",
        severity: "warning",
      });
    }
  }

  for (const s of input.studies ?? []) {
    if (s.strength != null && s.strength < 4) {
      alerts.push({
        kind: "thesis_weak",
        symbol: s.symbol ?? s.instrumentId,
        message: `Fuerza baja (${s.strength.toFixed(1)})`,
        severity: "warning",
      });
    }
    if (s.tradePlanStatus === "TRIGGERED") {
      alerts.push({
        kind: "trigger_reached",
        symbol: s.symbol ?? s.instrumentId,
        message: "Trigger alcanzado — revisar propuesta",
        severity: "info",
      });
    }
  }

  return alerts;
}
