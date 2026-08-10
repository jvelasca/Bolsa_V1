/**
 * Reconciliación DÍA D — F-D#1 vs F-hoy#1 + calidad OOS (ADR-021).
 */

import type { InstrumentStrategyTopSlotV1 } from "@bolsa/shared";
import type { DiaDEvidenceBand } from "@/features/trading/dia-d-session-evidence";

export type DiaDReconciliationCode =
  | "SAME_CONFIRMED"
  | "SAME_FAILED"
  | "SAME_MIXED"
  | "DRIFT_BETTER"
  | "DRIFT_WORSE"
  | "INCONCLUSIVE";

export type DiaDIdentityKind =
  | "same_id"
  | "same_family"
  | "different"
  | "unknown";

export const DIA_D_RECONCILIATION_LABELS: Record<
  DiaDReconciliationCode,
  string
> = {
  SAME_CONFIRMED: "Misma operativa · confirmada en D→hoy",
  SAME_FAILED: "Misma operativa · mal resultado D→hoy",
  SAME_MIXED: "Misma operativa · resultado mixto",
  DRIFT_BETTER: "Distinta a F-hoy · buena en D→hoy (revisar Finalistas)",
  DRIFT_WORSE: "Distinta a F-hoy · mala en D→hoy",
  INCONCLUSIVE: "Inconcluso (datos / sin F-hoy)",
};

/** Métricas OOS D→hoy del contrafactual F-hoy#1 (misma ventana que V). */
export type DiaDCounterfactualOos = {
  returnPct: number | null;
  tradeCount: number | null;
  maxDrawdownPct: number | null;
  /** return F-D#1 − return F-hoy#1 (pp). */
  deltaReturnPp: number | null;
  status: "ready" | "skipped_same" | "pending" | "error" | "unavailable";
  note: string | null;
};

export type DiaDReconciliationInput = {
  experimentSlot: Pick<
    InstrumentStrategyTopSlotV1,
    "strategyDefinitionId" | "label" | "strategyType"
  > | null;
  productionSlot: Pick<
    InstrumentStrategyTopSlotV1,
    "strategyDefinitionId" | "label" | "strategyType"
  > | null;
  evidenceBand: DiaDEvidenceBand | null;
  oosReturnPct?: number | null;
  /** Contrafactual opcional (v1.1 ADR-021). */
  counterfactual?: DiaDCounterfactualOos | null;
};

export type DiaDReconciliationResult = {
  schemaVersion: "dia_d_reconciliation_v1";
  code: DiaDReconciliationCode;
  identity: DiaDIdentityKind;
  label: string;
  summary: string;
  experimentLabel: string | null;
  productionLabel: string | null;
  evidenceBand: DiaDEvidenceBand | null;
  oosReturnPct: number | null;
  counterfactual: DiaDCounterfactualOos | null;
};

export function buildCounterfactualOos(opts: {
  experimentReturnPct: number | null | undefined;
  productionReturnPct: number | null | undefined;
  productionTradeCount?: number | null;
  productionMaxDrawdownPct?: number | null;
  identity: DiaDIdentityKind;
  status?: DiaDCounterfactualOos["status"];
  note?: string | null;
}): DiaDCounterfactualOos {
  if (
    opts.status === "unavailable" ||
    opts.status === "error" ||
    opts.status === "pending"
  ) {
    return {
      returnPct: opts.productionReturnPct ?? null,
      tradeCount: opts.productionTradeCount ?? null,
      maxDrawdownPct: opts.productionMaxDrawdownPct ?? null,
      deltaReturnPp: null,
      status: opts.status,
      note: opts.note ?? null,
    };
  }
  if (opts.identity === "same_id") {
    return {
      returnPct: opts.productionReturnPct ?? null,
      tradeCount: opts.productionTradeCount ?? null,
      maxDrawdownPct: opts.productionMaxDrawdownPct ?? null,
      deltaReturnPp: 0,
      status: "skipped_same",
      note: opts.note ?? "F-hoy#1 = F-D#1: sin contrafactual aparte",
    };
  }
  const exp = opts.experimentReturnPct;
  const prod = opts.productionReturnPct;
  const delta =
    exp != null && prod != null && Number.isFinite(exp) && Number.isFinite(prod)
      ? exp - prod
      : null;
  return {
    returnPct: prod ?? null,
    tradeCount: opts.productionTradeCount ?? null,
    maxDrawdownPct: opts.productionMaxDrawdownPct ?? null,
    deltaReturnPp: delta,
    status: opts.status ?? (prod != null ? "ready" : "pending"),
    note: opts.note ?? null,
  };
}

