"""Catálogo canónico de comisiones/fiscal y contrato de ``calculate_trade_fees``.

Fija en el DOMINIO los números que el frontend replica en
``packages/shared/src/account-settings.ts`` (``COMMISSION_PRESETS`` / ``TAX_PRESETS``).
Si estos valores cambian aquí, el preset TS debe cambiar a la vez o el wizard
enviará al servidor un perfil distinto del que la UI muestra.

Cierra además el borde que no tenía prueba: la cuantización a 4 decimales
``ROUND_HALF_UP`` y la semántica compra/venta del impuesto de transmisiones.
"""

import pytest

from bolsa_domain.account_settings import (
    COMMISSION_PRESETS,
    TAX_PRESETS,
    calculate_trade_fees,
    default_account_settings,
    settings_from_dict,
    settings_to_dict,
)


def _es_settings():
    return default_account_settings("standard_es", "ES")


def test_commission_catalog_is_the_contract_the_frontend_mirrors() -> None:
    standard = COMMISSION_PRESETS["standard_es"]
    assert standard.stock_commission_pct == pytest.approx(0.1)
    assert standard.stock_commission_min == pytest.approx(1.0)
    assert standard.stock_commission_max == pytest.approx(29.0)
    assert standard.vat_on_commission_pct == pytest.approx(21.0)
    assert standard.fx_conversion_pct == pytest.approx(0.5)
    assert standard.custody_annual_pct == pytest.approx(0.2)

    xtb = COMMISSION_PRESETS["xtb_zero_stock"]
    assert xtb.stock_commission_pct == 0.0
    assert xtb.fx_conversion_pct == pytest.approx(0.5)

    ibkr = COMMISSION_PRESETS["ibkr_tiered"]
    assert ibkr.stock_commission_min == pytest.approx(1.25)
    assert ibkr.fx_conversion_pct == pytest.approx(0.002)

    none = COMMISSION_PRESETS["none"]
    assert none.stock_commission_pct == 0.0
    assert none.stock_commission_max is None
    assert none.vat_on_commission_pct == 0.0


def test_tax_catalog_defines_the_es_capital_gains_projection() -> None:
    """COM-D1: el preset TS enviaba ``capitalGainsTaxPct: null`` frente al 19 % de aquí.

    El dominio es la fuente de verdad; este test lo deja fijado para que la paridad
    del frontend sea verificable y no una convención verbal.
    """
    es = TAX_PRESETS["ES"]
    assert es.cost_basis_method == "fifo"
    assert es.stamp_duty_buy_pct == pytest.approx(0.2)
    assert es.dividend_withholding_pct == pytest.approx(19.0)
    assert es.capital_gains_tax_pct == pytest.approx(19.0)
    assert es.fiscal_year_start_month == 1

    assert TAX_PRESETS["EU_OTHER"].dividend_withholding_pct == pytest.approx(15.0)
    assert TAX_PRESETS["US"].dividend_withholding_pct == pytest.approx(30.0)
    assert TAX_PRESETS["CUSTOM"].dividend_withholding_pct == 0.0
    for jurisdiction in ("EU_OTHER", "US", "CUSTOM"):
        assert TAX_PRESETS[jurisdiction].capital_gains_tax_pct is None


def test_fees_quantize_to_four_decimals_half_up_without_intermediate_rounding() -> None:
    """``1234.5678`` en ES: comisión/IVA/transmisiones y total con 4 decimales.

    El mismo caso está en ``packages/shared/src/account-settings.test.ts``: los dos
    lados deben dar exactamente estos números.
    """
    fees = calculate_trade_fees(1234.5678, "buy", _es_settings(), currency="EUR")
    assert fees.commission == pytest.approx(1.2346)
    assert fees.vat_on_commission == pytest.approx(0.2593)
    assert fees.stamp_duty == pytest.approx(2.4691)
    assert fees.fx_conversion == 0.0
    assert fees.total == pytest.approx(3.9630)
    assert fees.currency == "EUR"


def test_fees_apply_the_per_operation_minimum() -> None:
    fees = calculate_trade_fees(100, "buy", _es_settings())
    assert fees.commission == pytest.approx(1.0)
    assert fees.vat_on_commission == pytest.approx(0.21)
    assert fees.stamp_duty == pytest.approx(0.2)
    assert fees.total == pytest.approx(1.41)


def test_fees_apply_the_per_operation_maximum() -> None:
    fees = calculate_trade_fees(100_000, "buy", _es_settings())
    assert fees.commission == pytest.approx(29.0)
    assert fees.vat_on_commission == pytest.approx(6.09)
    assert fees.stamp_duty == pytest.approx(200.0)
    assert fees.total == pytest.approx(235.09)


def test_stamp_duty_is_charged_only_on_buys() -> None:
    buy = calculate_trade_fees(5000, "buy", _es_settings())
    sell = calculate_trade_fees(5000, "sell", _es_settings())
    assert buy.stamp_duty == pytest.approx(10.0)
    assert sell.stamp_duty == 0.0
    assert sell.total == pytest.approx(6.05)


def test_fx_conversion_is_opt_in() -> None:
    assert calculate_trade_fees(10_000, "buy", _es_settings()).fx_conversion == 0.0
    converted = calculate_trade_fees(
        10_000, "buy", _es_settings(), is_fx_conversion=True
    )
    assert converted.fx_conversion == pytest.approx(50.0)


def test_none_preset_still_charges_the_tax_jurisdiction_stamp_duty() -> None:
    """COM-D12: «sin comisiones» no es «sin impuestos».

    El impuesto de transmisiones pertenece al perfil fiscal; con ES se sigue
    cobrando el 0,2 % aunque el preset de comisión sea ``none``. La UI no puede
    prometer lo contrario.
    """
    fees = calculate_trade_fees(5000, "buy", default_account_settings("none", "ES"))
    assert fees.commission == 0.0
    assert fees.vat_on_commission == 0.0
    assert fees.fx_conversion == 0.0
    assert fees.stamp_duty == pytest.approx(10.0)
    assert fees.total == pytest.approx(10.0)


def test_settings_round_trip_preserves_the_capital_gains_projection() -> None:
    payload = settings_to_dict(_es_settings())
    assert payload["tax"]["capitalGainsTaxPct"] == pytest.approx(19.0)
    restored = settings_from_dict(payload)
    assert restored.tax.capital_gains_tax_pct == pytest.approx(19.0)
