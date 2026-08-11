"""Entidad de dominio de cartera, posiciones y transacciones — sin dependencias externas."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Portfolio:
    id: str
    name: str
    currency: str
    cash: float


@dataclass(frozen=True, slots=True)
class Position:
    id: str
    instrument_id: str
    symbol: str
    name: str
    quantity: float
    avg_cost: float
    last_price: float | None
    market_value: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    portfolio: Portfolio
    positions: list[Position]
    total_market_value: float
    total_cost: float
    total_unrealized_pnl: float
    total_equity: float


@dataclass(frozen=True, slots=True)
class Transaction:
    id: str
    type: Literal["buy", "sell"]
    instrument_id: str
    symbol: str
    quantity: float
    price: float
    total: float
    executed_at: str


@dataclass(frozen=True, slots=True)
class TradeResult:
    transaction: Transaction
    summary: PortfolioSummary
