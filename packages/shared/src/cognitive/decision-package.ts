/**
 * ART-DECISION-PACKAGE — RFC-008 D2 (TA-only first).
 * Recommendation ≠ Conviction; métricas cuádruples (Amendment-1).
 */

import type { PolicyGateResult } from './trading-policy.js';

export type DecisionAction =
  | 'recommend_long'
  | 'recommend_short'
  | 'wait'
  | 'reduce'
  | 'exit_hint';

export interface EvidenceBreakdownItem {
  role: string;
  score: number;
  weight: number;
  facts: string[];
  invalidators?: string[];
}

export interface DecisionMetricsV1 {
  /** ¿Estoy seguro de la tesis? 0–1 */
  confidence: number;
  /** ¿Los motores coinciden? 0–1 */
  consensus: number;
  /** ¿Cuánta evidencia hay? 0–1 */
  evidenceStrength: number;
  /** ¿Robusta a perturbaciones leves? 0–1 */
  stability: number;
  /**
   * Potencial esperado de la tesis (distinto de confidence).
   * Alta conviction + baja confidence = apuesta asimétrica incierta.
   */
  conviction: number;
}

export interface DecisionPackageV1 {
  artifactType: 'ART-DECISION-PACKAGE';
  schemaVersion: '1.0.0';
  decisionId: string;
  instrumentId: string;
  timestamp: string;
  action: DecisionAction;
  /** Alias de metrics.confidence (compat UI) */
  overallConfidence: number;
  metrics: DecisionMetricsV1;
  scoreTa: number;
  evidenceBreakdown: EvidenceBreakdownItem[];
  factSetRef?: string;
  edgeReportRef?: string | null;
  edgeScore?: number | null;
  profileSnapshotRef?: string | null;
  policyVersion?: string | null;
  complianceCheck?: PolicyGateResult | null;
  memoryRef?: string | null;
  /** false si Gate VETO o action no abre posición; la `action` no se reescribe */
  executionAllowed?: boolean | null;
  decisionCaseRef?: string | null;
  notes?: string[];
}
