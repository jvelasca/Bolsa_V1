"""M-6 (T-M6) — margen real en `_account_summary_from_portfolio`.

Cubre la fórmula canónica de los 3 campos de margen que antes estaban hardcoded
(margin_used/free_margin/margin_level_pct):
- `margin_used = Σ market_value / leverage` (solo posiciones con precio).
- `free_margin = equity − margin_used`, con `equity = total_equity` del portfolio.
- `margin_level_pct = equity / margin_used * 100`, `None` si margin_used == 0.

Fakes en memoria (patrón de `test_list_account_summaries.py`), sin DB.
"""

from __future__ import annotations

import pytest

from bolsa_application.accounts import _account_summary_from_portfolio
from bolsa_domain.entities.account import (
    AccountSummary,
    InvestmentAccount,
    InvestmentPortfolio,
)
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, Position


def _account(*, leverage: float = 1.0, margin_call_level_pct: float | None = 100.0) -> InvestmentAccount:
    return InvestmentAccount(
        id="acc-1",
        user_id="u-1",
        name="A",
        description=None,
        type="DEMO",
        status="active",
        currency="EUR",
        base_currency="EUR",
        initial_deposit=100_000.0,
        leverage=leverage,
        margin_call_level_pct=margin_call_level_pct,
        is_default=True,
        settings=None,
        strategy_definition_id=None,
        source_backtest_run_id=None,
        created_at="t",
        updated_at="t",
        last_activity_at=None,
    )


def _portfolio() -> InvestmentPortfolio:
    return InvestmentPortfolio(
        id="pf-1",
        account_id="acc-1",
        legacy_portfolio_id=None,
        name="P",
        description=None,
        strategy_tag=None,
        sort_order=0,
        is_default=True,
    )


def _position(*, market_value: float | None, last_price: float | None = None) -> Position:
    return Position(
        id="pos-1",
        instrument_id="inst-1",
        symbol="AAA",
        name="AAA",
        quantity=10.0,
        avg_cost=8.0,
        last_price=last_price,
        market_value=market_value,
        unrealized_pnl=None,
        unrealized_pnl_pct=None,
    )


def _summary(*, cash: float, positions: list[Position], equity: float) -> PortfolioSummary:
    return PortfolioSummary(
        portfolio=Portfolio(id="pf-1", name="P", currency="EUR", cash=cash),
        positions=positions,
        total_market_value=sum(mv for mv in (pos.market_value for pos in positions) if mv is not None),
        total_cost=0.0,
        total_unrealized_pnl=0.0,
        total_equity=equity,
    )


def _build(
    *, leverage: float = 1.0, positions: list[Position], equity: float, cash: float
) -> AccountSummary:
    return _account_summary_from_portfolio(
        account=_account(leverage=leverage),
        default_portfolio=_portfolio(),
        portfolio_summary=_summary(cash=cash, positions=positions, equity=equity),
    )


def test_margin_no_positions() -> None:
    """Caso A: sin posiciones → margin_used=0, free_margin=equity, margin_level=None."""
    summary = _build(positions=[], equity=1000.0, cash=1000.0)

    assert summary.margin_used == 0.0
    assert summary.free_margin == pytest.approx(1000.0)  # equity − 0
    assert summary.margin_level_pct is None
    assert summary.cash == 1000.0


def test_margin_single_position() -> None:
    """Caso B: una posición con market_value conocido → margin_used = mv/leverage."""
    summary = _build(
        leverage=2.0,
        positions=[_position(market_value=200.0, last_price=20.0)],
        equity=1200.0,  # cash 1000 + mv 200
        cash=1000.0,
    )

    assert summary.margin_used == pytest.approx(100.0)  # 200 / 2
    assert summary.free_margin == pytest.approx(1100.0)  # 1200 − 100
    assert summary.margin_level_pct == pytest.approx(1200.0)  # equity/margin_used*100


def test_margin_two_positions_leverage_gt_one() -> None:
    """Caso C: leverage>1 con dos posiciones → margin_used = Σmv/leverage, level>0."""
    summary = _build(
        leverage=3.0,
        positions=[
            _position(market_value=300.0, last_price=10.0),
            _position(market_value=600.0, last_price=20.0),
        ],
        equity=1900.0,  # cash 1000 + 300 + 600
        cash=1000.0,
    )

    assert summary.margin_used == pytest.approx(300.0)  # (300+600)/3
    assert summary.free_margin == pytest.approx(1600.0)  # 1900 − 300
    assert summary.margin_level_pct == pytest.approx(1900.0 / 300.0 * 100)
    assert summary.margin_level_pct is not None
    assert summary.margin_level_pct > 0


def test_margin_position_without_price_does_not_count() -> None:
    """Caso D: posición sin precio (market_value=None) NO suma a margin_used."""
    summary = _build(
        positions=[_position(market_value=None, last_price=None)],
        equity=1000.0,  # la posición sin precio no aporta equity
        cash=1000.0,
    )

    assert summary.margin_used == 0.0
    assert summary.free_margin == pytest.approx(1000.0)
    assert summary.margin_level_pct is None


def test_margin_mixed_positions_only_count_priced() -> None:
    """Caso D': posición sin precio ignorada, con otra con precio sí suma."""
    summary = _build(
        leverage=1.0,
        positions=[
            _position(market_value=None, last_price=None),
            _position(market_value=80.0, last_price=8.0),
        ],
        equity=1080.0,  # cash 1000 + 80 (solo la con precio)
        cash=1000.0,
    )

    assert summary.margin_used == pytest.approx(80.0)
    assert summary.free_margin == pytest.approx(1000.0)  # 1080 − 80
    assert summary.margin_level_pct == pytest.approx(1080.0 / 80.0 * 100)


# Caso E: guard leverage==0 → no divide por cero
def test_margin_leverage_zero_guard() -> None:
    summary = _build(leverage=0.0, positions=[_position(market_value=100.0, last_price=10.0)], equity=1100.0, cash=1000.0)

    assert summary.margin_used == 0.0
    assert summary.free_margin == pytest.approx(1100.0)  # equity − 0
    assert summary.margin_level_pct is None
