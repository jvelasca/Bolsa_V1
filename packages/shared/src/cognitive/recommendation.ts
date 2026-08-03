/**
 * ART-RECOMMENDATION — Portfolio domain (RFC-000 / RFC-008 / F3).
 * Signal = mercado; Recommendation = acción + sizing base; Intent = voluntad autorizada.
 */

import type { DecisionAction, DecisionMetricsV1 } from './decision-package.js';

export type RecommendationStatus =
  | 'proposed'
  | 'awaiting_human'
  | 'approved'
  | 'rejected'
  | 'expired'
  | 'superseded';

export interface RecommendationV1 {
  artifactType: 'ART-RECOMMENDATION';
  schemaVersion: '1.0.0';
  recommendationId: string;
  decisionId: string;
  instrumentId: string;
  symbol?: string;
  /** ISO país del instrumento (preferencia geo SEMI). */
  country?: string | null;
  accountId?: string | null;
  action: DecisionAction;
  /** Unidades sugeridas (paper/sizing base). */
  suggestedQuantity: number;
  suggestedPrice?: number | null;
  notional?: number | null;
  metrics: DecisionMetricsV1;
  scoreTa?: number | null;
  profileSnapshotRef?: string | null;
  policyVersion?: string | null;
  decisionPackageRef?: string | null;
  edgeReportRef?: string | null;
  status: RecommendationStatus;
  createdAt: string;
  expiresAt?: string | null;
  notes?: string[];
}
