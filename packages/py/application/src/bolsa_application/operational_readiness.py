"""OR-6 — SEMI operational certification (ADR-035).

Cuatro estados discretos. Un FAIL crítico no se promedia a un %.
OE-1 PASS/FAIL/WARN sigue measure ≠ Accept. El carril AUTO no entra.
"""

from __future__ import annotations

from typing import Any, Literal

ReadinessState = Literal[
    "PAPER_READY",
    "PAPER_DEGRADED",
    "LIVE_EXPERIMENTAL",
    "LIVE_BLOCKED",
]
BrokerVenue = Literal["paper", "live"]
CtaKind = Literal["execute", "protect"]

_READINESS_RULE = (
    "no averaging · critical FAIL is not fifty-percent ready · measure ≠ Accept"
)


def _norm_venue(raw: str | None) -> BrokerVenue:
    venue = (raw or "paper").strip().lower()
    return "live" if venue == "live" else "paper"


def derive_operational_readiness(
    *,
    broker_venue: BrokerVenue | str | None = None,
    kill_switch_effective: bool = False,
    portfolio_reconciliation_status: str | None = "not_wired",
    live_reconciliation_status: str | None = None,
    semi_path_mark: str | None = "PASS",
    live_adapter_wired: bool | None = None,
) -> dict[str, Any]:
    """Mapea runtime + OE-1 a un estado. AUTO marks no son parámetro a propósito."""

    venue = _norm_venue(broker_venue)
    reasons: list[str] = []
    notes: list[str] = []

    recon = (portfolio_reconciliation_status or "not_wired").strip().lower()
    if recon == "drift":
        reasons.append("portfolio_drift")
    elif recon != "ok":
        reasons.append("recon_not_certified")

    if kill_switch_effective:
        reasons.append("kill_switch")

    semi = (semi_path_mark or "PASS").strip().upper()
    if semi == "UNAVAILABLE":
        reasons.append("semi_path_unavailable")
    elif semi == "WARN":
        notes.append("thin_semi_evidence")

    live = (live_reconciliation_status or "").strip().lower()
    if venue == "live":
        if live == "drift":
            reasons.append("live_drift")
        elif live == "unavailable":
            reasons.append("live_unavailable")
        if live_adapter_wired is False:
            reasons.append("live_adapter_not_wired")
        notes.append("live_not_accepted")

    if venue == "live":
        state: ReadinessState = (
            "LIVE_BLOCKED" if reasons else "LIVE_EXPERIMENTAL"
        )
    else:
        state = "PAPER_DEGRADED" if reasons else "PAPER_READY"

    return {
        "state": state,
        "venue": venue,
        "reasons": reasons,
        "notes": notes,
        "rule": _READINESS_RULE,
    }


def execute_cta_label(
    venue: BrokerVenue | str | None = None,
    *,
    kind: CtaKind = "execute",
) -> str:
    """Copy de firma. Protect no es envío a broker."""

    if kind == "protect":
        return "Confirmar protección"
    if _norm_venue(venue) == "live":
        return "Ejecutar en LIVE"
    return "Ejecutar en PAPER"
