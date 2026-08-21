"""Entidad de dominio cuenta de inversión y cartera — sin dependencias externas."""
from dataclasses import dataclass
from typing import Any


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
    initial_deposit: float
    leverage: float
    margin_call_level_pct: float | None
    is_default: bool
    settings: "AccountSettings | None"
    strategy_definition_id: str | None
    source_backtest_run_id: str | None
    created_at: str
    updated_at: str
    last_activity_at: str | None
    active_profile_id: str | None = None
    # Lab evidence snapshot at paper deploy (settings_json.labEvidence).
    lab_evidence: dict[str, Any] | None = None


from bolsa_domain.account_settings import AccountSettings  # noqa: E402


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
    cash: float
    total_market_value: float
    total_cost: float
    total_unrealized_pnl: float
    total_equity: float
    margin_used: float
    free_margin: float
    margin_level_pct: float | None
    positions_count: int


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    id: str
    account_id: str
    portfolio_id: str | None
    type: str
    amount: float
    currency: str
    balance_after: float
    instrument_id: str | None
    symbol: str | None
    quantity: float | None
    price: float | None
    reference_type: str | None
    reference_id: str | None
    description: str | None
    executed_at: str


@dataclass(frozen=True, slots=True)
class CashMovementResult:
    id: str
    account_id: str
    portfolio_id: str
    kind: str
    amount: float
    currency: str
    balance_after: float
    executed_at: str
    description: str | None


@dataclass(frozen=True, slots=True)
class CustodyObligation:
    """Obligación de custodia pendiente/aplicada de una cuenta (ADR 026, F4a).

    Una fila por cuenta (PK ``account_id``): el ``period`` en curso se sobrescribe en
    cada ciclo anual re-cobrable. ``status`` solo ``PENDING`` | ``APPLIED``.
    """

    account_id: str
    period: str
    status: str
    outstanding: float
    total_fee: float
