"""Entidad de dominio de cartera, posiciones y transacciones — sin dependencias externas.

Fase 2.3a (auditoría externa): dinero y precios en ``Decimal``, normalizados en
``__post_init__``. ``quantity`` es una cantidad de títulos: sigue en ``float`` porque todo
el motor de backtest trabaja en ``float`` y la cantidad no se suma en un libro de caja;
el notional se calcula en ``Decimal`` a partir de ella (``to_decimal(qty) * price``).
``unrealized_pnl_pct`` es un ratio: ``float``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from bolsa_domain.money import coerce_money_fields


@dataclass(frozen=True, slots=True)
class Portfolio:
    id: str
    name: str
    currency: str
    cash: Decimal

    def __post_init__(self) -> None:
        coerce_money_fields(self, "cash")


@dataclass(frozen=True, slots=True)
class Position:
    id: str
    instrument_id: str
    symbol: str
    name: str
    quantity: float
    avg_cost: Decimal
    last_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: float | None
    sector: str | None = None

    def __post_init__(self) -> None:
        coerce_money_fields(self, "avg_cost", "last_price", "market_value", "unrealized_pnl")


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    portfolio: Portfolio
    positions: list[Position]
    total_market_value: Decimal
    total_cost: Decimal
    total_unrealized_pnl: Decimal
    total_equity: Decimal

    def __post_init__(self) -> None:
        coerce_money_fields(
            self,
            "total_market_value",
            "total_cost",
            "total_unrealized_pnl",
            "total_equity",
        )


@dataclass(frozen=True, slots=True)
class Transaction:
    id: str
    type: Literal["buy", "sell"]
    instrument_id: str
    symbol: str
    quantity: float
    price: Decimal
    total: Decimal
    executed_at: str

    def __post_init__(self) -> None:
        coerce_money_fields(self, "price", "total")


@dataclass(frozen=True, slots=True)
class TradeResult:
    transaction: Transaction
    summary: PortfolioSummary
