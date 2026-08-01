from typing import Any, Protocol

from bolsa_domain.entities.hypothesis_belief import BeliefHistoryEntry, HypothesisBelief


class HypothesisBeliefRepository(Protocol):
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
