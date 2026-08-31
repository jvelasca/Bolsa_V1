/**
 * OperatingPolicy — composición InvestorProfile → políticas operativas (V1.35).
 * Esqueleto documental: compone TradingPolicy + ExitPolicy sin nuevos gates.
 */

import type { ExitPolicyV1 } from "./exit-policy.js";
import { resolveExitPolicy } from "./exit-policy.js";
import type { PolicyTemplateId, TradingPolicyV1 } from "./trading-policy.js";
import { getTradingPolicyTemplate } from "./trading-policy-templates.js";

export type OperatingPolicyTemplateId = Extract<
  PolicyTemplateId,
  "conservative" | "moderate" | "aggressive_swing"
>;

export type EntryPolicyV1 = {
  /** Placeholder — setup bias / entry_ready (TradePlan v0). */
  requiresSetup: boolean;
};

export type RiskPolicyV1 = TradingPolicyV1["risk"];

export type PositionSizingPolicyV1 = {
  maxOpenPositions: number;
  maxPortfolioConcentrationPct: number;
};

export type TrailingPolicyV1 = {
  trailWidth: ExitPolicyV1["trailWidth"];
  /** Ratchet: nunca empeorar stop sin override auditado. */
  ratchetOnly: true;
};

export type TimePolicyV1 = {
  maxHoldingPeriodDays: number;
  minHoldingPeriodMinutes: number;
};

export type ConcentrationPolicyV1 = {
  maxSectorExposurePct: number;
  maxLeverage: number;
};

export type OperatingPolicyV1 = {
  templateId: OperatingPolicyTemplateId;
  entry: EntryPolicyV1;
  risk: RiskPolicyV1;
  sizing: PositionSizingPolicyV1;
  exit: ExitPolicyV1;
  trailing: TrailingPolicyV1;
  time: TimePolicyV1;
  concentration: ConcentrationPolicyV1;
};

function normalizeTemplateId(
  templateId: string | null | undefined,
): OperatingPolicyTemplateId {
  if (templateId === "conservative" || templateId === "aggressive_swing") {
    return templateId;
  }
  return "moderate";
}

/** InvestorProfile template → OperatingPolicy (≠ permiso de firma). */
export function resolveOperatingPolicy(
  templateId: string | null | undefined,
): OperatingPolicyV1 {
  const id = normalizeTemplateId(templateId);
  const trading = getTradingPolicyTemplate(id);
  const exit = resolveExitPolicy(id);
  return {
    templateId: id,
    entry: { requiresSetup: true },
    risk: trading.risk,
    sizing: {
      maxOpenPositions: trading.exposure.maxOpenPositions,
      maxPortfolioConcentrationPct:
        trading.exposure.maxPortfolioConcentrationPct,
    },
    exit,
    trailing: {
      trailWidth: exit.trailWidth,
      ratchetOnly: true,
    },
    time: {
      maxHoldingPeriodDays: trading.horizon.maxHoldingPeriodDays,
      minHoldingPeriodMinutes: trading.horizon.minHoldingPeriodMinutes,
    },
    concentration: {
      maxSectorExposurePct: trading.exposure.maxSectorExposurePct,
      maxLeverage: trading.exposure.maxLeverage,
    },
  };
}

export function formatOperatingPolicyPreview(
  policy: OperatingPolicyV1,
): string {
  const t1 = Math.round(policy.exit.t1ReduceFraction * 100);
  const t2 = Math.round(policy.exit.t2ReduceFraction * 100);
  return (
    `${policy.templateId}: T1 ${t1}% · T2 ${t2}% · trail ${policy.trailing.trailWidth} · ` +
    `max DD ${policy.risk.hardMaxDrawdownLimitPct}% · sector ${policy.concentration.maxSectorExposurePct}%`
  );
}
