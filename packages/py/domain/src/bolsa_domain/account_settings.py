from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommissionPresetId = Literal["standard_es", "xtb_zero_stock", "ibkr_tiered", "custom", "none"]
TaxJurisdiction = Literal["ES", "EU_OTHER", "US", "CUSTOM"]
CostBasisMethod = Literal["fifo", "average"]


@dataclass(frozen=True, slots=True)
class CommissionProfile:
    preset_id: str
    label: str
    stock_commission_pct: float
    stock_commission_min: float
    stock_commission_max: float | None
    vat_on_commission_pct: float
    fx_conversion_pct: float
    custody_annual_pct: float | None


@dataclass(frozen=True, slots=True)
class TaxProfile:
    jurisdiction: str
    cost_basis_method: str
    stamp_duty_buy_pct: float
    dividend_withholding_pct: float
    capital_gains_tax_pct: float | None
    fiscal_year_start_month: int


@dataclass(frozen=True, slots=True)
class AccountSettings:
    """Preferencias de cuenta (comisiones/fiscal). El perfil inversor vive en investor_profiles."""

    commission: CommissionProfile
    tax: TaxProfile
    notes: str | None


@dataclass(frozen=True, slots=True)
class TradeFeeBreakdown:
    commission: float
    vat_on_commission: float
    stamp_duty: float
    fx_conversion: float
    total: float
    currency: str


COMMISSION_PRESETS: dict[str, CommissionProfile] = {
    "none": CommissionProfile(
        preset_id="none",
        label="Sin comisiones",
        stock_commission_pct=0.0,
        stock_commission_min=0.0,
        stock_commission_max=None,
        vat_on_commission_pct=0.0,
        fx_conversion_pct=0.0,
        custody_annual_pct=None,
    ),
    "xtb_zero_stock": CommissionProfile(
        preset_id="xtb_zero_stock",
        label="Zero comisión acciones (spread)",
        stock_commission_pct=0.0,
        stock_commission_min=0.0,
        stock_commission_max=None,
        vat_on_commission_pct=0.0,
        fx_conversion_pct=0.5,
        custody_annual_pct=None,
    ),
    "standard_es": CommissionProfile(
        preset_id="standard_es",
        label="Broker estándar ES",
        stock_commission_pct=0.1,
        stock_commission_min=1.0,
        stock_commission_max=29.0,
        vat_on_commission_pct=21.0,
        fx_conversion_pct=0.5,
        custody_annual_pct=0.2,
    ),
    "ibkr_tiered": CommissionProfile(
        preset_id="ibkr_tiered",
        label="IBKR tiered (EU)",
        stock_commission_pct=0.05,
        stock_commission_min=1.25,
        stock_commission_max=None,
        vat_on_commission_pct=21.0,
        fx_conversion_pct=0.002,
        custody_annual_pct=None,
    ),
    "custom": CommissionProfile(
        preset_id="custom",
        label="Personalizado",
        stock_commission_pct=0.1,
        stock_commission_min=1.0,
        stock_commission_max=None,
        vat_on_commission_pct=21.0,
        fx_conversion_pct=0.5,
        custody_annual_pct=None,
    ),
}


TAX_PRESETS: dict[str, TaxProfile] = {
    "ES": TaxProfile(
        jurisdiction="ES",
        cost_basis_method="fifo",
        stamp_duty_buy_pct=0.2,
        dividend_withholding_pct=19.0,
        capital_gains_tax_pct=19.0,
        fiscal_year_start_month=1,
    ),
    "EU_OTHER": TaxProfile(
        jurisdiction="EU_OTHER",
        cost_basis_method="fifo",
        stamp_duty_buy_pct=0.0,
        dividend_withholding_pct=15.0,
        capital_gains_tax_pct=None,
        fiscal_year_start_month=1,
    ),
    "US": TaxProfile(
        jurisdiction="US",
        cost_basis_method="fifo",
        stamp_duty_buy_pct=0.0,
        dividend_withholding_pct=30.0,
        capital_gains_tax_pct=None,
        fiscal_year_start_month=1,
    ),
    "CUSTOM": TaxProfile(
        jurisdiction="CUSTOM",
        cost_basis_method="fifo",
        stamp_duty_buy_pct=0.0,
        dividend_withholding_pct=0.0,
        capital_gains_tax_pct=None,
        fiscal_year_start_month=1,
    ),
}


def default_account_settings(
    commission_preset_id: str = "standard_es",
    jurisdiction: str = "ES",
) -> AccountSettings:
    commission = COMMISSION_PRESETS.get(commission_preset_id, COMMISSION_PRESETS["standard_es"])
    tax = TAX_PRESETS.get(jurisdiction, TAX_PRESETS["ES"])
    return AccountSettings(commission=commission, tax=tax, notes=None)


