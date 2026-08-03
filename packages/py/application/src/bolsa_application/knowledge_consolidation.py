"""P2.D — Knowledge nodes v0 + Consolidation stub (ADR-012 §3.3, ADR-013 §7).

Consolidation is always explicit. Never auto-promotes from a single good trial.
"""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_domain.entities.hypothesis import Hypothesis
from bolsa_domain.entities.hypothesis_belief import HypothesisBelief
from bolsa_domain.entities.knowledge_node import KnowledgeNode
from bolsa_domain.entities.research_evidence import ResearchEvidence

MATH_VERSION_CONSOLIDATION_V0 = "consolidation_lab_v0"

MIN_N_EXPERIMENTS = 3
MIN_BELIEF = 0.55
MAX_CI_WIDTH = 0.40
MIN_KNOWLEDGE_CONFIDENCE = 0.40

ALLOWED_STAGES = frozenset(
    {"CANDIDATE", "EMERGING", "ACCEPTED", "CANONICAL", "DEPRECATED"}
)


class _HypRepo(Protocol):
    async def get_by_id(self, hypothesis_id: str) -> Hypothesis | None: ...

    async def update(
        self,
        hypothesis_id: str,
        *,
        status: str | None = None,
        **kwargs: Any,
    ) -> Hypothesis | None: ...


class _BeliefRepo(Protocol):
    async def get_by_hypothesis_id(self, hypothesis_id: str) -> HypothesisBelief | None: ...


class _EvidenceRepo(Protocol):
    async def list_evidence(
        self,
        *,
        hypothesis_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        **kwargs: Any,
    ) -> tuple[list[ResearchEvidence], int]: ...


class _KnowledgeRepo(Protocol):
    async def insert(
        self,
        *,
        hypothesis_id: str,
        stage: str,
        statement: str,
        knowledge_confidence: float,
        validity_context: dict[str, Any],
        evidence_ids: list[str],
        belief_snapshot: dict[str, Any],
        consolidation_report: dict[str, Any],
        math_version: str,
        notes: str | None = None,
        node_id: str | None = None,
    ) -> KnowledgeNode: ...

    async def get_by_id(self, node_id: str) -> KnowledgeNode | None: ...

    async def list(
        self,
        *,
        hypothesis_id: str | None = None,
        stage: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[KnowledgeNode], int]: ...

    async def list_active_for_hypothesis(
        self, hypothesis_id: str
    ) -> list[KnowledgeNode]: ...

    async def update_stage(
        self, node_id: str, stage: str
    ) -> KnowledgeNode | None: ...


def _ci_width(belief: HypothesisBelief) -> float:
    return max(0.0, float(belief.belief_ci_high) - float(belief.belief_ci_low))


def _has_level_b_or_better(evidences: list[ResearchEvidence]) -> bool:
    return any(e.level in {"A", "B"} for e in evidences)


def initial_knowledge_confidence(belief: HypothesisBelief) -> float:
    """Structural seed from Belief (not the same as Belief itself)."""
    width = _ci_width(belief)
    stability = max(0.0, 1.0 - width)
    n_factor = min(1.0, belief.n_experiments / 10.0)
    raw = 0.35 * belief.belief + 0.35 * stability + 0.30 * n_factor
    return max(MIN_KNOWLEDGE_CONFIDENCE, min(0.85, raw))


def evaluate_consolidation_eligibility(
    *,
    hypothesis: Hypothesis | None,
    belief: HypothesisBelief | None,
    evidences: list[ResearchEvidence],
    active_nodes: list[KnowledgeNode],
    acknowledge_landscape_gap: bool = False,
) -> dict[str, Any]:
    """Pure gate report. eligible=True only if all hard checks pass."""
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    def add(code: str, ok: bool, detail: str, *, hard: bool = True) -> None:
        checks.append({"code": code, "ok": ok, "detail": detail, "hard": hard})

    if hypothesis is None:
        add("hypothesis_exists", False, "Hypothesis not found")
        return {
            "eligible": False,
            "mathVersion": MATH_VERSION_CONSOLIDATION_V0,
            "checks": checks,
            "warnings": warnings,
            "failReasons": ["hypothesis_exists"],
        }

    add("hypothesis_exists", True, f"kind={hypothesis.kind} status={hypothesis.status}")

    if belief is None:
        add("belief_exists", False, "No Belief state — create/link evidence first")
    else:
        add("belief_exists", True, f"belief={belief.belief:.3f} n={belief.n_experiments}")
        add(
            "min_n",
            belief.n_experiments >= MIN_N_EXPERIMENTS,
            f"n_experiments={belief.n_experiments} (min {MIN_N_EXPERIMENTS})",
        )
        add(
            "min_belief",
            belief.belief >= MIN_BELIEF,
            f"belief={belief.belief:.3f} (min {MIN_BELIEF})",
        )
        width = _ci_width(belief)
        add(
            "ci_stable",
            width <= MAX_CI_WIDTH,
            f"ci_width={width:.3f} (max {MAX_CI_WIDTH})",
        )
        add(
            "falsifiers_clear",
            len(belief.contexts_fail) == 0,
            f"contexts_fail={belief.contexts_fail}",
        )

    has_b = _has_level_b_or_better(evidences)
    levels = sorted({e.level for e in evidences})
    add(
        "evidence_level_b",
        has_b,
        f"levels={levels or []} — need ≥1 Evidence A/B (ADR-012)",
    )

    # Landscape: not evaluated in lab v0 — hard fail unless acknowledged.
    landscape_ok = acknowledge_landscape_gap
    add(
        "landscape_not_peak",
        landscape_ok,
        "landscape_not_evaluated — pass acknowledgeLandscapeGap=true to proceed (stub)",
    )
    if acknowledge_landscape_gap:
        warnings.append("landscape_gap_acknowledged")

    no_active = len(active_nodes) == 0
    add(
        "no_active_knowledge",
        no_active,
        f"active_nodes={len(active_nodes)} (deprecate existing before re-consolidate)",
    )

    fail_reasons = [c["code"] for c in checks if c["hard"] and not c["ok"]]
    return {
        "eligible": len(fail_reasons) == 0,
        "mathVersion": MATH_VERSION_CONSOLIDATION_V0,
        "checks": checks,
        "warnings": warnings,
        "failReasons": fail_reasons,
        "hypothesisId": hypothesis.id,
        "proposedStage": "EMERGING",
    }


