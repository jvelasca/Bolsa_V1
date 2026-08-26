/**
 * OR-6 — SEMI operational certification (ADR-035).
 * Cuatro estados discretos. Un FAIL crítico no se promedia a un %.
 * AUTO lane no entra. Espejo de operational_readiness.py.
 */

export type OperationalReadinessStateV1 =
  | "PAPER_READY"
  | "PAPER_DEGRADED"
  | "LIVE_EXPERIMENTAL"
  | "LIVE_BLOCKED";

export type ExecuteCtaKindV1 = "execute" | "protect";

type Venue = "paper" | "live";

export type OperationalReadinessInputV1 = {
  brokerVenue?: Venue | string | null;
  killSwitchEffective?: boolean;
  portfolioReconciliationStatus?: string | null;
  liveReconciliationStatus?: string | null;
  semiPathMark?: string | null;
  liveAdapterWired?: boolean | null;
};

export type OperationalReadinessV1 = {
  state: OperationalReadinessStateV1;
  venue: Venue;
  reasons: string[];
  notes: string[];
  rule: string;
};

const READINESS_RULE =
  "no averaging · critical FAIL is not fifty-percent ready · measure ≠ Accept";

function normVenue(raw: string | null | undefined): Venue {
  return String(raw ?? "paper")
    .trim()
    .toLowerCase() === "live"
    ? "live"
    : "paper";
}

export function deriveOperationalReadiness(
  input: OperationalReadinessInputV1 = {},
): OperationalReadinessV1 {
  const venue = normVenue(input.brokerVenue);
  const reasons: string[] = [];
  const notes: string[] = [];

  const recon = String(input.portfolioReconciliationStatus ?? "not_wired")
    .trim()
    .toLowerCase();
  if (recon === "drift") {
    reasons.push("portfolio_drift");
  } else if (recon !== "ok") {
    reasons.push("recon_not_certified");
  }

  if (input.killSwitchEffective) {
    reasons.push("kill_switch");
  }

  const semi = String(input.semiPathMark ?? "PASS")
    .trim()
    .toUpperCase();
  if (semi === "UNAVAILABLE") {
    reasons.push("semi_path_unavailable");
  } else if (semi === "WARN") {
    notes.push("thin_semi_evidence");
  }

  const live = String(input.liveReconciliationStatus ?? "")
    .trim()
    .toLowerCase();
  if (venue === "live") {
    if (live === "drift") {
      reasons.push("live_drift");
    } else if (live === "unavailable") {
      reasons.push("live_unavailable");
    }
    if (input.liveAdapterWired === false) {
      reasons.push("live_adapter_not_wired");
    }
    notes.push("live_not_accepted");
  }

  const state: OperationalReadinessStateV1 =
    venue === "live"
      ? reasons.length > 0
        ? "LIVE_BLOCKED"
        : "LIVE_EXPERIMENTAL"
      : reasons.length > 0
        ? "PAPER_DEGRADED"
        : "PAPER_READY";

  return {
    state,
    venue,
    reasons,
    notes,
    rule: READINESS_RULE,
  };
}

export function executeCtaLabel(
  venue?: Venue | string | null,
  kind: ExecuteCtaKindV1 = "execute",
): string {
  if (kind === "protect") return "Confirmar protección";
  return normVenue(venue) === "live" ? "Ejecutar en LIVE" : "Ejecutar en PAPER";
}
