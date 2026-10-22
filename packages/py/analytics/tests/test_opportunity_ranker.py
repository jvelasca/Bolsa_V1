"""OpportunityRanker — score explicable y TOP N (AUTO 2.0 · P0)."""

from bolsa_analytics.cognitive.opportunity_ranker import (
    OPPORTUNITY_WEIGHTS,
    OpportunityScore,
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


def test_identity_is_transported_and_never_affects_the_score() -> None:
    """V2.88.153 — preset/versión viajan ADITIVOS: no pesan ni reordenan."""
    with_identity = score_opportunity(
        "AAPL",
        edge=0.8,
        strategy_preset_key="momentum_breakout",
        strategy_version="2026.10.1",
    )
    without_identity = score_opportunity("AAPL", edge=0.8)
    assert with_identity.combined == without_identity.combined
    assert with_identity.strategy_preset_key == "momentum_breakout"
    assert with_identity.strategy_version == "2026.10.1"
    assert without_identity.strategy_preset_key is None
    assert without_identity.strategy_version is None


def test_rank_preserves_identity_on_every_copy() -> None:
    ranked = rank_opportunities(
        [
            score_opportunity("B", edge=0.5, strategy_preset_key="p-b"),
            score_opportunity("A", edge=0.9, strategy_preset_key="p-a", strategy_version="v1"),
        ]
    )
    assert [(s.instrument_id, s.rank) for s in ranked] == [("A", 1), ("B", 2)]
    assert ranked[0].strategy_preset_key == "p-a"
    assert ranked[0].strategy_version == "v1"
    assert ranked[1].strategy_preset_key == "p-b"
    assert ranked[1].strategy_version is None


def test_identity_is_omitted_from_to_dict_when_absent() -> None:
    """Un hueco no se publica como clave vacía: se OMITE (misma doctrina que el journal)."""
    payload = score_opportunity("AAPL", edge=0.8).to_dict()
    assert "strategyPresetKey" not in payload
    assert "strategyVersion" not in payload
    full = score_opportunity(
        "AAPL", edge=0.8, strategy_preset_key="p", strategy_version="v"
    ).to_dict()
    assert full["strategyPresetKey"] == "p"
    assert full["strategyVersion"] == "v"


# ---------------------------------------------------------------------------
# W-159-4 (Hueco A) ? el TOP no se rellena con candidatas sin medir.
# ``measured_components = ()`` es un 0,0 ESTRUCTURAL, no una nota baja: esa candidata no
# es comparable econ?micamente y no debe ocupar un hueco del TOP por desempate alfab?tico.
# ---------------------------------------------------------------------------


def test_top_is_never_filled_with_unscored_zeroes() -> None:
    """S?lo compiten las que declaran medici?n; el resto queda fuera, no en el TOP."""
    measured = score_opportunity("ZZZ", edge=0.4)
    unmeasured = [
        score_opportunity(f"SYM{index:02d}") for index in range(5)
    ]

    top = select_top_opportunities([measured, *unmeasured], top_n=5, require_measured=True)

    assert [score.instrument_id for score in top] == ["ZZZ"], (
        "un 0,0 sin componentes no puede ganar un hueco por orden alfab?tico"
    )
    assert all(score.scored for score in top)


def test_a_declared_zero_is_measurement_not_absence() -> None:
    """Un ``0.0`` DECLARADO s? es medici?n: la candidata existe y compite."""
    declared = score_opportunity("AAA", edge=0.0)

    assert declared.measured_components == ("edge",)
    assert declared.scored is True
    assert select_top_opportunities([declared], top_n=3) == rank_opportunities([declared])
    assert [s.instrument_id for s in select_top_opportunities([declared], top_n=3)] == ["AAA"]


def test_without_any_measurement_the_top_is_empty() -> None:
    """Sin una sola medici?n no hay TOP que decidir (fail-closed, no un ranking de ceros)."""
    unmeasured = [score_opportunity(f"SYM{index:02d}") for index in range(5)]

    assert all(score.measured_components == () for score in unmeasured)
    assert select_top_opportunities(unmeasured, top_n=5, require_measured=True) == ()


def test_directly_constructed_score_is_not_dropped() -> None:
    """``measured_components = None`` no es ?sin medir?: no se afirma la ausencia."""
    hand_made = OpportunityScore(instrument_id="AAA", combined=0.5)

    assert hand_made.measured_components is None
    assert hand_made.scored is True
    assert [s.instrument_id for s in select_top_opportunities([hand_made], top_n=1)] == ["AAA"]


def test_evidence_mode_keeps_unmeasured_candidates() -> None:
    """La FOTO del TOP3 no filtra: informa. S?lo la decisi?n exige medici?n."""
    measured = score_opportunity("AAA", edge=0.9)
    unmeasured = score_opportunity("BBB")

    assert [s.instrument_id for s in select_top_opportunities([measured, unmeasured], top_n=5)] == [
        "AAA",
        "BBB",
    ], "sin ``require_measured`` la foto conserva a la candidata sin campe?n"
    assert [
        s.instrument_id
        for s in select_top_opportunities([measured, unmeasured], top_n=5, require_measured=True)
    ] == ["AAA"]