export function resolveDiaDIdentity(
  a: DiaDReconciliationInput["experimentSlot"],
  b: DiaDReconciliationInput["productionSlot"],
): DiaDIdentityKind {
  if (!a || !b) return "unknown";
  const idA = a.strategyDefinitionId?.trim() || null;
  const idB = b.strategyDefinitionId?.trim() || null;
  if (idA && idB && idA === idB) return "same_id";
  const famA = (a.strategyType ?? "").trim().toLowerCase();
  const famB = (b.strategyType ?? "").trim().toLowerCase();
  if (famA && famB && famA === famB) return "same_family";
  return "different";
}

export function buildDiaDReconciliation(
  input: DiaDReconciliationInput,
): DiaDReconciliationResult {
  const identity = resolveDiaDIdentity(
    input.experimentSlot,
    input.productionSlot,
  );
  const band = input.evidenceBand;
  const oos = input.oosReturnPct ?? null;
  const experimentLabel = input.experimentSlot?.label ?? null;
  const productionLabel = input.productionSlot?.label ?? null;

  let code: DiaDReconciliationCode = "INCONCLUSIVE";
  if (
    !input.experimentSlot ||
    !band ||
    band === "incomplete" ||
    identity === "unknown"
  ) {
    code = "INCONCLUSIVE";
  } else if (identity === "same_id" || identity === "same_family") {
    if (band === "favorable") code = "SAME_CONFIRMED";
    else if (band === "adverse") code = "SAME_FAILED";
    else code = "SAME_MIXED";
  } else if (identity === "different") {
    if (band === "favorable") code = "DRIFT_BETTER";
    else if (band === "adverse") code = "DRIFT_WORSE";
    else code = "INCONCLUSIVE";
  }

  const same =
    identity === "same_id" || identity === "same_family"
      ? identity === "same_family"
        ? "Misma familia de estrategia"
        : "Misma estrategia"
      : identity === "different"
        ? "Estrategia distinta a la Finalista #1 operativa (F-hoy)"
        : "No hay Finalista operativa #1 para comparar";

  const oosBit =
    oos != null && Number.isFinite(oos)
      ? ` OOS D→hoy (F-D#1): ${oos > 0 ? "+" : ""}${oos.toFixed(1)}%.`
      : "";

  const cf = input.counterfactual ?? null;
  let cfBit = "";
  if (
    cf?.status === "ready" &&
    cf.returnPct != null &&
    Number.isFinite(cf.returnPct)
  ) {
    const d =
      cf.deltaReturnPp != null && Number.isFinite(cf.deltaReturnPp)
        ? ` · Δ ${cf.deltaReturnPp > 0 ? "+" : ""}${cf.deltaReturnPp.toFixed(1)} pp vs F-hoy`
        : "";
    cfBit = ` Contrafactual F-hoy#1: ${cf.returnPct > 0 ? "+" : ""}${cf.returnPct.toFixed(1)}%${d}.`;
  } else if (cf?.status === "skipped_same") {
    cfBit = " Contrafactual: misma #1.";
  }

  return {
    schemaVersion: "dia_d_reconciliation_v1",
    code,
    identity,
    label: DIA_D_RECONCILIATION_LABELS[code],
    summary: `${same}.${oosBit}${cfBit} ${DIA_D_RECONCILIATION_LABELS[code]}.`
      .replace(/\s+/g, " ")
      .trim(),
    experimentLabel,
    productionLabel,
    evidenceBand: band,
    oosReturnPct: oos,
    counterfactual: cf,
  };
}
