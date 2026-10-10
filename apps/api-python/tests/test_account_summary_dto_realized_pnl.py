"""F4 — contrato del P&L realizado agregado en el resumen de cuenta (DTO).

``total_realized_pnl`` viaja como ``totalRealizedPnl`` y es nullable: ``None`` (fuente no
disponible) se propaga hasta el DTO sin convertirse en 0.
"""

from __future__ import annotations

from bolsa_api.schemas.account_mappers import to_account_summary_dto
from bolsa_api.schemas.accounts import AccountSummaryDto
from bolsa_domain.entities.account import (
    AccountSummary,
    InvestmentAccount,
    InvestmentPortfolio,
)


def _account() -> InvestmentAccount:
    return InvestmentAccount(
        id="acc-1",
        user_id="u-1",
        name="A",
        description=None,
        type="simulated",
        status="active",
        currency="EUR",
        base_currency="EUR",
        initial_deposit=100_000.0,
        leverage=1.0,
        margin_call_level_pct=100.0,
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
        legacy_portfolio_id="legacy-1",
        name="P",
        description=None,
        strategy_tag=None,
        sort_order=0,
        is_default=True,
    )


def _summary(total_realized_pnl: float | None) -> AccountSummary:
    return AccountSummary(
        account=_account(),
        default_portfolio=_portfolio(),
        cash=10_000.0,
        total_market_value=0.0,
        total_cost=0.0,
        total_unrealized_pnl=0.0,
        total_equity=10_000.0,
        margin_used=0.0,
        free_margin=10_000.0,
        margin_level_pct=None,
        positions_count=0,
        total_realized_pnl=total_realized_pnl,
    )


def test_dto_publica_el_realizado_con_alias_camelcase() -> None:
    dto = to_account_summary_dto(_summary(94.5))
    assert dto.total_realized_pnl == 94.5
    assert dto.model_dump(by_alias=True)["totalRealizedPnl"] == 94.5


def test_dto_propaga_none_sin_fabricar_cero() -> None:
    dto = to_account_summary_dto(_summary(None))
    assert dto.total_realized_pnl is None
    dumped = dto.model_dump(by_alias=True)
    assert "totalRealizedPnl" in dumped
    assert dumped["totalRealizedPnl"] is None


def test_dto_field_es_opcional_para_no_romper_consumidores() -> None:
    # Esquema: `totalRealizedPnl` opcional/nullable (default None).
    field = AccountSummaryDto.model_fields["total_realized_pnl"]
    assert field.is_required() is False
