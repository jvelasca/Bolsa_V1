"""P2.C — Belief Engine v0 (ADR-011 D13, ADR-012). Pure update + persistence."""

from __future__ import annotations

import math
from typing import Any, Protocol

from bolsa_domain.entities.hypothesis_belief import BeliefHistoryEntry, HypothesisBelief
from bolsa_domain.entities.research_evidence import ResearchEvidence

MATH_VERSION_BELIEF_V0 = "belief_lab_v0"

PRIOR_BELIEF = 0.35
PRIOR_CI_LOW = 0.15
PRIOR_CI_HIGH = 0.55

_LEVEL_ALPHA: dict[str, float] = {
    "A": 0.28,
    "B": 0.18,
    "C": 0.08,
    "D": 0.0,
}


class _BeliefRepo(Protocol):
    async def get_by_hypothesis_id(self, hypothesis_id: str) -> HypothesisBelief | None: ...

    async def get_by_id(self, belief_id: str) -> HypothesisBelief | None: ...

    async def upsert_state(
        self,
        *,
        hypothesis_id: str,
        belief: float,
        belief_ci_low: float,
        belief_ci_high: float,
        n_experiments: int,
        evidence_weight: float,
        contexts_ok: list[str],
        contexts_fail: list[str],
        evidence_ids: list[str],
        trial_ids: list[str],
        math_version: str,
        belief_id: str | None = None,
    ) -> HypothesisBelief: ...

    async def append_history(
        self,
        *,
        hypothesis_id: str,
        belief_id: str,
        belief: float,
        belief_ci_low: float,
        belief_ci_high: float,
        n_experiments: int,
        evidence_weight: float,
        math_version: str,
        trigger_evidence_id: str | None = None,
        delta: dict[str, Any] | None = None,
    ) -> BeliefHistoryEntry: ...

    async def list_history(
        self,
        hypothesis_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BeliefHistoryEntry], int]: ...


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _ci_for_n(belief: float, n: int) -> tuple[float, float]:
    """Symmetric CI that shrinks with n; never narrower than ±0.05."""
    half = max(0.05, 0.40 / math.sqrt(max(n, 1)))
    return _clamp01(belief - half), _clamp01(belief + half)


def evidence_support_sign(evidence: ResearchEvidence) -> float:
    """+1 support, -1 contradict, 0 neutral. Lab heuristics only (v0)."""
    summary = evidence.summary if isinstance(evidence.summary, dict) else {}
    if evidence.level == "D":
        return 0.0

    score = None
    for key in ("isScore", "totalReturnPct", "sharpeRatio", "walkForwardEfficiency"):
        val = summary.get(key)
        if isinstance(val, (int, float)):
            score = float(val)
            break

    pbo = summary.get("pbo")
    band = summary.get("edgeBand")
    fail = summary.get("failCode")

    sign = 0.0
    if fail:
        sign -= 1.0
    if isinstance(pbo, (int, float)) and float(pbo) >= 0.5:
        sign -= 0.75
    if isinstance(band, str):
        if band in {"edge", "strong"}:
            sign += 0.75
        elif band in {"luck", "none"}:
            sign -= 0.5
        elif band == "uncertain":
            sign += 0.0
    if score is not None:
        if score > 0:
            sign += 0.5
        elif score < 0:
            sign -= 0.5

    if sign > 0.25:
        return 1.0
    if sign < -0.25:
        return -1.0
    return 0.0


