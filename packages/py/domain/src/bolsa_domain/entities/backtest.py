from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class BacktestRun:
    id: str
    instrument_id: str
    symbol: str
    name: str
    strategy_type: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_count: int
    bar_count: int
    first_date: str
    last_date: str
    created_at: str
    timeframe: str = "1d"
    data_version: str | None = None
    commission_bps: int = 0
    slippage_bps: int = 0
    manifest: dict[str, Any] | None = None
    strategy_definition_id: str | None = None


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    id: str
    type: Literal["buy", "sell"]
    timestamp: str
    price: float
    quantity: float
    equity_after: float


@dataclass(frozen=True, slots=True)
class BacktestRunDetail(BacktestRun):
    trades: list[BacktestTrade] = field(default_factory=list)
