/**
 * OR-4 — Reconciliation → opening veto (ADR-035).
 * OI-6 / LR-1 detect/report → DENY aperturas. Exits bypassean en check_opening.
 * Nunca auto-heal.
 */

export type PortfolioReconStatusV1 = "clean" | "drift" | "unavailable";

export const PORTFOLIO_RECON_STATUSES = [
  "clean",
  "drift",
  "unavailable",
] as const satisfies readonly PortfolioReconStatusV1[];
export type LiveReconStatusV1 = "clean" | "drift" | "unavailable";
export type BrokerVenueV1 = "paper" | "live";

export type ReconciliationOpeningVetoInputV1 = {
  portfolioReconStatus?: PortfolioReconStatusV1 | null;
  liveReconStatus?: LiveReconStatusV1 | null;
  brokerVenue?: BrokerVenueV1 | string | null;
  require?: boolean;
};

/** Reason de VETO OR-4, o null si la apertura puede seguir. */
export function reconciliationOpeningVetoReason(
  input: ReconciliationOpeningVetoInputV1 = {},
): string | null {
  const require = Boolean(input.require);
  const portfolio = input.portfolioReconStatus ?? null;
  const live = input.liveReconStatus ?? null;
  if (!require && portfolio == null && live == null) {
    return null;
  }
  if (portfolio === "drift") {
    return "reconciliation:portfolio_drift";
  }
  if (portfolio === "unavailable") {
    return "reconciliation:portfolio_unavailable";
  }
  const venue = String(input.brokerVenue ?? "paper")
    .trim()
    .toLowerCase();
  if (venue === "live") {
    if (live === "drift") {
      return "reconciliation:live_drift";
    }
    if (live === "unavailable" || (require && live == null)) {
      return "reconciliation:live_unavailable";
    }
  }
  return null;
}