def calculate_trade_fees(
    notional: float,
    side: Literal["buy", "sell"],
    settings: AccountSettings,
    *,
    is_fx_conversion: bool = False,
    currency: str = "EUR",
) -> TradeFeeBreakdown:
    profile = settings.commission
    tax = settings.tax

    commission = 0.0
    if profile.stock_commission_pct > 0 or profile.stock_commission_min > 0:
        commission = (notional * profile.stock_commission_pct) / 100.0
        commission = max(commission, profile.stock_commission_min)
        if profile.stock_commission_max is not None:
            commission = min(commission, profile.stock_commission_max)

    vat = (commission * profile.vat_on_commission_pct) / 100.0
    stamp = (
        (notional * tax.stamp_duty_buy_pct) / 100.0
        if side == "buy" and tax.stamp_duty_buy_pct > 0
        else 0.0
    )
    fx = (
        (notional * profile.fx_conversion_pct) / 100.0
        if is_fx_conversion and profile.fx_conversion_pct > 0
        else 0.0
    )
    total = commission + vat + stamp + fx
    return TradeFeeBreakdown(
        commission=commission,
        vat_on_commission=vat,
        stamp_duty=stamp,
        fx_conversion=fx,
        total=total,
        currency=currency,
    )


def settings_to_dict(settings: AccountSettings) -> dict:
    return {
        "commission": {
            "presetId": settings.commission.preset_id,
            "label": settings.commission.label,
            "stockCommissionPct": settings.commission.stock_commission_pct,
            "stockCommissionMin": settings.commission.stock_commission_min,
            "stockCommissionMax": settings.commission.stock_commission_max,
            "vatOnCommissionPct": settings.commission.vat_on_commission_pct,
            "fxConversionPct": settings.commission.fx_conversion_pct,
            "custodyAnnualPct": settings.commission.custody_annual_pct,
        },
        "tax": {
            "jurisdiction": settings.tax.jurisdiction,
            "costBasisMethod": settings.tax.cost_basis_method,
            "stampDutyBuyPct": settings.tax.stamp_duty_buy_pct,
            "dividendWithholdingPct": settings.tax.dividend_withholding_pct,
            "capitalGainsTaxPct": settings.tax.capital_gains_tax_pct,
            "fiscalYearStartMonth": settings.tax.fiscal_year_start_month,
        },
        "notes": settings.notes,
    }


def settings_from_dict(data: dict | None) -> AccountSettings:
    if not data:
        return default_account_settings()
    commission_raw = data.get("commission") or {}
    tax_raw = data.get("tax") or {}
    preset_id = commission_raw.get("presetId", "standard_es")
    base_commission = COMMISSION_PRESETS.get(preset_id)
    if base_commission and preset_id != "custom":
        commission = base_commission
    else:
        commission = CommissionProfile(
            preset_id=preset_id if preset_id else "custom",
            label=commission_raw.get("label", "Personalizado"),
            stock_commission_pct=float(commission_raw.get("stockCommissionPct", 0.1)),
            stock_commission_min=float(commission_raw.get("stockCommissionMin", 1)),
            stock_commission_max=commission_raw.get("stockCommissionMax"),
            vat_on_commission_pct=float(commission_raw.get("vatOnCommissionPct", 21)),
            fx_conversion_pct=float(commission_raw.get("fxConversionPct", 0)),
            custody_annual_pct=commission_raw.get("custodyAnnualPct"),
        )
    jurisdiction = tax_raw.get("jurisdiction", "ES")
    base_tax = TAX_PRESETS.get(jurisdiction, TAX_PRESETS["ES"])
    tax = TaxProfile(
        jurisdiction=jurisdiction,
        cost_basis_method=tax_raw.get("costBasisMethod", base_tax.cost_basis_method),
        stamp_duty_buy_pct=float(tax_raw.get("stampDutyBuyPct", base_tax.stamp_duty_buy_pct)),
        dividend_withholding_pct=float(
            tax_raw.get("dividendWithholdingPct", base_tax.dividend_withholding_pct),
        ),
        capital_gains_tax_pct=tax_raw.get("capitalGainsTaxPct", base_tax.capital_gains_tax_pct),
        fiscal_year_start_month=int(
            tax_raw.get("fiscalYearStartMonth", base_tax.fiscal_year_start_month),
        ),
    )
    return AccountSettings(
        commission=commission,
        tax=tax,
        notes=data.get("notes"),
    )
