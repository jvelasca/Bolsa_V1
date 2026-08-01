/**
 * ART-DECISION-MEMORY stub (RFC-008 D2.4 / D7).
 */

export type MemoryOutcome = 'accepted' | 'rejected' | 'deferred';

export interface DecisionMemoryEntryV1 {
  artifactType: 'ART-DECISION-MEMORY';
  schemaVersion: '1.0.0';
  memoryId: string;
  decisionId: string;
  instrumentId: string;
  outcome: MemoryOutcome;
  reasons: string[];
  policyRuleIds: string[];
  reevaluateWhen: string[];
  /** true si la oportunidad sigue válida aunque el permiso falle */
  opportunityIntact: boolean;
  policyId?: string | null;
  policyVersion?: string | null;
  createdAt: string;
}
