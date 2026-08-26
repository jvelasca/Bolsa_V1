/**
 * OperationalIncident — resolución humana de recon (ADR-035 DEX-3).
 * OR-4 detecta y veta. Este objeto exige review → resolve → clear.
 * Nunca auto-heal: resolve/clear no mutan cash, holdings ni PositionState.
 */

export type OperationalIncidentKindV1 =
  | "portfolio_drift"
  | "live_drift"
  | "live_unavailable";

export type OperationalIncidentStatusV1 =
  | "open"
  | "in_review"
  | "resolved"
  | "cleared";

export type IncidentOpeningStatusV1 = "clear" | "unresolved";

export type OperationalIncidentV1 = {
  incidentId: string;
  accountId: string;
  kind: OperationalIncidentKindV1;
  status: OperationalIncidentStatusV1;
  snapshot: string | null;
  openedAt: string;
  reviewedAt: string | null;
  reviewedBy: string | null;
  resolvedAt: string | null;
  resolvedBy: string | null;
  resolutionNote: string | null;
  clearedAt: string | null;
};

export const OPERATIONAL_INCIDENT_KEY = "operationalIncident";

const ACTIVE_STATUSES: ReadonlySet<OperationalIncidentStatusV1> = new Set([
  "open",
  "in_review",
  "resolved",
]);

const VALID_KINDS: ReadonlySet<OperationalIncidentKindV1> = new Set([
  "portfolio_drift",
  "live_drift",
  "live_unavailable",
]);

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function isoNow(): string {
  return new Date().toISOString();
}

export function incidentBlocksOpening(
  status: OperationalIncidentStatusV1 | string,
): boolean {
  return ACTIVE_STATUSES.has(status as OperationalIncidentStatusV1);
}

export function incidentOpeningVetoReason(
  input: {
    incidentStatus?: IncidentOpeningStatusV1 | null;
    require?: boolean;
  } = {},
): string | null {
  const require = Boolean(input.require);
  const status = input.incidentStatus ?? null;
  if (!require && status == null) {
    return null;
  }
  if (status === "unresolved") {
    return "incident:unresolved";
  }
  return null;
}

export function kindsFromRecon(input: {
  portfolioReconStatus?: string | null;
  liveReconStatus?: string | null;
  brokerVenue?: string | null;
}): OperationalIncidentKindV1[] {
  const out: OperationalIncidentKindV1[] = [];
  if (input.portfolioReconStatus === "drift") {
    out.push("portfolio_drift");
  }
  const venue = String(input.brokerVenue ?? "paper")
    .trim()
    .toLowerCase();
  if (venue === "live") {
    if (input.liveReconStatus === "drift") {
      out.push("live_drift");
    } else if (input.liveReconStatus === "unavailable") {
      out.push("live_unavailable");
    }
  }
  return out;
}

export function openIncident(input: {
  incidentId: string;
  accountId: string;
  kind: OperationalIncidentKindV1;
  snapshot?: string | null;
  now?: string | null;
}): OperationalIncidentV1 {
  const incidentId = nonEmpty(input.incidentId);
  const accountId = nonEmpty(input.accountId);
  if (incidentId == null || accountId == null) {
    throw new Error("incident:identity_required");
  }
  if (!VALID_KINDS.has(input.kind)) {
    throw new Error("incident:invalid_kind");
  }
  return {
    incidentId,
    accountId,
    kind: input.kind,
    status: "open",
    snapshot: nonEmpty(input.snapshot),
    openedAt: nonEmpty(input.now) ?? isoNow(),
    reviewedAt: null,
    reviewedBy: null,
    resolvedAt: null,
    resolvedBy: null,
    resolutionNote: null,
    clearedAt: null,
  };
}

export function markInReview(
  incident: OperationalIncidentV1,
  input: { reviewedBy?: string | null; now?: string | null } = {},
): OperationalIncidentV1 {
  if (incident.status === "in_review") {
    return incident;
  }
  if (incident.status !== "open") {
    throw new Error("incident:invalid_transition");
  }
  return {
    ...incident,
    status: "in_review",
    reviewedAt: nonEmpty(input.now) ?? isoNow(),
    reviewedBy: nonEmpty(input.reviewedBy),
    resolvedAt: null,
    resolvedBy: null,
    resolutionNote: null,
    clearedAt: null,
  };
}

export function resolveIncident(
  incident: OperationalIncidentV1,
  input: {
    resolutionNote: string;
    resolvedBy?: string | null;
    now?: string | null;
  },
): OperationalIncidentV1 {
  if (incident.status === "resolved") {
    return incident;
  }
  if (incident.status === "cleared") {
    throw new Error("incident:already_cleared");
  }
  if (incident.status !== "open" && incident.status !== "in_review") {
    throw new Error("incident:invalid_transition");
  }
  const note = nonEmpty(input.resolutionNote);
  if (note == null) {
    throw new Error("incident:resolution_note_required");
  }
  return {
    ...incident,
    status: "resolved",
    resolvedAt: nonEmpty(input.now) ?? isoNow(),
    resolvedBy: nonEmpty(input.resolvedBy),
    resolutionNote: note,
    clearedAt: null,
  };
}

export function canClear(
  incident: OperationalIncidentV1,
  reconStatus: string | null | undefined,
): boolean {
  return incident.status === "resolved" && reconStatus === "clean";
}

export function clearIncident(
  incident: OperationalIncidentV1,
  input: { reconStatus?: string | null; now?: string | null },
): OperationalIncidentV1 {
  if (incident.status === "cleared") {
    return incident;
  }
  if (incident.status !== "resolved") {
    throw new Error("incident:not_resolved");
  }
  if (input.reconStatus !== "clean") {
    throw new Error("incident:recon_not_clean");
  }
  return {
    ...incident,
    status: "cleared",
    clearedAt: nonEmpty(input.now) ?? isoNow(),
  };
}

export function operationalIncidentStatusCopy(
  status: OperationalIncidentStatusV1 | string,
): string {
  if (status === "open") {
    return "Incidente abierto — requiere revisión humana. Sin auto-heal.";
  }
  if (status === "in_review") {
    return "Incidente en revisión — no abre cesta hasta resolve + clear.";
  }
  if (status === "resolved") {
    return "Resuelto (nota humana). Clear solo si recon = clean. Sin auto-heal.";
  }
  if (status === "cleared") {
    return "Incidente cerrado. Un drift nuevo abre otro incidente.";
  }
  return "Estado de incidente desconocido.";
}
