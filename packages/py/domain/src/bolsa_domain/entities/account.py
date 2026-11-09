"""Entidad de dominio cuenta de inversión y cartera — sin dependencias externas.

Fase 2.3a (auditoría externa): los campos **monetarios** son ``Decimal`` y se normalizan
en ``__post_init__``. Un llamador que siga pasando ``float`` obtiene ``Decimal(str(valor))``
— la repr decimal del ``float``, no su expansión binaria exacta (``Decimal(0.1)`` es
0.10000000000000000555...). El redondeo a céntimos es explícito (``quantize_money``). Los
ratios (``leverage``, ``*_pct``) siguen en ``float``: no se suman en un libro. Ver
``packages/py/domain/tests/test_money_decimal_guard.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from bolsa_domain.account_settings import AccountSettings
from bolsa_domain.money import coerce_money_fields


@dataclass(frozen=True, slots=True)
class InvestmentAccount:
    id: str
    user_id: str | None
    name: str
    description: str | None
    type: str
    status: str
    currency: str
    base_currency: str
    initial_deposit: Decimal
    leverage: float
    margin_call_level_pct: float | None
    is_default: bool
    settings: AccountSettings | None
    strategy_definition_id: str | None
    source_backtest_run_id: str | None
    created_at: str
    updated_at: str
    last_activity_at: str | None
    active_profile_id: str | None = None
    # Lab evidence snapshot at paper deploy (settings_json.labEvidence).
    lab_evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        coerce_money_fields(self, "initial_deposit")


@dataclass(frozen=True, slots=True)
class InvestmentPortfolio:
    id: str
    account_id: str
    legacy_portfolio_id: str | None
    name: str
    description: str | None
    strategy_tag: str | None
    sort_order: int
    is_default: bool


@dataclass(frozen=True, slots=True)
class AccountScope:
    account: InvestmentAccount
    portfolio: InvestmentPortfolio
    legacy_portfolio_id: str


@dataclass(frozen=True, slots=True)
class AccountSummary:
    account: InvestmentAccount
    default_portfolio: InvestmentPortfolio
    cash: Decimal
    total_market_value: Decimal
    total_cost: Decimal
    total_unrealized_pnl: Decimal
    total_equity: Decimal
    margin_used: Decimal
    free_margin: Decimal
    margin_level_pct: float | None
    positions_count: int
    # F4: P&L realizado AGREGADO de todo el historial (misma base canónica que el tax
    # report). ``None`` = no medido / fuente no disponible → «Sin dato todavía», NUNCA 0.
    # Default ``None`` para no romper constructores existentes.
    total_realized_pnl: Decimal | None = None

    def __post_init__(self) -> None:
        coerce_money_fields(
            self,
            "cash",
            "total_market_value",
            "total_cost",
            "total_unrealized_pnl",
            "total_equity",
            "margin_used",
            "free_margin",
            "total_realized_pnl",
        )


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    id: str
    account_id: str
    portfolio_id: str | None
    type: str
    amount: Decimal
    currency: str
    balance_after: Decimal
    instrument_id: str | None
    symbol: str | None
    quantity: float | None
    price: Decimal | None
    reference_type: str | None
    reference_id: str | None
    description: str | None
    executed_at: str

    def __post_init__(self) -> None:
        coerce_money_fields(self, "amount", "balance_after", "price")


@dataclass(frozen=True, slots=True)
class CashMovementResult:
    id: str
    account_id: str
    portfolio_id: str
    kind: str
    amount: Decimal
    currency: str
    balance_after: Decimal
    executed_at: str
    description: str | None

    def __post_init__(self) -> None:
        coerce_money_fields(self, "amount", "balance_after")


@dataclass(frozen=True, slots=True)
class CustodyObligation:
    """Obligaciones de custodia pendiente/aplicada de una cuenta, MULTI-periodo.

    Representa UNA obligación por (cuenta, año): ``UNIQUE(account_id, period)``.
    Un PENDING de un año anterior (p. ej. 2026) pervive aunque se genere el cargo de
    2027 — no se sobrescribe. ``status`` solo ``PENDING`` | ``APPLIED``; ``outstanding``
    = importe pendiente; ``total_fee`` = importe total original. ``id`` (PK) y
    ``created_at``/``updated_at`` son opcionales (ausentes en flujos de solo lectura).
    """

    account_id: str
    period: str
    status: str
    outstanding: Decimal
    total_fee: Decimal
    id: int | None = None
    created_at: object | None = None
    updated_at: object | None = None

    def __post_init__(self) -> None:
        coerce_money_fields(self, "outstanding", "total_fee")
