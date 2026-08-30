/**
 * EffectiveTradingPolicy — TradingPolicy resuelta desde perfil activo (V1.30).
 * SoT para límites de encaje en scenario / priority; fallback moderate sin perfil.
 */

import type { PolicyTemplateId, TradingPolicyV1 } from "./trading-policy.js";
import { getTradingPolicyTemplate } from "./trading-policy-templates.js";

export type EffectiveTradingPolicyTemplateId = Extract<
  PolicyTemplateId,
  "conservative" | "moderate" | "aggressive_swing"
>;

function normalizeTemplateId(
  templateId: string | null | undefined,
): EffectiveTradingPolicyTemplateId {
  if (templateId === "conservative" || templateId === "aggressive_swing") {
    return templateId;
  }
  return "moderate";
}

/** Política operativa efectiva desde plantilla de perfil (≠ permiso de firma). */
export function resolveEffectiveTradingPolicy(
  templateId: string | null | undefined,
): TradingPolicyV1 {
  return getTradingPolicyTemplate(normalizeTemplateId(templateId));
}

export function effectiveMaxSectorExposurePct(
  templateId: string | null | undefined,
): number {
  return resolveEffectiveTradingPolicy(templateId).exposure
    .maxSectorExposurePct;
}

export function effectiveMaxPortfolioConcentrationPct(
  templateId: string | null | undefined,
): number {
  return resolveEffectiveTradingPolicy(templateId).exposure
    .maxPortfolioConcentrationPct;
}

/** Preview Config — límites de encaje (no es permiso). */
export function formatPortfolioFitPreview(policy: TradingPolicyV1): string {
  const e = policy.exposure;
  return `Encaja: max sector ${e.maxSectorExposurePct}% · max posición ${e.maxPortfolioConcentrationPct}% · ${e.maxOpenPositions} pos. abiertas`;
}
