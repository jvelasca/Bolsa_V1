"""Risk Engine — encaje de cesta (PortfolioFit v1) a nivel check_opening.

El Risk de cesta debe VETAR (fail-closed) cuando la puesta propuesta —sumada a las
posiciones existentes tras el as-if fill— supera el límite de concentración por
activo (`max_portfolio_concentration_pct`) o por sector (`max_sector_exposure_pct`).

profile=None → política por defecto `moderate`:
  max_portfolio_concentration_pct = 12.0
  max_sector_exposure_pct = 30.0
"""

from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_application.risk_engine import RiskDecision, check_opening


def _open(
    *,
    instrument_id: str,
    existing: list[BasketPosition] | None,
    quantity: float,
    sector: str | None = None,
    equity: float = 200.0,
) -> RiskDecision:
    return check_opening(
        profile=None,
        instrument_id=instrument_id,
        symbol=instrument_id.upper(),
        trade_type="buy",
        quantity=quantity,
        price=1.0,
        signal_kind="entry_long",
        equity=equity,
        portfolio_positions=existing,
        proposal_sector=sector,
    )


def test_basket_asset_concentration_denies() -> None:
    # La puesta (instrumento "a", notional 4) + posición existente "a" (25) = 29/200
    # = 14.5% > 12% (moderate max_portfolio_concentration_pct) → DENY por concentración.
    existing = [
        BasketPosition("a", 25.0, "tech"),
        BasketPosition("b", 20.0, "health"),
    ]
    d = _open(instrument_id="a", existing=existing, quantity=4)
    assert d.verdict == "DENY"
    assert d.guard is not None and d.guard.allowed is False
    assert any("Concentración cesta superada" in r for r in d.reasons)


def test_basket_sector_exposure_denies() -> None:
    # Cada activo ≤ 12% (no viola concentración por activo) pero el SECTOR "tech"
    # tras el fill = (22*4 + 4)/200 = 46% > 30% (moderate max_sector_exposure_pct).
    existing = [
        BasketPosition("t1", 22.0, "tech"),
        BasketPosition("t2", 22.0, "tech"),
        BasketPosition("t3", 22.0, "tech"),
        BasketPosition("t4", 22.0, "tech"),
        BasketPosition("h1", 20.0, "health"),
        BasketPosition("h2", 20.0, "health"),
        BasketPosition("e1", 20.0, "energy"),
        BasketPosition("c1", 10.0, "cons"),
    ]
    d = _open(instrument_id="new", existing=existing, quantity=4, sector="tech")
    assert d.verdict == "DENY"
    assert d.guard is not None and d.guard.allowed is False
    assert any("Exposición sector superada" in r for r in d.reasons)


def test_basket_no_violation_allows() -> None:
    # Puesta pequeña y diversificada: ni concentración por activo (>12) ni por sector
    # (>30) se superan tras el fill → ALLOW (sin DENY por estas reglas).
    existing = [
        BasketPosition("a", 4.0, "tech"),
        BasketPosition("b", 4.0, "health"),
        BasketPosition("c", 4.0, "energy"),
        BasketPosition("d", 4.0, "cons"),
    ]
    d = _open(
        instrument_id="new",
        existing=existing,
        quantity=4,
        sector="materials",
    )
    assert d.verdict == "ALLOW"
    assert d.guard is not None and d.guard.allowed is True
    assert all(
        "Concentración cesta superada" not in r and "Exposición sector superada" not in r
        for r in d.reasons
    )
