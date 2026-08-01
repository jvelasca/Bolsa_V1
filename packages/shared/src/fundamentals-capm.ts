/**
 * FIE F2.6 — CAPM cost of equity (`fund_capm_v1`).
 *
 * k_e = r_f + beta × ERP
 * - beta: vivo (Yahoo)
 * - r_f / ERP: constantes versionadas (bump si cambian)
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 */

export const FUND_CAPM_VERSION = 'fund_capm_v1' as const;

export const CAPM_RF = 0.04;
export const CAPM_ERP = 0.05;
export const CAPM_BETA_FLOOR = 0.3;
export const CAPM_BETA_CAP = 2.5;

export function clampBeta(beta: number | null | undefined): number | null {
  if (beta == null || !Number.isFinite(beta) || beta <= 0) return null;
  return Math.max(CAPM_BETA_FLOOR, Math.min(CAPM_BETA_CAP, beta));
}

export function computeCapmCostOfEquity(
  beta: number | null | undefined,
  opts?: { rf?: number; erp?: number },
): {
  ke: number;
  method: typeof FUND_CAPM_VERSION;
  beta: number;
  rf: number;
  erp: number;
} | null {
  const b = clampBeta(beta);
  if (b == null) return null;
  const rf = opts?.rf ?? CAPM_RF;
  const erp = opts?.erp ?? CAPM_ERP;
  if (!(erp > 0) || rf < 0) return null;
  return {
    ke: Math.round((rf + b * erp) * 10000) / 10000,
    method: FUND_CAPM_VERSION,
    beta: Math.round(b * 10000) / 10000,
    rf,
    erp,
  };
}
