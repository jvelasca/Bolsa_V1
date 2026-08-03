"""P2.A — Evidence Store v0: classify + emit (ADR-018).

Incluye emit desde research_trials (Lab) y sandbox DÍA D
(``emit_evidence_for_dia_d_session``, source=``dia_d_session``, techo C, sin Belief).
"""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_domain.entities.research_evidence import (
    EvidenceLevel,
    EvidenceSource,
    ResearchEvidence,
)
from bolsa_domain.entities.research_trial import ResearchTrial

MATH_VERSION_EVIDENCE_V0 = "evidence_level_lab_v0"

_WEIGHT: dict[EvidenceLevel, float] = {
    "A": 1.0,
    "B": 0.7,
    "C": 0.25,
    "D": 0.0,
}


class _EvidenceRepo(Protocol):
    async def insert_evidence(
        self,
        *,
        instrument_id: str,
        level: str,
        source: str,
        evidence_weight: float,
        summary: dict[str, Any],
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        edge_report_id: str | None = None,
        math_version: str | None = None,
        evidence_id: str | None = None,
    ) -> ResearchEvidence: ...

    async def get_by_id(self, evidence_id: str) -> ResearchEvidence | None: ...

    async def list_evidence(
        self,
        *,
        instrument_id: str | None = None,
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchEvidence], int]: ...


def evidence_weight_for_level(level: EvidenceLevel) -> float:
    return _WEIGHT[level]


def classify_evidence_from_blocks(
    blocks: dict[str, Any] | None,
    *,
    has_is_metrics: bool = True,
) -> tuple[EvidenceLevel, EvidenceSource]:
    """Lab-adapted ADR-012 levels (ADR-018). Never returns A automatically."""
    if not has_is_metrics and not blocks:
        return "D", "narrative"

    if isinstance(blocks, dict):
        if isinstance(blocks.get("cpcv"), dict):
            return "B", "cpcv"
        if isinstance(blocks.get("walkForward"), dict):
            return "B", "walkforward"
        if isinstance(blocks.get("oosMetrics"), dict):
            return "C", "holdout"
        # Edge-only without OOS structure still counts as weak experimental evidence.
        if isinstance(blocks.get("edgeReport"), dict) and has_is_metrics:
            return "C", "trial_is"

    if has_is_metrics:
        return "C", "trial_is"
    return "D", "narrative"


def _extract_pbo(blocks: dict[str, Any], lab: dict[str, Any]) -> float | None:
    if isinstance(lab.get("pbo"), (int, float)):
        return float(lab["pbo"])
    pbo_block = blocks.get("pbo")
    if isinstance(pbo_block, dict) and isinstance(pbo_block.get("pbo"), (int, float)):
        return float(pbo_block["pbo"])
    cpcv = blocks.get("cpcv")
    if isinstance(cpcv, dict):
        nested = cpcv.get("pbo")
        if isinstance(nested, dict) and isinstance(nested.get("pbo"), (int, float)):
            return float(nested["pbo"])
        if isinstance(nested, (int, float)):
            return float(nested)
    return None


def build_evidence_summary(
    trial: ResearchTrial,
    *,
    level: EvidenceLevel,
    source: EvidenceSource,
) -> dict[str, Any]:
    blocks = trial.blocks if isinstance(trial.blocks, dict) else {}
    metrics = trial.is_metrics if isinstance(trial.is_metrics, dict) else {}
    edge = blocks.get("edgeReport") if isinstance(blocks.get("edgeReport"), dict) else {}
    lab = blocks.get("labEvidence") if isinstance(blocks.get("labEvidence"), dict) else {}
    wf = blocks.get("walkForward") if isinstance(blocks.get("walkForward"), dict) else {}
    cpcv = blocks.get("cpcv") if isinstance(blocks.get("cpcv"), dict) else {}
    wfe = (
        lab.get("walkForwardEfficiency")
        or wf.get("walkForwardEfficiency")
        or cpcv.get("walkForwardEfficiency")
    )
    summary: dict[str, Any] = {
        "level": level,
        "source": source,
        "proposedBy": trial.proposed_by,
        "presetKey": trial.preset_key,
        "strategyName": trial.strategy_name,
        "isScore": trial.is_score,
        "sharpeRatio": metrics.get("sharpeRatio"),
        "totalReturnPct": metrics.get("totalReturnPct"),
        "labMode": lab.get("mode"),
        "walkForwardEfficiency": wfe,
        "pbo": _extract_pbo(blocks, lab),
        "edgeBand": edge.get("band"),
        "edgeCredibility": edge.get("credibility"),
        "persistedEdgeReportId": edge.get("persistedEdgeReportId") or edge.get("edgeReportId"),
        "optimizationRunId": trial.optimization_run_id,
        "backtestRunId": trial.backtest_run_id,
        "failCode": trial.fail_code,
    }
    return {k: v for k, v in summary.items() if v is not None}


