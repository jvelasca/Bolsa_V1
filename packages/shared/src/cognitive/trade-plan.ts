/**
 * TradePlan v0 — plan condicional sobre DecisionPackage (ADR-031).
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
  | "regime";

export type EntrySetupV1 = "breakout" | "pullback" | "wyckoff" | "none";

export type TradePlanV1 = {
  decisionId: string;
  instrumentId: string;
  direction: TradePlanDirectionV1;
  status: TradePlanStatusV1;
  quantity: number;
  riskPct: number;
  whyNot: TradePlanWhyNotV1[];
  executionAllowed: boolean;
  opportunityScore?: number | null;
  actionability?: number | null;
  entry?: number | null;
  structuralStop?: number | null;
  expiresAt?: string | null;
  entrySetup?: EntrySetupV1 | null;
};
