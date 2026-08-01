/**
 * ART-PROFILE — InvestorProfile (RFC-008).
 * Declared ≠ Observed: never auto-merge into Policy.
 * Catálogo: tabla investor_profiles; cuentas referencian activeProfileId.
 */

import type { SuggestablePolicyTemplateId } from './suggest-policy-from-declared.js';

export type ProfileHorizon =
  | 'intraday'
  | 'swing'
  | 'position'
  | 'long_term';

export type RiskTolerance = 'low' | 'moderate' | 'high';

export type ExperienceLevel = 'novice' | 'intermediate' | 'advanced' | 'professional';

export type ProfileUpdatedBy = 'user' | 'system_observation' | 'hybrid';

/** Quién dice ser el inversor (cuestionario). */
export interface DeclaredInvestorProfile {
  horizon: ProfileHorizon;
  objectives: string[];
  riskTolerance: RiskTolerance;
  experience: ExperienceLevel;
  maxAcceptableLossPct?: number;
  notes?: string;
}

/**
 * Comportamiento medido — solo observación.
 * Nunca reescribe Declared ni TradingPolicy.
 */
export interface ObservedInvestorProfile {
  sampleTradeCount: number;
  impulsivityScore?: number;
  overtradingScore?: number;
  disciplineScore?: number;
  /** true si el comportamiento diverge del perfil declarado / policy activa */
  divergesFromDeclared: boolean;
  divergesFromPolicy: boolean;
  lastObservedAt?: string;
  notes?: string[];
}

/** Ficha de catálogo ART-PROFILE (tabla investor_profiles). */
export interface InvestorProfileV1 {
  artifactType?: 'ART-PROFILE';
  schemaVersion?: '1.0.0';
  profileId: string;
  version: string;
  name: string;
  userId?: string | null;
  declared: DeclaredInvestorProfile;
  observed?: ObservedInvestorProfile | null;
  suggestedPolicyTemplateId: SuggestablePolicyTemplateId | string;
  selectedPolicyTemplateId: SuggestablePolicyTemplateId | string;
  updatedBy: ProfileUpdatedBy | string;
  updatedAt: string;
  createdAt: string;
}

export interface ProfilePolicyDivergence {
  profileId: string;
  policyId: string;
  divergesFromDeclared: boolean;
  divergesFromPolicy: boolean;
  messages: string[];
}
