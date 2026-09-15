"""OpportunityRanker — score explicable y TOP N (AUTO 2.0 · P0)."""

from bolsa_analytics.cognitive.opportunity_ranker import (
    OPPORTUNITY_WEIGHTS,
    rank_opportunities,
    score_opportunity,
    select_top_opportunities,
)


def test_weights_sum_to_one() -> None:
    total = sum(OPPORTUNITY_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


def test_score_perfect_is_one() -> None:
    s = score_opportunity(
        "AAPL",
        edge=1.0,
        robustness=1.0,
        regime_fit=1.0,
        momentum=1.0,
        liquidity=1.0,
        risk_reward=1.0,
        execution_quality=1.0,
    )
    assert s.combined == 1.0
    assert s.components["edge"] == 1.0


def test_score_missing_components_fail_closed_to_zero() -> None:
    s = score_opportunity("AAPL", edge=1.0)
    # edge 0.30 * 1.0 = 0.3; resto 0 y sin redistribuir.
    assert s.combined == 0.3
    assert s.components["momentum"] == 0.0
    assert s.components["liquidity"] == 0.0


def test_score_clamps_out_of_range() -> None:
    s = score_opportunity("AAPL", edge=5.0, robustness=-1.0)
    assert s.components["edge"] == 1.0
    assert s.components["robustness"] == 0.0


def test_score_nan_and_garbage() -> None:
    s = score_opportunity("AAPL", edge=float("nan"), momentum="basura")
    assert s.components["edge"] == 0.0
    assert s.components["momentum"] == 0.0


def test_ranking_descending_and_deterministic_tiebreak() -> None:
    scores = [
        score_opportunity("B", edge=0.5),
        score_opportunity("A", edge=0.9),
        score_opportunity("C", edge=0.5),
    ]
    ranked = rank_opportunities(scores)
    assert [s.instrument_id for s in ranked] == ["A", "B", "C"]
    assert [s.rank for s in ranked] == [1, 2, 3]


def test_select_top_n() -> None:
    scores = [
        score_opportunity("B", edge=0.5),
        score_opportunity("A", edge=0.9),
        score_opportunity("C", edge=0.7),
        score_opportunity("D", edge=0.1),
    ]
    top = select_top_opportunities(scores, top_n=2)
    assert [s.instrument_id for s in top] == ["A", "C"]
    assert all(s.rank is not None for s in top)


def test_select_top_zero_fail_closed() -> None:
    scores = [score_opportunity("A", edge=0.9)]
    assert select_top_opportunities(scores, top_n=0) == ()
    assert select_top_opportunities(scores, top_n=-1) == ()


def test_to_dict_shape() -> None:
    d = score_opportunity("AAPL", edge=0.8).to_dict()
    assert d["instrumentId"] == "AAPL"
    assert set(d["components"].keys()) == set(OPPORTUNITY_WEIGHTS.keys())
    assert d["combined"] == 0.24  # 0.8 * 0.30
