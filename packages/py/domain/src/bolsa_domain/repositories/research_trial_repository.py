from typing import Any, Literal, Protocol

from bolsa_domain.entities.research_trial import ResearchTrial

ResearchTrialSort = Literal[
    "created_at",
    "sharpe",
    "pnl",
    "commission",
    "k_contribution",
]


class ResearchTrialRepository(Protocol):
    async def insert_trial(
        self,
        *,
        instrument_id: str,
        params: dict[str, Any],
        is_metrics: dict[str, Any],
        proposed_by: str,
        k_contribution: int = 1,
        hypothesis_id: str | None = None,
        research_question_id: str | None = None,
        backtest_run_id: str | None = None,
        optimization_run_id: str | None = None,
        strategy_definition_id: str | None = None,
        preset_key: str | None = None,
        strategy_name: str | None = None,
        blocks: dict[str, Any] | None = None,
        is_score: float | None = None,
        parent_trial_id: str | None = None,
        fail_code: str | None = None,
        manifest_ref: dict[str, Any] | None = None,
        trial_id: str | None = None,
    ) -> ResearchTrial: ...

    async def get_by_id(self, trial_id: str) -> ResearchTrial | None: ...

    async def set_hypothesis_id(
        self, trial_id: str, hypothesis_id: str | None
    ) -> ResearchTrial | None: ...

    async def list_trials(
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
    ) -> tuple[list[ResearchTrial], int]: ...

    async def sum_k_by_instrument(self, instrument_id: str) -> int: ...

    async def list_by_instrument(
        self,
        instrument_id: str,
        *,
        limit: int = 50,
    ) -> list[ResearchTrial]: ...

    async def instrument_summary(self, instrument_id: str) -> dict[str, Any] | None: ...

    async def laboratory_summary(self) -> dict[str, Any]: ...

    async def lab_health(self) -> dict[str, Any]: ...
