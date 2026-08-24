"""PortfolioFit v1 — encaje de cesta (función pura)."""

from bolsa_analytics.cognitive.portfolio_fit import (
    BasketPosition,
    compute_portfolio_fit,
)


def test_weight_by_asset_after_as_if_fill() -> None:
    signal = compute_portfolio_fit(
        proposal=BasketPosition("aaa", 20.0, "tech"),
        existing=[
            BasketPosition("bbb", 60.0, "health"),
            BasketPosition("ccc", 20.0, "tech"),
        ],
        equity=100.0,
    )
    assert signal.max_asset_weight_pct == 60.0  # bbb 60/100
    # sector health = 60 (bbb) > sector tech = 40 (aaa+ccc) → el máximo es health
    assert signal.max_sector_weight_pct == 60.0


def test_weight_by_sector_groups_none_under_unknown() -> None:
    signal = compute_portfolio_fit(
        proposal=BasketPosition("p1", 10.0, "tech"),
        existing=[
            BasketPosition("x1", 40.0, None),
            BasketPosition("x2", 30.0, None),
            BasketPosition("y1", 20.0, "tech"),
        ],
        equity=100.0,
    )
    # None se agrupa bajo la clave sentinel "<unknown>".
    assert signal.max_sector_weight_pct == 70.0  # x1+x2 (unknown)
    assert signal.max_asset_weight_pct == 40.0  # x1
    # el sector 'tech' (p1+y1) queda por debajo: 30.0
    assert signal.max_sector_weight_pct == 70.0


def test_unknown_sector_collected_but_reported() -> None:
    signal = compute_portfolio_fit(
        proposal=BasketPosition("p", 10.0, None),
        existing=[],
        equity=None,  # sin equity → denominador = suma de market_values
    )
    assert signal.max_asset_weight_pct == 100.0
    assert signal.max_sector_weight_pct == 100.0
    assert signal.violating_sector is None  # sin límite aportado
    assert "concentración cesta" in signal.note


def test_no_equity_uses_sum_of_market_values() -> None:
    signal = compute_portfolio_fit(
        proposal=BasketPosition("a", 25.0, "fin"),
        existing=[BasketPosition("b", 75.0, "fin")],
        equity=None,
    )
    assert signal.max_asset_weight_pct == 75.0
    assert signal.max_sector_weight_pct == 100.0


def test_violation_asset_breaks_limit() -> None:
    signal = compute_portfolio_fit(
        proposal=BasketPosition("a", 30.0, "tech"),
        existing=[
            BasketPosition("b", 50.0, "tech"),
            BasketPosition("c", 20.0, "health"),
        ],
        equity=100.0,
        max_asset_weight_pct=25.0,
        max_sector_weight_pct=40.0,
    )
    assert signal.violating_asset == "b"  # 50% > 25%
    assert signal.violating_sector == "tech"  # 80% > 40%


def test_as_if_fill_breaks_limit_by_proposal_only() -> None:
    # Sin la puesta propuesta no habría violación; con ella sí.
    before = compute_portfolio_fit(
        proposal=BasketPosition("new", 5.0, "tech"),
        existing=[BasketPosition("a", 60.0, "tech")],
        equity=100.0,
        max_sector_weight_pct=65.0,
    )
    # a(new 5 + a 60) = 65 → <= 65 → no viola por igualdad
    assert before.violating_sector is None
    after = compute_portfolio_fit(
        proposal=BasketPosition("new", 10.0, "tech"),
        existing=[BasketPosition("a", 60.0, "tech")],
        equity=100.0,
        max_sector_weight_pct=65.0,
    )
    assert after.violating_sector == "tech"  # 70% > 65%


def test_unobservable_returns_no_evaluable_without_violation() -> None:
    signal = compute_portfolio_fit(
        proposal=BasketPosition("a", None, "tech"),
        existing=[
            BasketPosition("b", None, "tech"),
        ],
        equity=100.0,
        max_asset_weight_pct=10.0,
        max_sector_weight_pct=20.0,
    )
    assert signal.max_asset_weight_pct is None
    assert signal.max_sector_weight_pct is None
    assert signal.violating_asset is None
    assert signal.violating_sector is None
    assert "no_evaluable" in signal.note
