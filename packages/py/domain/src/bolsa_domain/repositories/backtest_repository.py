from typing import Any, Literal, Protocol

from bolsa_domain.entities.backtest import BacktestRun, BacktestRunDetail


class BacktestRepository(Protocol):
    async def list_runs(self, limit: int = 20) -> list[BacktestRun]: ...

    async def prune_runs(self, keep: int) -> int: ...

    async def get_run(self, run_id: str) -> BacktestRunDetail | None: ...

    async def save_run(
        self,
        *,
        instrument_id: str,
        strategy_type: str,
        initial_cash: float,
        final_equity: float,
        total_return_pct: float,
        max_drawdown_pct: float,
        trade_count: int,
        win_count: int,
        bar_count: int,
        first_date: str,
        last_date: str,
        trades: list[tuple[Literal["buy", "sell"], str, float, float, float]],
        timeframe: str = "1d",
        data_version: str | None = None,
        commission_bps: int = 0,
        slippage_bps: int = 0,
        manifest: dict[str, Any] | None = None,
        run_id: str | None = None,
        strategy_definition_id: str | None = None,
    ) -> BacktestRunDetail: ...