def build_evidence_draft_from_trial(trial: ResearchTrial) -> dict[str, Any] | None:
    """Pure draft for insert_evidence kwargs. None only if trial lacks instrument."""
    if not trial.instrument_id:
        return None
    has_metrics = bool(trial.is_metrics)
    level, source = classify_evidence_from_blocks(trial.blocks, has_is_metrics=has_metrics)
    blocks = trial.blocks if isinstance(trial.blocks, dict) else {}
    edge = blocks.get("edgeReport") if isinstance(blocks.get("edgeReport"), dict) else {}
    edge_id = edge.get("persistedEdgeReportId") or edge.get("edgeReportId")
    if isinstance(edge_id, str) and not edge_id:
        edge_id = None
    return {
        "instrument_id": trial.instrument_id,
        "level": level,
        "source": source,
        "evidence_weight": evidence_weight_for_level(level),
        "summary": build_evidence_summary(trial, level=level, source=source),
        "trial_id": trial.id,
        "hypothesis_id": trial.hypothesis_id,
        "edge_report_id": edge_id if isinstance(edge_id, str) else None,
        "math_version": MATH_VERSION_EVIDENCE_V0,
    }


async def emit_evidence_for_trial(
    repo: _EvidenceRepo | None,
    trial: ResearchTrial,
    *,
    belief_repo: Any | None = None,
) -> ResearchEvidence | None:
    """Best-effort append (+ Belief update if hypothesis linked). No-op if repo missing."""
    if repo is None:
        return None
    draft = build_evidence_draft_from_trial(trial)
    if draft is None:
        return None
    evidence = await repo.insert_evidence(**draft)
    if belief_repo is not None and evidence.hypothesis_id:
        from bolsa_application.belief_engine import update_belief_from_evidence

        await update_belief_from_evidence(belief_repo, evidence)
    return evidence


MATH_VERSION_DIA_D_EVIDENCE_V0 = "dia_d_session_evidence_v0"


def classify_dia_d_session_level(band: str | None) -> EvidenceLevel:
    """Sandbox DÍA D nunca sube de C; incomplete → D."""
    b = (band or "").strip().lower()
    if b in {"favorable", "mixed", "adverse"}:
        return "C"
    return "D"


def build_evidence_draft_from_dia_d_session(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Draft insert_evidence para sesión C DÍA D. No toca Belief ni TOP."""
    instrument_id = str(payload.get("instrumentId") or payload.get("instrument_id") or "").strip()
    if not instrument_id:
        return None
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    band = str(evidence.get("band") or payload.get("band") or "")
    level = classify_dia_d_session_level(band)
    paragraphs = evidence.get("paragraphs") if isinstance(evidence.get("paragraphs"), list) else []
    claims = evidence.get("claims") if isinstance(evidence.get("claims"), list) else []
    warnings = evidence.get("warnings") if isinstance(evidence.get("warnings"), list) else []
    metrics = evidence.get("metrics") if isinstance(evidence.get("metrics"), dict) else {}
    summary: dict[str, Any] = {
        "kind": "dia_d_session",
        "schemaVersion": evidence.get("schemaVersion") or "dia_d_session_evidence_v1",
        "sandbox": True,
        "level": level,
        "source": "dia_d_session",
        "band": band or None,
        "confidence": evidence.get("confidence"),
        "mode": payload.get("mode") or metrics.get("mode"),
        "symbol": payload.get("symbol"),
        "strategyLabel": payload.get("strategyLabel") or payload.get("strategy_label"),
        "diaD": payload.get("diaD") or payload.get("dia_d"),
        "endDate": payload.get("endDate") or payload.get("end_date"),
        "engine": payload.get("engine") or "heuristic",
        "metrics": metrics or None,
        "claims": claims or None,
        "warnings": warnings or None,
        "paragraphs": [str(p) for p in paragraphs[:3]] or None,
        "disclaimer": evidence.get("disclaimer"),
        "note": "Sandbox DÍA D ≠ DEMO live. No auto-paper. No Belief.",
    }
    return {
        "instrument_id": instrument_id,
        "level": level,
        "source": "dia_d_session",
        "evidence_weight": evidence_weight_for_level(level),
        "summary": {k: v for k, v in summary.items() if v is not None},
        "trial_id": None,
        "hypothesis_id": None,
        "edge_report_id": None,
        "math_version": MATH_VERSION_DIA_D_EVIDENCE_V0,
    }


async def emit_evidence_for_dia_d_session(
    repo: _EvidenceRepo | None,
    payload: dict[str, Any],
) -> ResearchEvidence | None:
    """Persiste Evidence sesión C DÍA D en research_evidence. Sin Belief."""
    if repo is None:
        return None
    draft = build_evidence_draft_from_dia_d_session(payload)
    if draft is None:
        return None
    return await repo.insert_evidence(**draft)


class ListResearchEvidence:
    """Lista Research Evidence."""
    def __init__(self, repository: _EvidenceRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        instrument_id: str | None = None,
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchEvidence], int]:
        return await self._repository.list_evidence(
            instrument_id=instrument_id,
            trial_id=trial_id,
            hypothesis_id=hypothesis_id,
            level=level,
            limit=limit,
            offset=offset,
        )


class GetResearchEvidence:
    """Obtiene Research Evidence."""
    def __init__(self, repository: _EvidenceRepo) -> None:
        self._repository = repository

    async def execute(self, evidence_id: str) -> ResearchEvidence | None:
        return await self._repository.get_by_id(evidence_id)
