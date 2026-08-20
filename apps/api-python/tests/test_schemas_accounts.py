"""Unit de DTOs financieros (R-9.4): invariantes estrictos sin tocar el wire."""

from math import nan

import pytest
from pydantic import ValidationError

from bolsa_api.schemas.accounts import (
    CommissionProfileDto,
    CreateInvestmentAccountDto,
)


def _min_commission_fields(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "preset_id": "standard_es",
        "label": "ES",
        "stock_commission_pct": 0.1,
        "stock_commission_min": 1,
        "stock_commission_max": 29,
        "vat_on_commission_pct": 21,
        "fx_conversion_pct": 0.5,
        "custody_annual_pct": 0.2,
    }
    base.update(overrides)
    return base


def _min_create_fields(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"name": "Cuenta test"}
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "overrides",
    [
        {"initial_deposit": -1},
        {"initial_deposit": 0.0, "leverage": 0},
        {"initial_deposit": 0.0, "leverage": -2},
        {"initial_deposit": 0.0, "margin_call_level_pct": -0.1},
    ],
)
def test_create_account_rejects_invalid_monetary_inputs(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CreateInvestmentAccountDto(**_min_create_fields(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"initial_deposit": nan},
        {"leverage": float("inf")},
    ],
)
def test_create_account_rejects_nan_and_inf(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CreateInvestmentAccountDto(**_min_create_fields(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"stock_commission_pct": -0.01},
        {"vat_on_commission_pct": -5},
        {"fx_conversion_pct": -1},
        {"custody_annual_pct": -0.1},
        {"stock_commission_max": -1},
    ],
)
def test_commission_rejects_negative_rates(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CommissionProfileDto(**_min_commission_fields(**overrides))


def test_commission_rejects_max_below_min() -> None:
    with pytest.raises(ValidationError):
        CommissionProfileDto(**_min_commission_fields(stock_commission_max=0.5))


def test_commission_rejects_nan_rate() -> None:
    with pytest.raises(ValidationError):
        CommissionProfileDto(**_min_commission_fields(stock_commission_pct=nan))


@pytest.mark.parametrize(
    "overrides",
    [
        {"initial_deposit": 0, "leverage": 1, "margin_call_level_pct": 0},
        {"initial_deposit": 0.0, "leverage": 10.0, "margin_call_level_pct": 0},
    ],
)
def test_create_account_accepts_boundary_valid(overrides: dict[str, object]) -> None:
    dto = CreateInvestmentAccountDto(**_min_create_fields(**overrides))
    assert dto.initial_deposit >= 0
    assert dto.leverage > 0
    assert dto.margin_call_level_pct is not None
    assert dto.margin_call_level_pct >= 0


def test_create_account_accepts_zero_limits() -> None:
    dto = CreateInvestmentAccountDto(
        **_min_create_fields(
            initial_deposit=0, leverage=10.0, margin_call_level_pct=0
        )
    )
    assert dto.initial_deposit == 0
    assert dto.leverage == 10.0
    assert dto.margin_call_level_pct == 0


def test_commission_accepts_zero_rates_and_max_equal_to_min() -> None:
    dto = CommissionProfileDto(
        **_min_commission_fields(
            stock_commission_pct=0,
            stock_commission_min=0,
            stock_commission_max=0,
            vat_on_commission_pct=0,
            fx_conversion_pct=0,
            custody_annual_pct=0,
        )
    )
    assert dto.stock_commission_pct == 0
    assert dto.stock_commission_max == dto.stock_commission_min


def test_commission_allows_none_optional_fields() -> None:
    dto = CommissionProfileDto(
        **_min_commission_fields(stock_commission_max=None, custody_annual_pct=None)
    )
    assert dto.stock_commission_max is None
    assert dto.custody_annual_pct is None


def test_create_account_allows_none_optional_fields() -> None:
    dto = CreateInvestmentAccountDto(**_min_create_fields(margin_call_level_pct=None))
    assert dto.margin_call_level_pct is None


def test_wire_accepted_by_alias_and_field_name() -> None:
    # alias wire: initialDeposit
    by_alias = CreateInvestmentAccountDto(**{"name": "x", "initialDeposit": 100000})
    assert by_alias.initial_deposit == 100_000
    # populate_by_name: initial_deposit
    by_name = CreateInvestmentAccountDto(**{"name": "x", "initial_deposit": 50_000})
    assert by_name.initial_deposit == 50_000
    # serializa igual (el valor no cambia con la vía)
    assert by_alias.initial_deposit == 100_000
    assert by_name.initial_deposit == 50_000


def test_commission_wire_serializes_by_alias() -> None:
    dto = CommissionProfileDto(**_min_commission_fields())
    dumped = dto.model_dump(by_alias=True)
    assert dumped["stockCommissionMin"] == 1
    assert dumped["stockCommissionMax"] == 29
