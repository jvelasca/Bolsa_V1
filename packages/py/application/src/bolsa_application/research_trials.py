from typing import Any, Literal

from bolsa_domain.entities.research_trial import ResearchTrial
from bolsa_domain.repositories.research_trial_repository import ResearchTrialRepository

ResearchTrialSort = Literal[
    "created_at",
    "sharpe",
    "pnl",
    "commission",
    "k_contribution",
]


class ListResearchTrials:
    def __init__(self, repository: ResearchTrialRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        instrument_id: str | None = None,
        hypothesis_id: str | None = None,
        proposed_by: str | None = None,
        preset_key: str | None = None,
        strategy_name: str | None = None,
        strategy_definition_id: str | None = None,
        optimization_run_id: str | None = None,
        backtest_run_id: str | None = None,
        fail_code: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: ResearchTrialSort = "created_at",
        sort_dir: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchTrial], int]:
        return await self._repository.list_trials(
            instrument_id=instrument_id,
            hypothesis_id=hypothesis_id,
            proposed_by=proposed_by,
            preset_key=preset_key,
            strategy_name=strategy_name,
            strategy_definition_id=strategy_definition_id,
            optimization_run_id=optimization_run_id,
            backtest_run_id=backtest_run_id,
            fail_code=fail_code,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )


class GetResearchTrial:
    def __init__(self, repository: ResearchTrialRepository) -> None:
        self._repository = repository

    async def execute(self, trial_id: str) -> ResearchTrial | None:
        return await self._repository.get_by_id(trial_id)


class GetInstrumentResearchSummary:
    def __init__(self, repository: ResearchTrialRepository) -> None:
        self._repository = repository

    async def execute(self, instrument_id: str) -> dict[str, Any] | None:
        return await self._repository.instrument_summary(instrument_id)


class GetLaboratoryResearchSummary:
    def __init__(self, repository: ResearchTrialRepository) -> None:
        self._repository = repository

    async def execute(self) -> dict[str, Any]:
        return await self._repository.laboratory_summary()


class GetLabHealth:
    """Q0.1 — cobertura métricas, zero-trades, campañas (sin Belief)."""

    def __init__(self, repository: ResearchTrialRepository) -> None:
        self._repository = repository

    async def execute(self) -> dict[str, Any]:
        return await self._repository.lab_health()
