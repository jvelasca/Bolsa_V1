/**
 * ART-ORDER-PROPOSAL — handle de fase spine (refs-only; ADR-029).
 * Proyección desde `decision_sessions` kind=propose; no duplica Recommendation/Intent.
 */

export type OrderProposalStatus =
  | "open"
  | "confirmed"
  | "rejected"
  | "superseded"
  | "expired";

export interface OrderProposalV1 {
  artifactType?: "ART-ORDER-PROPOSAL";
  schemaVersion: "1.0.0";
  /** Same as propose session id. */
  proposalId: string;
  decisionId: string;
  recommendationId: string;
  sessionId: string;
  accountId?: string | null;
  instrumentId: string;
  status: OrderProposalStatus;
  createdAt: string;
  closedAt?: string | null;
}
