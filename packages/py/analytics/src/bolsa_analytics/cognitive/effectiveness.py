"""Panel Efectividad — skill vs luck + memoria + observed (RFC-008 D7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from bolsa_analytics.cognitive.decision_memory import DecisionMemoryEntry
from bolsa_analytics.cognitive.edge_report import EdgeBand, EdgeReport
from bolsa_analytics.cognitive.investor_profile import ObservedInvestorProfile
from bolsa_analytics.cognitive.observe_profile import observed_to_dict
from bolsa_analytics.cognitive.trials_log import TrialsLog

EffectivenessStatus = Literal["ready", "insufficient_data", "demo"]


@dataclass(frozen=True, slots=True)
class EffectivenessSummary:
    """DTO para Ayuda → Efectividad (no muta Profile/Policy)."""

    status: EffectivenessStatus
    as_of: str
    trials_n: int
    credibility: float | None
    edge_score: float | None
    band: EdgeBand | None
    memory_accepted: int
    memory_rejected: int
    memory_deferred: int
    reevaluate_pending: int
    observed: ObservedInvestorProfile | None
    headline: str
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "asOf": self.as_of,
            "trialsN": self.trials_n,
            "credibility": self.credibility,
            "edgeScore": self.edge_score,
            "band": self.band,
            "memory": {
                "accepted": self.memory_accepted,
                "rejected": self.memory_rejected,
                "deferred": self.memory_deferred,
                "reevaluatePending": self.reevaluate_pending,
            },
            "observed": None if self.observed is None else observed_to_dict(self.observed),
            "headline": self.headline,
            "notes": list(self.notes),
        }


def _band_headline(band: EdgeBand | None, trials_n: int) -> str:
    if trials_n < 1:
        return "Sin TrialsLog — DSR/Credibility no son concluyentes"
    if band == "skill":
        return "Señal compatible con skill (no garantiza de PnL)"
    if band == "luck":
        return "Evidencia insuficiente / posible luck — bloquear auto-live"
    if band == "uncertain":
        return "Zona gris — paper/shadow antes de auto"
    return "Sin EdgeReport"


def build_effectiveness_summary(
    *,
    edge_report: EdgeReport | None = None,
    trials_log: TrialsLog | None = None,
    memory_entries: list[DecisionMemoryEntry] | tuple[DecisionMemoryEntry, ...] = (),
    observed: ObservedInvestorProfile | None = None,
    status: EffectivenessStatus | None = None,
) -> EffectivenessSummary:
    """Agrega Edge + Trials + Decision Memory + Observed para el panel Efectividad."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    mem = list(memory_entries)
    accepted = sum(1 for m in mem if m.outcome == "accepted")
    rejected = sum(1 for m in mem if m.outcome == "rejected")
    deferred = sum(1 for m in mem if m.outcome == "deferred")
    reevaluate = sum(1 for m in mem if m.outcome == "rejected" and m.reevaluate_when)

    trials_n = trials_log.trials_n if trials_log is not None else (
        edge_report.suite.trials_n if edge_report is not None else 0
    )

    notes: list[str] = []
    if edge_report is None and not mem and observed is None:
        st: EffectivenessStatus = status or "insufficient_data"
        notes.append("Sin EdgeReport / memoria / observed — motores listos; falta cablear datos")
        return EffectivenessSummary(
            status=st,
            as_of=now,
            trials_n=trials_n,
            credibility=None,
            edge_score=None,
            band=None,
            memory_accepted=accepted,
            memory_rejected=rejected,
            memory_deferred=deferred,
            reevaluate_pending=reevaluate,
            observed=observed,
            headline=_band_headline(None, trials_n),
            notes=tuple(notes),
        )

    band = edge_report.band if edge_report else None
    cred = edge_report.credibility if edge_report else None
    edge = edge_report.edge_score if edge_report else None
    if edge_report:
        notes.append(f"EdgeReport {edge_report.edge_report_id} band={edge_report.band}")
    if observed and (observed.diverges_from_declared or observed.diverges_from_policy):
        notes.append("Divergencia Observed vs Declared/Policy (solo alerta)")
    if reevaluate:
        notes.append(f"{reevaluate} rechazo(s) con reevaluateWhen pendiente")

    st = status or "ready"
    return EffectivenessSummary(
        status=st,
        as_of=now,
        trials_n=trials_n,
        credibility=cred,
        edge_score=edge,
        band=band,
        memory_accepted=accepted,
        memory_rejected=rejected,
        memory_deferred=deferred,
        reevaluate_pending=reevaluate,
        observed=observed,
        headline=_band_headline(band, trials_n),
        notes=tuple(notes),
    )
