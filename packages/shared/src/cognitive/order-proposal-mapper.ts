/**
 * Proyecta DecisionSessionV1 kind=propose → OrderProposalV1 (refs-only).
 */

import type { DecisionSessionV1 } from "./decision-session.js";
import type { OrderProposalStatus, OrderProposalV1 } from "./order-proposal.js";

const PROPOSAL_STATUSES: ReadonlySet<string> = new Set([
  "open",
  "confirmed",
  "rejected",
  "superseded",
  "expired",
]);

function deriveProposalStatus(session: DecisionSessionV1): OrderProposalStatus {
  const recStatus =
    session.recommendation &&
    typeof session.recommendation === "object" &&
    "status" in session.recommendation
      ? String((session.recommendation as { status?: string }).status ?? "")
      : "";

  if (recStatus === "approved") return "confirmed";
  if (recStatus === "rejected") return "rejected";
  if (recStatus === "expired") return "expired";
  if (recStatus === "superseded") return "superseded";
  if (session.status === "closed") return "confirmed";
  return "open";
}

/** Maps a propose session to OrderProposalV1; returns null if not mappable. */
export function sessionToOrderProposal(
  session: DecisionSessionV1,
): OrderProposalV1 | null {
  if (session.kind !== "propose") return null;

  const decisionId = session.decisionId ?? "";
  const recommendationId =
    session.recommendationId ??
    (session.recommendation &&
    typeof session.recommendation === "object" &&
    "recommendationId" in session.recommendation
      ? String(
          (session.recommendation as { recommendationId?: string })
            .recommendationId ?? "",
        )
      : "");

  if (!decisionId || !recommendationId) return null;

  const status = deriveProposalStatus(session);
  const closedAt =
    status !== "open" && session.status === "closed" ? session.createdAt : null;

  return {
    artifactType: "ART-ORDER-PROPOSAL",
    schemaVersion: "1.0.0",
    proposalId: session.sessionId,
    decisionId,
    recommendationId,
    sessionId: session.sessionId,
    accountId: session.accountId ?? null,
    instrumentId: session.instrumentId,
    status: PROPOSAL_STATUSES.has(status) ? status : "open",
    createdAt: session.createdAt,
    closedAt,
  };
}
