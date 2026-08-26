"""OperationalIncident — resolución humana de recon (ADR-035 DEX-3).

OR-4 detecta y veta. Este objeto exige review → resolve → clear.
Nunca auto-heal: resolve/clear no mutan cash, holdings ni PositionState.
≠ PortfolioReconciliation (informe) ≠ Confirm split (DEX-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

OperationalIncidentKind = Literal[
    "portfolio_drift",
    "live_drift",
    "live_unavailable",
]
OperationalIncidentStatus = Literal["open", "in_review", "resolved", "cleared"]
IncidentOpeningStatus = Literal["clear", "unresolved"]

OPERATIONAL_INCIDENT_KEY = "operationalIncident"

_ACTIVE_STATUSES: frozenset[OperationalIncidentStatus] = frozenset(
    {"open", "in_review", "resolved"}
)
_VALID_KINDS: frozenset[str] = frozenset(
    {"portfolio_drift", "live_drift", "live_unavailable"}
)


def _non_empty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class OperationalIncident:
    """Incidente operacional. Activo hasta clear explícito con recon clean."""

    incident_id: str
    account_id: str
    kind: OperationalIncidentKind
    status: OperationalIncidentStatus
    snapshot: str | None
    opened_at: datetime
    reviewed_at: datetime | None
    reviewed_by: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None
    cleared_at: datetime | None

    def to_dict(self) -> dict[str, object]:
        return {
            "incidentId": self.incident_id,
            "accountId": self.account_id,
            "kind": self.kind,
            "status": self.status,
            "snapshot": self.snapshot,
            "openedAt": self.opened_at.isoformat(),
            "reviewedAt": (
                self.reviewed_at.isoformat() if self.reviewed_at is not None else None
            ),
            "reviewedBy": self.reviewed_by,
            "resolvedAt": (
                self.resolved_at.isoformat() if self.resolved_at is not None else None
            ),
            "resolvedBy": self.resolved_by,
            "resolutionNote": self.resolution_note,
            "clearedAt": (
                self.cleared_at.isoformat() if self.cleared_at is not None else None
            ),
        }


def incident_blocks_opening(status: OperationalIncidentStatus | str) -> bool:
    """True mientras el incidente no está cleared (exige resolución humana)."""
    return status in _ACTIVE_STATUSES


def incident_opening_veto_reason(
    *,
    incident_status: IncidentOpeningStatus | None = None,
    require: bool = False,
) -> str | None:
    """Reason de VETO DEX-3, o None si la apertura puede seguir.

    ``require=False`` y sin status → gate off (compat tests / wiring legado).
    ``incident_status=unresolved`` → ``incident:unresolved``.
    """
    if not require and incident_status is None:
        return None
    if incident_status == "unresolved":
        return "incident:unresolved"
    return None


def kinds_from_recon(
    *,
    portfolio_recon_status: str | None = None,
    live_recon_status: str | None = None,
    broker_venue: str | None = None,
) -> tuple[OperationalIncidentKind, ...]:
    """Kinds a abrir desde statuses OI-6 / LR-1. Paper ignora live (igual OR-4)."""
    out: list[OperationalIncidentKind] = []
    if portfolio_recon_status == "drift":
        out.append("portfolio_drift")
    venue = (broker_venue or "paper").strip().lower()
    if venue == "live":
        if live_recon_status == "drift":
            out.append("live_drift")
        elif live_recon_status == "unavailable":
            out.append("live_unavailable")
    return tuple(out)


def open_incident(
    *,
    incident_id: str,
    account_id: str,
    kind: OperationalIncidentKind,
    snapshot: str | None = None,
    now: datetime | None = None,
) -> OperationalIncident:
    iid = _non_empty(incident_id)
    aid = _non_empty(account_id)
    if iid is None or aid is None:
        raise ValueError("incident:identity_required")
    if kind not in _VALID_KINDS:
        raise ValueError("incident:invalid_kind")
    stamp = now or _utcnow()
    return OperationalIncident(
        incident_id=iid,
        account_id=aid,
        kind=kind,
        status="open",
        snapshot=_non_empty(snapshot),
        opened_at=stamp,
        reviewed_at=None,
        reviewed_by=None,
        resolved_at=None,
        resolved_by=None,
        resolution_note=None,
        cleared_at=None,
    )


def mark_in_review(
    incident: OperationalIncident,
    *,
    reviewed_by: str | None = None,
    now: datetime | None = None,
) -> OperationalIncident:
    if incident.status == "in_review":
        return incident
    if incident.status != "open":
        raise ValueError("incident:invalid_transition")
    stamp = now or _utcnow()
    return OperationalIncident(
        incident_id=incident.incident_id,
        account_id=incident.account_id,
        kind=incident.kind,
        status="in_review",
        snapshot=incident.snapshot,
        opened_at=incident.opened_at,
        reviewed_at=stamp,
        reviewed_by=_non_empty(reviewed_by),
        resolved_at=None,
        resolved_by=None,
        resolution_note=None,
        cleared_at=None,
    )


def resolve_incident(
    incident: OperationalIncident,
    *,
    resolution_note: str,
    resolved_by: str | None = None,
    now: datetime | None = None,
) -> OperationalIncident:
    """Humano registra resolución. No muta libros."""
    if incident.status == "resolved":
        return incident
    if incident.status == "cleared":
        raise ValueError("incident:already_cleared")
    if incident.status not in {"open", "in_review"}:
        raise ValueError("incident:invalid_transition")
    note = _non_empty(resolution_note)
    if note is None:
        raise ValueError("incident:resolution_note_required")
    stamp = now or _utcnow()
    return OperationalIncident(
        incident_id=incident.incident_id,
        account_id=incident.account_id,
        kind=incident.kind,
        status="resolved",
        snapshot=incident.snapshot,
        opened_at=incident.opened_at,
        reviewed_at=incident.reviewed_at,
        reviewed_by=incident.reviewed_by,
        resolved_at=stamp,
        resolved_by=_non_empty(resolved_by),
        resolution_note=note,
        cleared_at=None,
    )


def can_clear(
    incident: OperationalIncident,
    *,
    recon_status: str | None,
) -> bool:
    return incident.status == "resolved" and recon_status == "clean"


def clear_incident(
    incident: OperationalIncident,
    *,
    recon_status: str | None,
    now: datetime | None = None,
) -> OperationalIncident:
    """Cierra solo si resolved y recon actual clean. Nunca auto-heal."""
    if incident.status == "cleared":
        return incident
    if incident.status != "resolved":
        raise ValueError("incident:not_resolved")
    if recon_status != "clean":
        raise ValueError("incident:recon_not_clean")
    stamp = now or _utcnow()
    return OperationalIncident(
        incident_id=incident.incident_id,
        account_id=incident.account_id,
        kind=incident.kind,
        status="cleared",
        snapshot=incident.snapshot,
        opened_at=incident.opened_at,
        reviewed_at=incident.reviewed_at,
        reviewed_by=incident.reviewed_by,
        resolved_at=incident.resolved_at,
        resolved_by=incident.resolved_by,
        resolution_note=incident.resolution_note,
        cleared_at=stamp,
    )


def operational_incident_status_copy(status: OperationalIncidentStatus | str) -> str:
    if status == "open":
        return "Incidente abierto — requiere revisión humana. Sin auto-heal."
    if status == "in_review":
        return "Incidente en revisión — no abre cesta hasta resolve + clear."
    if status == "resolved":
        return "Resuelto (nota humana). Clear solo si recon = clean. Sin auto-heal."
    if status == "cleared":
        return "Incidente cerrado. Un drift nuevo abre otro incidente."
    return "Estado de incidente desconocido."
