"""P2.B — Hypothesis CRUD + falsifiers stub (ADR-011 D21, ADR-018)."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from bolsa_domain.entities.hypothesis import Hypothesis
from bolsa_domain.entities.research_trial import ResearchTrial

ALLOWED_KINDS = frozenset({"hypothesis", "anti"})
ALLOWED_STATUSES = frozenset({"open", "paused", "abandoned", "consolidated"})
ALLOWED_FALSIFIER_KINDS = frozenset(
    {"metric_threshold", "narrative", "regime_break", "other"}
)


class _HypothesisRepo(Protocol):
    async def insert(
        self,
        *,
        statement: str,
        falsifiers: list[dict[str, Any]],
        kind: str = "hypothesis",
        domain: str | None = None,
        context: dict[str, Any] | None = None,
        status: str = "open",
        hypothesis_id: str | None = None,
    ) -> Hypothesis: ...

    async def get_by_id(self, hypothesis_id: str) -> Hypothesis | None: ...

    async def list(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Hypothesis], int]: ...

    async def update(
        self,
        hypothesis_id: str,
        *,
        statement: str | None = None,
        falsifiers: list[dict[str, Any]] | None = None,
        kind: str | None = None,
        domain: str | None = None,
        context: dict[str, Any] | None = None,
        status: str | None = None,
        clear_domain: bool = False,
        clear_context: bool = False,
    ) -> Hypothesis | None: ...


class _TrialRepo(Protocol):
    async def get_by_id(self, trial_id: str) -> ResearchTrial | None: ...

    async def set_hypothesis_id(
        self, trial_id: str, hypothesis_id: str | None
    ) -> ResearchTrial | None: ...


def normalize_falsifiers(raw: Any) -> list[dict[str, Any]]:
    """Validate and normalize falsifiers stub. Raises ValueError if invalid."""
    if not isinstance(raw, list) or len(raw) < 1:
        raise ValueError("falsifiers: se requiere al menos un falsifier (ADR-011 D21)")
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"falsifiers[{i}]: debe ser un objeto")
        desc = item.get("description")
        if not isinstance(desc, str) or not desc.strip():
            raise ValueError(f"falsifiers[{i}].description: obligatorio")
        kind = item.get("kind") or "narrative"
        if not isinstance(kind, str) or kind not in ALLOWED_FALSIFIER_KINDS:
            raise ValueError(
                f"falsifiers[{i}].kind: uno de {sorted(ALLOWED_FALSIFIER_KINDS)}"
            )
        fid = item.get("id")
        if not isinstance(fid, str) or not fid.strip():
            fid = str(uuid4())
        entry: dict[str, Any] = {
            "id": fid.strip(),
            "description": desc.strip(),
            "kind": kind,
        }
        params = item.get("params")
        if isinstance(params, dict):
            entry["params"] = params
        out.append(entry)
    return out


class CreateHypothesis:
    def __init__(
        self,
        repository: _HypothesisRepo,
        belief_repository: Any | None = None,
    ) -> None:
        self._repository = repository
        self._beliefs = belief_repository

    async def execute(
        self,
        *,
        statement: str,
        falsifiers: list[dict[str, Any]] | Any,
        kind: str = "hypothesis",
        domain: str | None = None,
        context: dict[str, Any] | None = None,
        status: str = "open",
    ) -> Hypothesis:
        text = (statement or "").strip()
        if not text:
            raise ValueError("statement es obligatorio")
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"kind: uno de {sorted(ALLOWED_KINDS)}")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"status: uno de {sorted(ALLOWED_STATUSES)}")
        if context is not None and not isinstance(context, dict):
            raise ValueError("context debe ser un objeto JSON")
        normalized = normalize_falsifiers(falsifiers)
        hyp = await self._repository.insert(
            statement=text,
            falsifiers=normalized,
            kind=kind,
            domain=(domain.strip() if isinstance(domain, str) and domain.strip() else None),
            context=context,
            status=status,
        )
        if self._beliefs is not None:
            from bolsa_application.belief_engine import ensure_prior_belief

            await ensure_prior_belief(self._beliefs, hyp.id)
        return hyp


class GetHypothesis:
    def __init__(self, repository: _HypothesisRepo) -> None:
        self._repository = repository

    async def execute(self, hypothesis_id: str) -> Hypothesis | None:
        return await self._repository.get_by_id(hypothesis_id)


class ListHypotheses:
    def __init__(self, repository: _HypothesisRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Hypothesis], int]:
        if status is not None and status not in ALLOWED_STATUSES:
            raise ValueError(f"status: uno de {sorted(ALLOWED_STATUSES)}")
        if kind is not None and kind not in ALLOWED_KINDS:
            raise ValueError(f"kind: uno de {sorted(ALLOWED_KINDS)}")
        return await self._repository.list(
            status=status, kind=kind, limit=limit, offset=offset
        )


class UpdateHypothesis:
    def __init__(self, repository: _HypothesisRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        hypothesis_id: str,
        *,
        statement: str | None = None,
        falsifiers: list[dict[str, Any]] | Any | None = None,
        kind: str | None = None,
        domain: str | None = None,
        context: dict[str, Any] | None = None,
        status: str | None = None,
        clear_domain: bool = False,
        clear_context: bool = False,
    ) -> Hypothesis | None:
        if statement is not None and not statement.strip():
            raise ValueError("statement no puede ser vacío")
        if kind is not None and kind not in ALLOWED_KINDS:
            raise ValueError(f"kind: uno de {sorted(ALLOWED_KINDS)}")
        if status is not None and status not in ALLOWED_STATUSES:
            raise ValueError(f"status: uno de {sorted(ALLOWED_STATUSES)}")
        if context is not None and not isinstance(context, dict):
            raise ValueError("context debe ser un objeto JSON")
        normalized = None if falsifiers is None else normalize_falsifiers(falsifiers)
        return await self._repository.update(
            hypothesis_id,
            statement=None if statement is None else statement.strip(),
            falsifiers=normalized,
            kind=kind,
            domain=domain,
            context=context,
            status=status,
            clear_domain=clear_domain,
            clear_context=clear_context,
        )


class LinkTrialToHypothesis:
    """Attach (or detach) a research_trial to a hypothesis. Does not rewrite Evidence."""

    def __init__(
        self,
        hypotheses: _HypothesisRepo,
        trials: _TrialRepo,
    ) -> None:
        self._hypotheses = hypotheses
        self._trials = trials

    async def execute(
        self,
        *,
        trial_id: str,
        hypothesis_id: str | None,
    ) -> ResearchTrial:
        trial = await self._trials.get_by_id(trial_id)
        if trial is None:
            raise LookupError("Research trial not found")
        if hypothesis_id is not None:
            hyp = await self._hypotheses.get_by_id(hypothesis_id)
            if hyp is None:
                raise LookupError("Hypothesis not found")
        updated = await self._trials.set_hypothesis_id(trial_id, hypothesis_id)
        if updated is None:
            raise LookupError("Research trial not found")
        return updated
