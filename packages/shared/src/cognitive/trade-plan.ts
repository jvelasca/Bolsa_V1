/**
 * TradePlan — plan condicional sobre DecisionPackage (ADR-031 / ADR-032 F1).
 * Status machine = v0; F1 añade targets / R/R / sizing / fit snapshot / constraints.
 * Tesis ≠ plan ≠ permiso. No sustituye el spine.
 */

export type TradePlanStatusV1 =
  | "WATCH"
  | "ARMED"
  | "TRIGGERED"
  | "BLOCKED"
  | "EXPIRED";

export type TradePlanDirectionV1 = "long" | "short" | "none";

export type TradePlanWhyNotV1 =
  | "fit"
  | "freshness"
  | "mandate"
  | "entry"
  | "no_stop"
  | "expired"
  | "orphan"
  | "rr"
  | "regime"
  /** Proyección Hoy sin TradePlan vivo — no es un veto real del mapper. */
  | "legacy_projection";

export type EntrySetupV1 = "breakout" | "pullback" | "wyckoff" | "none";

/** F1 — condición evaluable; `entrySetup` v0 no desaparece. */
export type EntryConditionV1 = "ready" | "wait" | "none";

/** F1 — snapshot informativo; veto de fill sigue en check_opening. */
export type PortfolioFitSnapshotV1 = {
  status: "allow" | "veto" | "skipped";
  reason?: string | null;
};

/** F1 — TTL / liquidez / horario; no es orden. */
export type ExecutionConstraintsV1 = {
  expiresAt?: string | null;
  liquidity?: string | null;
  sessionWindow?: string | null;
};

export type TradePlanV1 = {
  decisionId: string;
  /** V1.65 — PK del plan cuando difiere de decisionId (default = decisionId). */
  tradePlanId?: string | null;
  instrumentId: string;
  direction: TradePlanDirectionV1;
  status: TradePlanStatusV1;
  quantity: number;
  riskPct: number;
  whyNot: TradePlanWhyNotV1[];
  executionAllowed: boolean;
  opportunityScore?: number | null;
  /** Ordinal de status (WATCH 0.4 / ARMED 0.7 / TRIGGERED 0.95), no score predictivo. */
  actionability?: number | null;
  entry?: number | null;
  structuralStop?: number | null;
  expiresAt?: string | null;
  entrySetup?: EntrySetupV1 | null;
  /** F1 — vínculo tesis ≠ plan; default = decisionId si ausente. */
  thesisId?: string | null;
  entryCondition?: EntryConditionV1 | null;
  target1?: number | null;
  target2?: number | null;
  initialRiskR?: number | null;
  riskAmount?: number | null;
  positionValue?: number | null;
  expectedRR?: number | null;
  portfolioFit?: PortfolioFitSnapshotV1 | null;
  executionConstraints?: ExecutionConstraintsV1 | null;
};