def apply_evidence_to_belief_state(
    current: HypothesisBelief | None,
    evidence: ResearchEvidence,
    *,
    hypothesis_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pure transition. Returns (next_state_kwargs, delta_for_history)."""
    if current is not None and evidence.id in current.evidence_ids:
        # Idempotent: already applied.
        return (
            {
                "hypothesis_id": current.hypothesis_id,
                "belief": current.belief,
                "belief_ci_low": current.belief_ci_low,
                "belief_ci_high": current.belief_ci_high,
                "n_experiments": current.n_experiments,
                "evidence_weight": current.evidence_weight,
                "contexts_ok": list(current.contexts_ok),
                "contexts_fail": list(current.contexts_fail),
                "evidence_ids": list(current.evidence_ids),
                "trial_ids": list(current.trial_ids),
                "math_version": current.math_version,
                "belief_id": current.id,
            },
            {"skipped": True, "reason": "evidence_already_applied"},
        )

    prior_belief = PRIOR_BELIEF if current is None else current.belief
    n0 = 0 if current is None else current.n_experiments
    w0 = 0.0 if current is None else current.evidence_weight
    ok = [] if current is None else list(current.contexts_ok)
    fail = [] if current is None else list(current.contexts_fail)
    eids = [] if current is None else list(current.evidence_ids)
    tids = [] if current is None else list(current.trial_ids)

    alpha = _LEVEL_ALPHA.get(evidence.level, 0.0)
    w = float(evidence.evidence_weight)
    sign = evidence_support_sign(evidence)
    step = alpha * w * sign
    new_belief = _clamp01(prior_belief + step)
    n1 = n0 + (0 if evidence.level == "D" else 1)
    w1 = w0 + w
    ci_low, ci_high = _ci_for_n(new_belief, max(n1, 1))

    source = evidence.source
    if sign > 0 and source not in ok:
        ok.append(source)
    if sign < 0 and source not in fail:
        fail.append(source)

    eids.append(evidence.id)
    if evidence.trial_id and evidence.trial_id not in tids:
        tids.append(evidence.trial_id)

    state = {
        "hypothesis_id": hypothesis_id,
        "belief": new_belief,
        "belief_ci_low": ci_low,
        "belief_ci_high": ci_high,
        "n_experiments": n1,
        "evidence_weight": w1,
        "contexts_ok": ok,
        "contexts_fail": fail,
        "evidence_ids": eids,
        "trial_ids": tids,
        "math_version": MATH_VERSION_BELIEF_V0,
        "belief_id": None if current is None else current.id,
    }
    delta = {
        "fromBelief": prior_belief,
        "toBelief": new_belief,
        "step": step,
        "sign": sign,
        "alpha": alpha,
        "evidenceWeight": w,
        "level": evidence.level,
        "source": evidence.source,
        "evidenceId": evidence.id,
    }
    return state, delta


def prior_belief_state(hypothesis_id: str) -> dict[str, Any]:
    return {
        "hypothesis_id": hypothesis_id,
        "belief": PRIOR_BELIEF,
        "belief_ci_low": PRIOR_CI_LOW,
        "belief_ci_high": PRIOR_CI_HIGH,
        "n_experiments": 0,
        "evidence_weight": 0.0,
        "contexts_ok": [],
        "contexts_fail": [],
        "evidence_ids": [],
        "trial_ids": [],
        "math_version": MATH_VERSION_BELIEF_V0,
        "belief_id": None,
    }


async def ensure_prior_belief(
    repo: _BeliefRepo | None,
    hypothesis_id: str,
) -> HypothesisBelief | None:
    if repo is None or not hypothesis_id:
        return None
    existing = await repo.get_by_hypothesis_id(hypothesis_id)
    if existing is not None:
        return existing
    state = prior_belief_state(hypothesis_id)
    saved = await repo.upsert_state(**state)
    await repo.append_history(
        hypothesis_id=hypothesis_id,
        belief_id=saved.id,
        belief=saved.belief,
        belief_ci_low=saved.belief_ci_low,
        belief_ci_high=saved.belief_ci_high,
        n_experiments=saved.n_experiments,
        evidence_weight=saved.evidence_weight,
        math_version=saved.math_version,
        trigger_evidence_id=None,
        delta={"event": "prior_seed"},
    )
    return saved


async def update_belief_from_evidence(
    repo: _BeliefRepo | None,
    evidence: ResearchEvidence,
) -> HypothesisBelief | None:
    """Apply one Evidence row to Belief. No-op without hypothesis_id or repo."""
    if repo is None or not evidence.hypothesis_id:
        return None
    current = await repo.get_by_hypothesis_id(evidence.hypothesis_id)
    state, delta = apply_evidence_to_belief_state(
        current, evidence, hypothesis_id=evidence.hypothesis_id
    )
    if delta.get("skipped"):
        return current
    saved = await repo.upsert_state(**state)
    await repo.append_history(
        hypothesis_id=saved.hypothesis_id,
        belief_id=saved.id,
        belief=saved.belief,
        belief_ci_low=saved.belief_ci_low,
        belief_ci_high=saved.belief_ci_high,
        n_experiments=saved.n_experiments,
        evidence_weight=saved.evidence_weight,
        math_version=saved.math_version,
        trigger_evidence_id=evidence.id,
        delta=delta,
    )
    return saved


class GetHypothesisBelief:
    """Obtiene Hypothesis Belief."""
    def __init__(self, repository: _BeliefRepo) -> None:
        self._repository = repository

    async def execute(self, hypothesis_id: str) -> HypothesisBelief | None:
        return await self._repository.get_by_hypothesis_id(hypothesis_id)


class ListBeliefHistory:
    """Lista Belief History."""
    def __init__(self, repository: _BeliefRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        hypothesis_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BeliefHistoryEntry], int]:
        return await self._repository.list_history(
            hypothesis_id, limit=limit, offset=offset
        )
