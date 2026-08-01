/**
 * Mapeo DeclaredInvestorProfile → plantilla TradingPolicy (RFC-008 D1).
 * Solo sugiere; el usuario puede override. Nunca escribe Observed ni Policy hard.
 */

import type { DeclaredInvestorProfile } from './investor-profile.js';

export type SuggestablePolicyTemplateId =
  | 'conservative'
  | 'moderate'
  | 'aggressive_swing';

/**
 * Heurística determinista v1:
 * - riskTolerance es el eje principal
 * - horizon intradía + high → aggressive_swing
 * - long_term + low se queda conservative
 */
export function suggestPolicyTemplateFromDeclared(
  declared: Pick<DeclaredInvestorProfile, 'riskTolerance' | 'horizon' | 'experience'>,
): SuggestablePolicyTemplateId {
  const { riskTolerance, horizon, experience } = declared;

  if (riskTolerance === 'low') {
    return 'conservative';
  }

  if (riskTolerance === 'high') {
    if (horizon === 'long_term' && experience === 'novice') {
      return 'moderate';
    }
    return 'aggressive_swing';
  }

  // moderate
  if (horizon === 'intraday') {
    return 'aggressive_swing';
  }
  if (horizon === 'long_term') {
    return 'conservative';
  }
  return 'moderate';
}

export const POLICY_TEMPLATE_LABELS: Record<SuggestablePolicyTemplateId, string> = {
  conservative: 'Conservador',
  moderate: 'Moderado',
  aggressive_swing: 'Swing agresivo',
};