class EvaluateConsolidation:
    """Evalúa Consolidation."""
    def __init__(
        self,
        hypotheses: _HypRepo,
        beliefs: _BeliefRepo,
        evidence: _EvidenceRepo,
        knowledge: _KnowledgeRepo,
    ) -> None:
        self._hypotheses = hypotheses
        self._beliefs = beliefs
        self._evidence = evidence
        self._knowledge = knowledge

    async def execute(
        self,
        hypothesis_id: str,
        *,
        acknowledge_landscape_gap: bool = False,
    ) -> dict[str, Any]:
        hyp = await self._hypotheses.get_by_id(hypothesis_id)
        belief = await self._beliefs.get_by_hypothesis_id(hypothesis_id)
        evidences, _ = await self._evidence.list_evidence(
            hypothesis_id=hypothesis_id, limit=200, offset=0
        )
        active = await self._knowledge.list_active_for_hypothesis(hypothesis_id)
        return evaluate_consolidation_eligibility(
            hypothesis=hyp,
            belief=belief,
            evidences=evidences,
            active_nodes=active,
            acknowledge_landscape_gap=acknowledge_landscape_gap,
        )


class ConsolidateHypothesis:
    """Explicit Consolidation → Knowledge node at EMERGING (not MKL/ACCEPTED yet)."""

    def __init__(
        self,
        hypotheses: _HypRepo,
        beliefs: _BeliefRepo,
        evidence: _EvidenceRepo,
        knowledge: _KnowledgeRepo,
        tree_repo: Any | None = None,
    ) -> None:
        self._hypotheses = hypotheses
        self._beliefs = beliefs
        self._evidence = evidence
        self._knowledge = knowledge
        self._tree = tree_repo

    async def execute(
        self,
        hypothesis_id: str,
        *,
        acknowledge_landscape_gap: bool = False,
        notes: str | None = None,
        validity_context: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        hyp = await self._hypotheses.get_by_id(hypothesis_id)
        if hyp is None:
            raise LookupError("Hypothesis not found")
        belief = await self._beliefs.get_by_hypothesis_id(hypothesis_id)
        evidences, _ = await self._evidence.list_evidence(
            hypothesis_id=hypothesis_id, limit=200, offset=0
        )
        active = await self._knowledge.list_active_for_hypothesis(hypothesis_id)
        report = evaluate_consolidation_eligibility(
            hypothesis=hyp,
            belief=belief,
            evidences=evidences,
            active_nodes=active,
            acknowledge_landscape_gap=acknowledge_landscape_gap,
        )
        if dry_run or not report["eligible"]:
            return {"created": False, "node": None, "report": report, "treeEdges": []}

        assert belief is not None  # eligible implies belief
        snapshot = {
            "belief": belief.belief,
            "beliefCiLow": belief.belief_ci_low,
            "beliefCiHigh": belief.belief_ci_high,
            "nExperiments": belief.n_experiments,
            "evidenceWeight": belief.evidence_weight,
            "mathVersion": belief.math_version,
        }
        ctx = validity_context if isinstance(validity_context, dict) else {}
        if hyp.domain and "domain" not in ctx:
            ctx = {**ctx, "domain": hyp.domain}
        node = await self._knowledge.insert(
            hypothesis_id=hypothesis_id,
            stage="EMERGING",
            statement=hyp.statement,
            knowledge_confidence=initial_knowledge_confidence(belief),
            validity_context=ctx,
            evidence_ids=list(belief.evidence_ids),
            belief_snapshot=snapshot,
            consolidation_report=report,
            math_version=MATH_VERSION_CONSOLIDATION_V0,
            notes=notes,
        )
        await self._hypotheses.update(hypothesis_id, status="consolidated")
        from bolsa_application.research_tree import link_consolidation_tree

        tree_edges = await link_consolidation_tree(
            self._tree, hypothesis_id=hypothesis_id, knowledge_node=node
        )
        return {
            "created": True,
            "node": node,
            "report": report,
            "treeEdges": tree_edges,
        }


class GetKnowledgeNode:
    """Obtiene Knowledge Node."""
    def __init__(self, repository: _KnowledgeRepo) -> None:
        self._repository = repository

    async def execute(self, node_id: str) -> KnowledgeNode | None:
        return await self._repository.get_by_id(node_id)


class ListKnowledgeNodes:
    """Lista Knowledge Nodes."""
    def __init__(self, repository: _KnowledgeRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        hypothesis_id: str | None = None,
        stage: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[KnowledgeNode], int]:
        if stage is not None and stage not in ALLOWED_STAGES:
            raise ValueError(f"stage: uno de {sorted(ALLOWED_STAGES)}")
        return await self._repository.list(
            hypothesis_id=hypothesis_id,
            stage=stage,
            limit=limit,
            offset=offset,
        )


class DeprecateKnowledgeNode:
    """Use-case / tipo: Deprecate Knowledge Node."""
    def __init__(self, repository: _KnowledgeRepo) -> None:
        self._repository = repository

    async def execute(self, node_id: str) -> KnowledgeNode | None:
        return await self._repository.update_stage(node_id, "DEPRECATED")
