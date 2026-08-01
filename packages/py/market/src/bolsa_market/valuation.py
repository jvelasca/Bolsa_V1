"""Valoración intrínseca simplificada — FIE F2.3 / F2.4 / F2.5.

Dos modelos deterministas (Python only; LLM no calcula):

1. **Graham Number** (`graham_number_v1`)
   ``sqrt(22.5 * EPS * BVPS)`` — valor por acción clásico.
   Upside vs precio implícito (mcap/shares o PE×EPS).

2. **DCF FCF 2 etapas** (`dcf_fcf_2stage_wacc_v1`)
   Horizonte 5 años de FCF creciendo a ``g`` (revenueGrowth acotado),
   terminal Gordon con ``g_term``, descuento ``r`` = WACC proxy por sector
   (`fund_wacc_sector_v1`). Fallback r=10% si sector desconocido.
   Trata FCF como cash libre a equity (simplificación documentada; no es
   FCFF−net debt completo). Si FCF≤0 o faltan inputs → null.

3. **DCF multi-escenario** (`dcf_scenarios_v1`) — F2.5
   bear / base / bull variando growth (±3pp) y WACC (±1pp).
   ``dcfEquityValue`` / ``dcfUpside`` siguen siendo el escenario **base**
   (gate y Composite no cambian de semántica).

Constantes versionadas: cambiar r/g_term/años/catálogo WACC/deltas ⇒ bump method.

@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
"""

from __future__ import annotations

from math import sqrt
from typing import Any

from bolsa_market.capm import compute_capm_cost_of_equity
from bolsa_market.wacc import (
    FUND_WACC_VERSION,
    WACC_SECTOR_DEFAULT,
    resolve_sector_wacc,
)

GRAHAM_METHOD = "graham_number_v1"
DCF_METHOD = "dcf_fcf_2stage_wacc_v1"
DCF_SCENARIOS_METHOD = "dcf_scenarios_v1"

# DCF assumptions (explicit — bump DCF_METHOD if changed)
DCF_HORIZON_YEARS = 5
DCF_DISCOUNT_RATE = WACC_SECTOR_DEFAULT
DCF_TERMINAL_GROWTH = 0.025
DCF_GROWTH_FLOOR = -0.05
DCF_GROWTH_CAP = 0.15
DCF_GROWTH_DEFAULT = 0.05

# F2.5 scenario deltas (bump DCF_SCENARIOS_METHOD if changed)
DCF_SCENARIO_GROWTH_DELTA = 0.03
DCF_SCENARIO_WACC_DELTA = 0.01


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def resolve_dcf_growth(revenue_growth: float | None) -> float:
    if revenue_growth is None:
        return DCF_GROWTH_DEFAULT
    return _clamp(float(revenue_growth), DCF_GROWTH_FLOOR, DCF_GROWTH_CAP)


def compute_graham_number(
    *,
    eps: float | None,
    book_value_per_share: float | None,
) -> tuple[float | None, str | None]:
    """Graham Number por acción. Requiere EPS>0 y BVPS>0."""
    if eps is None or book_value_per_share is None:
        return None, None
    if eps <= 0 or book_value_per_share <= 0:
        return None, None
    return round(sqrt(22.5 * eps * book_value_per_share), 4), GRAHAM_METHOD


def compute_price_per_share(
    *,
    market_cap: float | None,
    shares_outstanding: float | None,
    eps: float | None,
    trailing_pe: float | None,
) -> float | None:
    """Precio implícito para upside Graham/DCF por acción."""
    if (
        market_cap is not None
        and market_cap > 0
        and shares_outstanding is not None
        and shares_outstanding > 0
    ):
        return market_cap / shares_outstanding
    if eps is not None and eps > 0 and trailing_pe is not None and trailing_pe > 0:
        return eps * trailing_pe
    return None


def compute_graham_upside(
    *,
    graham_number: float | None,
    price_per_share: float | None,
) -> float | None:
    """(Graham − price) / price. Positivo = infravalorado vs Graham."""
    if graham_number is None or price_per_share is None or price_per_share <= 0:
        return None
    return round((graham_number - price_per_share) / price_per_share, 6)


def compute_dcf_fcf_2stage(
    *,
    free_cashflow: float | None,
    market_cap: float | None,
    revenue_growth: float | None,
    discount_rate: float = DCF_DISCOUNT_RATE,
    terminal_growth: float = DCF_TERMINAL_GROWTH,
    horizon_years: int = DCF_HORIZON_YEARS,
    method: str = DCF_METHOD,
) -> tuple[float | None, float | None, str | None]:
    """
    Returns ``(dcf_equity_value, dcf_upside, method)``.

    ``dcf_upside = (equity_value − marketCap) / marketCap``.
    """
    if (
        free_cashflow is None
        or free_cashflow <= 0
        or market_cap is None
        or market_cap <= 0
        or discount_rate <= terminal_growth
        or horizon_years < 1
    ):
        return None, None, None

    g = resolve_dcf_growth(revenue_growth)

    pv_explicit = 0.0
    fcf_t = float(free_cashflow)
    for year in range(1, horizon_years + 1):
        fcf_t = fcf_t * (1.0 + g)
        pv_explicit += fcf_t / ((1.0 + discount_rate) ** year)

    fcf_terminal = fcf_t * (1.0 + terminal_growth)
    terminal_value = fcf_terminal / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / ((1.0 + discount_rate) ** horizon_years)

    equity_value = pv_explicit + pv_terminal
    upside = (equity_value - market_cap) / market_cap
    return round(equity_value, 2), round(upside, 6), method


