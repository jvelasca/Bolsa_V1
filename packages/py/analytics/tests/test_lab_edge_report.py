"""Lab EdgeReport lite (P3.M)."""

from bolsa_analytics.optimize.lab_edge_report import (
    build_lab_edge_report_lite,
    trade_returns_from_pnls,
)


def test_trade_returns_from_pnls() -> None:
    assert trade_returns_from_pnls([100.0, -50.0], initial_cash=10_000) == [0.01, -0.005]
    assert trade_returns_from_pnls([1.0], initial_cash=0) == []


def test_build_lab_edge_report_lite_requires_trades() -> None:
    assert (
        build_lab_edge_report_lite(
            strategy_ref="sma:x",
            trade_returns=[0.01, -0.002],
            trials_n=10,
            lab_walk_forward_efficiency=0.7,
        )
        is None
    )


def test_build_lab_edge_report_lite_suite() -> None:
    returns = [0.02, -0.01, 0.015, 0.01, -0.005, 0.012, 0.008, -0.003]
    report = build_lab_edge_report_lite(
        strategy_ref="sma:inst",
        trade_returns=returns,
        trials_n=25,
        lab_walk_forward_efficiency=0.65,
        family="sma_crossover",
        monte_carlo_permutations=200,
    )
    assert report is not None
    assert report["mode"] == "lab_lite"
    assert report["suite"]["wfeSource"] == "lab_score"
    assert report["suite"]["walkForwardEfficiency"] == 0.65
    assert report["suite"]["monteCarloPValue"] is not None
    assert report["suite"]["dsr"] is not None
    assert report["credibility"] >= 0
    assert report["band"] in {"skill", "uncertain", "luck"}
