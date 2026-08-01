/**
 * ART-ORDER-INTENT — voluntad autorizada (humano o policy) antes de Order (F3/F4).
 */

export type OrderIntentSide = 'buy' | 'sell';

export type OrderIntentSource =
  | 'human_supervised'
  | 'paper_auto'
  | 'policy_gate'
  | 'manual';

export type OrderIntentStatus =
  | 'authorized'
  | 'executed'
  | 'cancelled'
  | 'rejected_by_gate'
  | 'expired';

export interface OrderIntentV1 {
  artifactType: 'ART-ORDER-INTENT';
  schemaVersion: '1.0.0';
  intentId: string;
  accountId: string;
  instrumentId: string;
  symbol?: string;
  side: OrderIntentSide;
  quantity: number;
  limitPrice?: number | null;
  recommendationId?: string | null;
  decisionId?: string | null;
  source: OrderIntentSource;
  status: OrderIntentStatus;
  authorizedBy: 'human' | 'system';
  authorizedAt: string;
  policyId?: string | null;
  policyVersion?: string | null;
  gateMemoryId?: string | null;
  notes?: string[];
}