def _scenario_leg(
    *,
    free_cashflow: float,
    market_cap: float,
    growth: float,
    wacc: float,
    terminal_growth: float,
) -> dict[str, Any] | None:
    value, upside, _ = compute_dcf_fcf_2stage(
        free_cashflow=free_cashflow,
        market_cap=market_cap,
        revenue_growth=growth,
        discount_rate=wacc,
        terminal_growth=terminal_growth,
        method=DCF_METHOD,
    )
    if value is None or upside is None:
        return None
    return {
        "equityValue": value,
        "upside": upside,
        "growth": round(growth, 4),
        "wacc": round(wacc, 4),
    }


def compute_dcf_scenarios(
    *,
    free_cashflow: float | None,
    market_cap: float | None,
    revenue_growth: float | None,
    discount_rate: float,
    terminal_growth: float = DCF_TERMINAL_GROWTH,
) -> dict[str, Any] | None:
    """
    bear / base / bull. Null si el base no es computable.

    - bear: g−3pp, wacc+1pp
    - base: g, wacc
    - bull: g+3pp, wacc−1pp (wacc floor = g_term+2pp)
    """
    if (
        free_cashflow is None
        or free_cashflow <= 0
        or market_cap is None
        or market_cap <= 0
        or discount_rate <= terminal_growth
    ):
        return None

    base_g = resolve_dcf_growth(revenue_growth)
    wacc_floor = terminal_growth + 0.02
    specs = (
        ("bear", -DCF_SCENARIO_GROWTH_DELTA, DCF_SCENARIO_WACC_DELTA),
        ("base", 0.0, 0.0),
        ("bull", DCF_SCENARIO_GROWTH_DELTA, -DCF_SCENARIO_WACC_DELTA),
    )
    out: dict[str, Any] = {"method": DCF_SCENARIOS_METHOD}
    for name, g_delta, w_delta in specs:
        g = _clamp(base_g + g_delta, DCF_GROWTH_FLOOR, DCF_GROWTH_CAP)
        w = max(float(discount_rate) + w_delta, wacc_floor)
        leg = _scenario_leg(
            free_cashflow=float(free_cashflow),
            market_cap=float(market_cap),
            growth=g,
            wacc=w,
            terminal_growth=terminal_growth,
        )
        if leg is None:
            return None
        out[name] = leg
    return out


def resolve_dcf_discount_rate(
    *,
    sector: str | None,
    beta: float | None = None,
) -> tuple[float, str, float | None, dict[str, Any] | None]:
    """
    Prefiere CAPM si hay beta; si no, WACC sector.
    Returns ``(discount, method, beta_used, capm_meta)``.
    ``capm_meta`` incluye ``rf`` / ``erp`` cuando aplica CAPM (para Tarjeta Valor).
    """
    ke, capm_method, meta = compute_capm_cost_of_equity(beta)
    if ke is not None and capm_method is not None and meta is not None:
        discount = ke if ke > DCF_TERMINAL_GROWTH else DCF_TERMINAL_GROWTH + 0.02
        return discount, capm_method, float(meta["beta"]), meta

    _known, wacc, _sector_key, wacc_method = resolve_sector_wacc(sector)
    discount = wacc if wacc > DCF_TERMINAL_GROWTH else DCF_TERMINAL_GROWTH + 0.02
    return discount, wacc_method if wacc_method else FUND_WACC_VERSION, None, None


def compute_valuation_from_yahoo_fields(
    *,
    market_cap: float | None,
    free_cashflow: float | None,
    revenue_growth: float | None,
    trailing_pe: float | None,
    trailing_eps: float | None,
    book_value_per_share: float | None,
    shares_outstanding: float | None,
    sector: str | None = None,
    beta: float | None = None,
) -> dict[str, Any]:
    """Bundle derived valuation fields for the fundamentals snapshot."""
    graham, graham_method = compute_graham_number(
        eps=trailing_eps,
        book_value_per_share=book_value_per_share,
    )
    price = compute_price_per_share(
        market_cap=market_cap,
        shares_outstanding=shares_outstanding,
        eps=trailing_eps,
        trailing_pe=trailing_pe,
    )
    graham_upside = compute_graham_upside(graham_number=graham, price_per_share=price)

    discount, wacc_method, beta_used, capm_meta = resolve_dcf_discount_rate(
        sector=sector, beta=beta
    )

    dcf_value, dcf_upside, dcf_method = compute_dcf_fcf_2stage(
        free_cashflow=free_cashflow,
        market_cap=market_cap,
        revenue_growth=revenue_growth,
        discount_rate=discount,
        method=DCF_METHOD,
    )
    scenarios = compute_dcf_scenarios(
        free_cashflow=free_cashflow,
        market_cap=market_cap,
        revenue_growth=revenue_growth,
        discount_rate=discount,
    )

    return {
        "grahamNumber": graham,
        "grahamMethod": graham_method,
        "grahamUpside": graham_upside,
        "beta": beta_used if beta_used is not None else (
            float(beta) if beta is not None and float(beta) > 0 else None
        ),
        "wacc": round(discount, 4),
        "waccMethod": wacc_method,
        "capmRf": float(capm_meta["rf"]) if capm_meta else None,
        "capmErp": float(capm_meta["erp"]) if capm_meta else None,
        "dcfEquityValue": dcf_value,
        "dcfUpside": dcf_upside,
        "dcfMethod": dcf_method,
        "dcfScenarios": scenarios,
    }
