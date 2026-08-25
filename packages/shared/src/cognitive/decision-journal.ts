/**
 * ART-DECISION-JOURNAL — audit trail append-only de transiciones spine (ADR-029).
 * Complementa DecisionSession (foto); no la sustituye.
 */

export type JournalEventType =
  | "proposal_recorded"
  | "gate_evaluated"
  | "human_confirm"
  | "human_reject"
  | "risk_veto"
  | "contract_verified"
  | "contract_absent"
  | "executed"
  | "session_verdict";

export type JournalActor = "human" | "system";

export interface DecisionJournalEntryV1 {
  artifactType?: "ART-DECISION-JOURNAL-ENTRY";
  schemaVersion: "1.0.0";
  entryId: string;
  decisionId: string;
  sessionId?: string | null;
  accountId?: string | null;
  instrumentId?: string | null;
  eventType: JournalEventType;
  actor: JournalActor;
  payload?: Record<string, unknown> | null;
  createdAt: string;
}
