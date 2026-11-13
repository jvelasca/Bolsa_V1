"""Tests del núcleo puro DÍA-D as-run (ADR-049).

Cubren los invariantes declarados en el ADR: determinismo, no look-ahead, gaps declarados
(``NOT_MEASURED``, nunca ``0``), coste explícito y veredicto por cohorte. Desde el cierre de
auditoría 2026-11-13 añaden: coste homogéneo entre brazos, benchmark comparable con la
estrategia, universo declarado y manifest por vela verificable.
"""

from __future__ import annotations

import pytest

from bolsa_application.dia_d_as_run import (
    ARM_AS_RUN,
    ARM_CANDIDATE,
    ARM_CASH,
    ARM_ENGINE_PARAMS,
    ARM_HOLD_STRUCTURAL,
    ARM_MARKET_BH,
    GAP_POLICY_OPEN,
    GAP_POLICY_THEORETICAL,
    REAL_FILLS_COST_EFFECTIVE,
    AsRunExecutionModel,
    AsRunFill,
    AsRunLeg,
    build_as_run_artifact,
    evaluate_multi_day,
    run_as_run_arm,
    run_cash_arm,
    run_hold_arm,
    run_market_bh_arm,
    verify_bars_manifest,
)
from bolsa_application.dia_d_certification import (
    CHECK_FAIL,
    CHECK_PASS,
    certify_artifact,
    certify_cohort,
)
from bolsa_domain.entities.ohlcv_bar import OhlcvBar

DAY = "2026-01-01"


def _bar(timestamp: str, *, open_: float, high: float, low: float, close: float) -> OhlcvBar:
    return OhlcvBar(
        timestamp=timestamp,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1_000,
    )


def _leg(**overrides: object) -> AsRunLeg:
    base: dict[str, object] = {
        "instrument_id": "AAA",
        "direction": "long",
        "quantity": 10.0,
        "entry": 100.0,
        "structural_stop": 95.0,
        "target1": 110.0,
        "target2": None,
    }
    base.update(overrides)
    return AsRunLeg(**base)  # type: ignore[arg-type]


# ── determinismo ────────────────────────────────────────────────────────────


def test_artifact_hash_is_stable_across_calls() -> None:
    legs = [_leg()]
    bars = {
        "AAA": [
            _bar("2026-01-02", open_=100.0, high=104.0, low=99.0, close=103.0),
            _bar("2026-01-03", open_=103.0, high=111.0, low=102.0, close=110.0),
        ]
    }
    fills = [AsRunFill(timestamp="2026-01-03", instrument_id="AAA", side="sell", quantity=10.0, price=110.0)]

    first = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=legs,
        fills=fills,
        bars_by_instrument=bars,
        cost_bps=32.0,
    )
    second = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=legs,
        fills=fills,
        bars_by_instrument=bars,
        cost_bps=32.0,
    )

    assert first == second
    assert first["hash"] == second["hash"]
    assert len(first["hash"]) == 64


def test_arm_order_is_canonical() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={},
    )
    assert [arm["arm"] for arm in artifact["arms"]] == [
        ARM_AS_RUN,
        ARM_HOLD_STRUCTURAL,
        ARM_CASH,
        ARM_ENGINE_PARAMS,
        ARM_CANDIDATE,
        ARM_MARKET_BH,
    ]


# ── no look-ahead ───────────────────────────────────────────────────────────


def test_future_bars_do_not_change_the_exit_already_taken() -> None:
    """Cambiar las barras *posteriores* al cierre no puede cambiar el resultado medido."""
    legs = [_leg()]
    through_exit = [
        _bar("2026-01-02", open_=100.0, high=101.0, low=98.0, close=100.0),
        _bar("2026-01-03", open_=100.0, high=104.0, low=96.0, close=99.0),
        _bar("2026-01-04", open_=99.0, high=102.0, low=94.0, close=95.0),  # toca stop 95
    ]
    with_future = through_exit + [
        _bar("2026-01-05", open_=95.0, high=120.0, low=95.0, close=118.0),
        _bar("2026-01-06", open_=118.0, high=130.0, low=117.0, close=129.0),
    ]

    prefix = run_hold_arm(legs, {"AAA": through_exit}, after=DAY)
    full = run_hold_arm(legs, {"AAA": with_future}, after=DAY)

    assert prefix.realized_r == full.realized_r
    assert prefix.stops == full.stops == 1


def test_bars_on_or_before_day_are_never_read() -> None:
    legs = [_leg()]
    history_before_day = [
        _bar("2025-12-30", open_=100.0, high=140.0, low=50.0, close=100.0),
        _bar(DAY, open_=100.0, high=140.0, low=50.0, close=100.0),
    ]
    future = [_bar("2026-01-05", open_=100.0, high=101.0, low=99.0, close=100.0)]

    without_history = run_hold_arm(legs, {"AAA": future}, after=DAY)
    with_history = run_hold_arm(legs, {"AAA": history_before_day + future}, after=DAY)

    assert without_history.realized_r == with_history.realized_r


def test_stop_is_checked_before_target_on_the_same_bar() -> None:
    """Un hueco adverso se ejecuta como stop, no como target."""
    legs = [_leg()]
    bars = [_bar("2026-01-02", open_=100.0, high=115.0, low=90.0, close=91.0)]

    result = run_hold_arm(legs, {"AAA": bars}, after=DAY, cost_bps=0.0)

    assert result.measured is True
    assert result.stops == 1
    assert result.targets == 0
    assert result.realized_r == -1.0


# ── gap declarado, nunca cero ───────────────────────────────────────────────


def test_cash_arm_is_measured_and_zero() -> None:
    result = run_cash_arm()
    assert result.measured is True
    assert result.realized_r == 0.0


def test_no_open_legs_declares_a_gap_instead_of_zero() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[],
        fills=[],
        bars_by_instrument={},
    )

    hold = next(arm for arm in artifact["arms"] if arm["arm"] == ARM_HOLD_STRUCTURAL)
    assert hold["measured"] is False
    assert hold["realizedR"] is None
    assert hold["reason"] == "no_open_legs"

    gaps = {gap["arm"]: gap["reason"] for gap in artifact["gaps"]}
    assert gaps[ARM_HOLD_STRUCTURAL] == "no_open_legs"
    assert gaps[ARM_AS_RUN] == "no_fills"
    assert gaps[ARM_ENGINE_PARAMS] == "params_not_declared"
    assert gaps[ARM_CANDIDATE] == "candidate_not_provided"
    assert ARM_CASH not in gaps


def test_missing_bars_declares_gap_per_instrument() -> None:
    result = run_hold_arm([_leg()], {}, after=DAY)
    assert result.measured is False
    assert result.reason == "no_measurable_legs"
    assert "no_bars:AAA" in result.reason_codes


def test_engine_params_arm_requires_declared_params() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={"AAA": [_bar("2026-01-02", open_=100.0, high=104.0, low=99.0, close=103.0)]},
    )
    engine = next(arm for arm in artifact["arms"] if arm["arm"] == ARM_ENGINE_PARAMS)
    assert engine["measured"] is False
    assert engine["reason"] == "params_not_declared"


def test_engine_params_arm_measures_when_params_are_declared() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={"AAA": [_bar("2026-01-02", open_=100.0, high=104.0, low=99.0, close=103.0)]},
        engine_stop_multiplier=1.0,
        engine_target_multiplier=1.0,
    )
    engine = next(arm for arm in artifact["arms"] if arm["arm"] == ARM_ENGINE_PARAMS)
    assert engine["measured"] is True


# ── coste explícito ─────────────────────────────────────────────────────────


def test_cost_reduces_realized_r() -> None:
    legs = [_leg()]
    bars = {"AAA": [_bar("2026-01-02", open_=100.0, high=110.5, low=100.0, close=110.0)]}

    free = run_hold_arm(legs, bars, after=DAY, cost_bps=0.0)
    costly = run_hold_arm(legs, bars, after=DAY, cost_bps=50.0)

    assert free.measured and costly.measured
    assert costly.realized_r < free.realized_r


# ── brazo as-run ────────────────────────────────────────────────────────────


def test_as_run_arm_pairs_fills_fifo() -> None:
    legs = [_leg()]
    fills = [
        AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="sell", quantity=10.0, price=110.0),
    ]
    # La compra previa está en el libro (leg), la venta es el fill de la ventana.
    # Sin compra en la ventana no hay ciclo cerrado.
    result = run_as_run_arm(legs, fills, cost_bps=0.0)
    assert result.measured is False
    assert result.reason == "no_closed_cycles"
    assert "unmatched_sell:AAA" in result.reason_codes


def test_as_run_arm_measures_a_realized_cycle() -> None:
    legs = [_leg()]
    fills = [
        AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="buy", quantity=10.0, price=100.0),
        AsRunFill(timestamp="2026-01-03", instrument_id="AAA", side="sell", quantity=10.0, price=110.0),
    ]
    result = run_as_run_arm(legs, fills, cost_bps=0.0)

    assert result.measured is True
    assert result.exits == 1
    assert result.realized_r == 2.0
    assert result.pnl_currency == 100.0


# ── cohorte ─────────────────────────────────────────────────────────────────


def _artifact_with(realized_by_arm: dict[str, float]) -> dict[str, object]:
    return {
        "arms": [
            {"arm": name, "measured": True, "realizedR": value}
            for name, value in realized_by_arm.items()
        ]
    }


def test_insufficient_sample_is_declared() -> None:
    verdict = evaluate_multi_day([_artifact_with({ARM_AS_RUN: 1.0, ARM_CASH: 0.0})], min_samples=5)
    assert verdict.verdict == "insufficient_sample"
    assert verdict.samples == 1
    assert verdict.reason == "min_samples:5"


def test_as_run_beats_arms_when_its_mean_is_higher() -> None:
    artifacts = [
        _artifact_with({ARM_AS_RUN: as_run, ARM_CASH: 0.0})
        for as_run in (1.0, 2.0, 3.0)
    ]
    verdict = evaluate_multi_day(artifacts, min_samples=3)
    assert verdict.verdict == "as_run_beats_arms"
    assert verdict.best_arm == ARM_CASH
    assert verdict.as_run_mean_r == 2.0


def test_arms_beat_as_run_when_they_are_better() -> None:
    artifacts = [
        _artifact_with({ARM_AS_RUN: -1.0, ARM_CASH: 0.0})
        for _ in range(3)
    ]
    verdict = evaluate_multi_day(artifacts, min_samples=3)
    assert verdict.verdict == "arms_beat_as_run"
    assert verdict.best_arm == ARM_CASH


def test_market_benchmark_does_not_compete_in_r() -> None:
    """El benchmark publica retorno, no R: no puede ganar la comparación de R."""
    artifacts = [
        {
            "arms": [
                {"arm": ARM_AS_RUN, "measured": True, "realizedR": 1.0},
                {"arm": ARM_CASH, "measured": True, "realizedR": 0.0},
                {"arm": ARM_MARKET_BH, "measured": True, "realizedR": None, "returnPct": 9.0},
            ]
        }
        for _ in range(3)
    ]
    verdict = evaluate_multi_day(artifacts, min_samples=3)
    assert verdict.best_arm == ARM_CASH
    assert verdict.verdict == "as_run_beats_arms"


# ── ejecución realista: gaps, deslizamiento y liquidez ──────────────────────


def test_adverse_gap_fills_at_open_not_at_theoretical_stop() -> None:
    """Un hueco adverso se ejecuta al open: el R es peor que el del stop teórico."""
    legs = [_leg()]
    bars = [_bar("2026-01-02", open_=90.0, high=92.0, low=88.0, close=91.0)]

    gap_aware = run_hold_arm(legs, {"AAA": bars}, after=DAY, cost_bps=0.0)
    theoretical = run_hold_arm(
        legs,
        {"AAA": bars},
        after=DAY,
        execution=AsRunExecutionModel(gap_policy=GAP_POLICY_THEORETICAL),
    )

    assert gap_aware.measured is True
    assert gap_aware.stops == 1
    assert gap_aware.realized_r == -2.0  # (90 - 100) / 5
    assert theoretical.realized_r == -1.0  # stop teórico 95


def test_favourable_gap_fills_at_open_above_the_target() -> None:
    legs = [_leg()]
    bars = [_bar("2026-01-02", open_=115.0, high=118.0, low=114.0, close=117.0)]

    result = run_hold_arm(legs, {"AAA": bars}, after=DAY, cost_bps=0.0)

    assert result.measured is True
    assert result.targets == 1
    assert result.realized_r == 3.0  # (115 - 100) / 5, no el target 110


def test_slippage_worsens_counterfactual_arms_and_leaves_real_fills_alone() -> None:
    legs = [_leg()]
    bars = {"AAA": [_bar("2026-01-02", open_=100.0, high=112.0, low=99.0, close=110.0)]}
    fills = [
        AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="sell", quantity=10.0, price=110.0),
        AsRunFill(timestamp="2026-01-01", instrument_id="AAA", side="buy", quantity=10.0, price=100.0),
    ]
    free = AsRunExecutionModel()
    slipped = AsRunExecutionModel(slippage_bps=50.0)

    hold_free = run_hold_arm(legs, bars, after=DAY, execution=free)
    hold_slipped = run_hold_arm(legs, bars, after=DAY, execution=slipped)
    real_free = run_as_run_arm(legs, fills, execution=free)
    real_slipped = run_as_run_arm(legs, fills, execution=slipped)

    assert hold_free.measured and hold_slipped.measured
    assert hold_slipped.realized_r < hold_free.realized_r
    # Los fills son reales: no se les aplica deslizamiento.
    assert real_slipped.realized_r == real_free.realized_r


def test_declared_cost_bps_is_round_trip_and_charged_once() -> None:
    """``cost_bps`` es el coste declarado de ida y vuelta; no se cobra dos veces."""
    legs = [_leg(structural_stop=90.0, target1=200.0)]
    bars = {"AAA": [_bar("2026-01-02", open_=100.0, high=100.0, low=100.0, close=100.0)]}

    result = run_hold_arm(legs, bars, after=DAY, cost_bps=32.0)

    assert result.measured is True
    # 10 acciones × 100 × 32 bps = 3,2 (y no 6,4 como si el 32 fuese por lado).
    assert result.pnl_currency == -3.2


def test_illiquid_bar_defers_the_exit_to_the_next_open() -> None:
    """Sin liquidez en la barra que dispara, el cierre se difiere al open siguiente."""
    legs = [_leg(quantity=10.0)]
    bars = [
        _bar("2026-01-02", open_=100.0, high=100.0, low=90.0, close=91.0),
        _bar("2026-01-03", open_=93.0, high=94.0, low=92.0, close=93.0),
    ]
    bars[0] = OhlcvBar(
        timestamp="2026-01-02", open=100.0, high=100.0, low=90.0, close=91.0, volume=10
    )
    model = AsRunExecutionModel(max_participation_pct=0.5)  # capacidad 5 < 10

    result = run_hold_arm(legs, {"AAA": bars}, after=DAY, execution=model)

    assert result.measured is True
    assert "deferred_exits:1" in result.reason_codes
    assert result.realized_r == -1.4  # (93 - 100) / 5
    exit_decision = next(d for d in result.decisions if d["action"] == "exit")
    assert exit_decision["reason"] == "stop_deferred"


def test_no_liquidity_anywhere_declares_a_gap_instead_of_a_fill() -> None:
    legs = [_leg(quantity=10.0)]
    thin = OhlcvBar(
        timestamp="2026-01-02", open=100.0, high=100.0, low=90.0, close=91.0, volume=10
    )
    model = AsRunExecutionModel(max_participation_pct=0.5)

    result = run_hold_arm(legs, {"AAA": [thin]}, after=DAY, execution=model)

    assert result.measured is False
    assert result.reason == "no_measurable_legs"
    assert "liquidity_insufficient:AAA" in result.reason_codes


def test_market_benchmark_is_measured_in_return_not_in_r() -> None:
    bars = {
        "AAA": [
            _bar("2026-01-02", open_=100.0, high=101.0, low=99.0, close=100.0),
            _bar("2026-01-03", open_=100.0, high=111.0, low=99.0, close=110.0),
        ]
    }

    result = run_market_bh_arm(bars, after=DAY, cost_bps=0.0)

    assert result.measured is True
    assert result.realized_r is None
    assert result.return_pct is not None and result.return_pct > 9.0
    assert "benchmark_return_only" in result.reason_codes


def test_market_benchmark_without_instruments_is_a_declared_gap() -> None:
    result = run_market_bh_arm({}, after=DAY)

    assert result.measured is False
    assert result.reason == "no_instruments"


# ── look-ahead de la candidata ──────────────────────────────────────────────


def test_candidate_without_point_in_time_is_not_measured() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={
            "AAA": [_bar("2026-01-02", open_=100.0, high=104.0, low=99.0, close=103.0)]
        },
        candidate_legs=[_leg()],
        candidate_as_of=None,
    )
    candidate = next(arm for arm in artifact["arms"] if arm["arm"] == ARM_CANDIDATE)
    assert candidate["measured"] is False
    assert candidate["reason"] == "candidate_not_point_in_time"


def test_candidate_after_day_is_a_look_ahead_and_is_not_measured() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={
            "AAA": [_bar("2026-01-02", open_=100.0, high=104.0, low=99.0, close=103.0)]
        },
        candidate_legs=[_leg()],
        candidate_as_of="2026-06-01",
    )
    candidate = next(arm for arm in artifact["arms"] if arm["arm"] == ARM_CANDIDATE)
    assert candidate["measured"] is False
    assert candidate["reason"] == "candidate_not_point_in_time"


def test_candidate_outside_the_declared_universe_is_not_measured() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={
            "AAA": [_bar("2026-01-02", open_=100.0, high=104.0, low=99.0, close=103.0)]
        },
        candidate_legs=[_leg(instrument_id="ZZZ")],
        candidate_as_of=DAY,
    )
    candidate = next(arm for arm in artifact["arms"] if arm["arm"] == ARM_CANDIDATE)
    assert candidate["measured"] is False
    assert str(candidate["reason"]).startswith("candidate_outside_universe")


def test_point_in_time_candidate_is_measured() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={
            "AAA": [_bar("2026-01-02", open_=100.0, high=104.0, low=99.0, close=103.0)]
        },
        candidate_legs=[_leg()],
        candidate_as_of=DAY,
    )
    candidate = next(arm for arm in artifact["arms"] if arm["arm"] == ARM_CANDIDATE)
    assert candidate["measured"] is True


# ── sobre de auditoría y certificación ─────────────────────────────────────


def _certifiable_artifact(day: str = DAY) -> dict:
    execution = AsRunExecutionModel(
        commission_bps=5.0,
        slippage_bps=3.0,
        spread_bps=2.0,
        max_participation_pct=0.1,
        gap_policy=GAP_POLICY_OPEN,
    )
    bars = {
        "AAA": [
            _bar("2026-01-02", open_=100.0, high=105.0, low=99.0, close=104.0),
            _bar("2026-01-03", open_=104.0, high=111.0, low=103.0, close=110.0),
        ]
    }
    fills = [
        AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="buy", quantity=10.0, price=100.0),
        AsRunFill(timestamp="2026-01-03", instrument_id="AAA", side="sell", quantity=10.0, price=110.0),
    ]
    return build_as_run_artifact(
        day=day,
        account_id="acc-1",
        legs=[_leg()],
        fills=fills,
        bars_by_instrument=bars,
        execution=execution,
        candidate_legs=[_leg(structural_stop=97.5, target1=110.0)],
        candidate_as_of=day,
        to_day="2026-01-03",
        state_source="sim_auto_positions",
        bars_source="postgres:ohlcv_bars",
        bars_timeframe="1d",
        params={
            "engineStopMultiplier": None,
            "engineTargetMultiplier": None,
            "universe": "watch",
            "execution": execution.to_dict(),
        },
        universe_instruments=["AAA"],
        bump="test-bump",
        limits=["método descriptivo, no causal"],
    )


def test_fully_declared_artifact_is_certified() -> None:
    artifact = _certifiable_artifact()

    certification = certify_artifact(artifact)

    assert certification.verdict == "certified"
    assert certification.certified is True
    assert certification.reasons == ()
    assert all(check.status == CHECK_PASS for check in certification.checks)


def test_artifact_without_audit_is_not_certified_and_says_why() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="buy", quantity=10.0, price=100.0)],
        bars_by_instrument={},
    )

    certification = certify_artifact(artifact)

    assert certification.verdict == "not_certified"
    assert certification.failures or certification.not_evaluated
    assert any(check.status == CHECK_FAIL or check.status == "NOT_EVALUATED" for check in certification.checks)


def test_reconstructed_state_is_a_hard_failure() -> None:
    artifact = _certifiable_artifact()
    artifact["audit"]["pointInTime"]["sourceIsReconstructed"] = True

    certification = certify_artifact(artifact)

    assert certification.verdict == "not_certified"
    assert "temporal_freeze" in certification.failures
    assert "initial_state" in certification.failures


def test_tampered_legs_hash_is_rejected() -> None:
    artifact = _certifiable_artifact()
    artifact["audit"]["pointInTime"]["legs"][0]["quantity"] = 999.0

    certification = certify_artifact(artifact)

    assert certification.verdict == "not_certified"
    assert "initial_state" in certification.failures


def test_certification_is_deterministic() -> None:
    artifact = _certifiable_artifact()

    first = certify_artifact(artifact).to_dict()
    second = certify_artifact(artifact).to_dict()

    assert first["hash"] == second["hash"]
    assert first["checks"] == second["checks"]


def test_cohort_without_enough_certified_days_is_insufficient() -> None:
    cohort = certify_cohort([_certifiable_artifact()], min_samples=12)

    assert cohort.verdict == "insufficient_sample"
    assert cohort.certified is False


def test_cohort_of_certified_days_is_certified() -> None:
    artifacts = [_certifiable_artifact("2026-01-01") for _ in range(3)]

    cohort = certify_cohort(artifacts, min_samples=3)

    assert cohort.verdict == "certified"
    assert cohort.certified is True


# ── hardening de auditoría: gaps, coste, benchmark y hashes ─────────────────


def test_gap_beyond_stop_and_below_target_exits_at_the_stop() -> None:
    """Una vela que abre por debajo del stop y del target sale por stop, no por target."""
    legs = [_leg()]  # stop 95, target 110
    bars = [OhlcvBar(timestamp="2026-01-02", open=90.0, high=92.0, low=88.0, close=91.0, volume=1_000)]

    result = run_hold_arm(legs, {"AAA": bars}, after=DAY, cost_bps=0.0)

    assert result.measured is True
    assert result.stops == 1
    assert result.targets == 0
    assert result.realized_r == -2.0  # (90 - 100) / 5: open real, no stop teórico


def test_deferred_exit_dates_the_fill_not_the_trigger() -> None:
    """Un cierre diferido se fecha en la barra que lo absorbe, nunca retroactivamente."""
    legs = [_leg(quantity=10.0)]
    trigger_bar = OhlcvBar(
        timestamp="2026-01-02", open=100.0, high=100.0, low=90.0, close=91.0, volume=10
    )
    absorbing_bar = OhlcvBar(
        timestamp="2026-01-03", open=93.0, high=94.0, low=92.0, close=93.0, volume=1_000
    )
    model = AsRunExecutionModel(max_participation_pct=0.5)  # capacidad 5 < 10 en la 1.ª

    result = run_hold_arm(
        legs, {"AAA": [trigger_bar, absorbing_bar]}, after=DAY, execution=model
    )

    exit_decision = next(d for d in result.decisions if d["action"] == "exit")
    assert exit_decision["date"] == "2026-01-03"
    assert exit_decision["price"] == 93.0
    assert exit_decision["reason"] == "stop_deferred"
    # La excursión se corta en el open ejecutado: el mínimo de 90 es del disparo, no futuro.
    assert result.mae_r == -2.0


def test_exit_bar_high_does_not_inflate_mfe() -> None:
    """El rango posterior al precio de salida no puede contarse como excursión favorable."""
    legs = [_leg()]  # target 110
    bars = [OhlcvBar(timestamp="2026-01-02", open=110.0, high=130.0, low=108.0, close=128.0, volume=1_000)]

    result = run_hold_arm(legs, {"AAA": bars}, after=DAY, cost_bps=0.0)

    assert result.targets == 1
    assert result.mfe_r == 2.0  # (110 - 100) / 5, no el máximo de 130
    assert result.capture == 1.0


def test_same_cycle_costs_the_same_measured_as_run_or_as_hold() -> None:
    """El coste se imputa una vez y con la misma base en todos los brazos."""
    legs = [_leg(structural_stop=90.0, target1=200.0)]
    bars = {"AAA": [OhlcvBar(timestamp="2026-01-02", open=100.0, high=100.0, low=100.0, close=100.0, volume=1_000)]}
    fills = [
        AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="buy", quantity=10.0, price=100.0),
        AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="sell", quantity=10.0, price=100.0),
    ]

    hold = run_hold_arm(legs, bars, after=DAY, cost_bps=32.0)
    real = run_as_run_arm(legs, fills, cost_bps=32.0)

    assert hold.pnl_currency == real.pnl_currency == -3.2
    assert hold.realized_r == real.realized_r


def test_effective_fills_charge_no_cash_cost_and_keep_the_round_trip_declared() -> None:
    """``effective`` dice que el precio ya es neto: cobrar otra vez duplicaría el coste."""
    legs = [_leg(structural_stop=90.0, target1=200.0)]
    bars = {"AAA": [OhlcvBar(timestamp="2026-01-02", open=100.0, high=100.0, low=100.0, close=100.0, volume=1_000)]}
    fills = [
        AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="buy", quantity=10.0, price=100.0),
        AsRunFill(timestamp="2026-01-02", instrument_id="AAA", side="sell", quantity=10.0, price=100.0),
    ]
    execution = AsRunExecutionModel(
        slippage_bps=16.0, real_fills_cost_basis=REAL_FILLS_COST_EFFECTIVE
    )

    real = run_as_run_arm(legs, fills, execution=execution)
    hold = run_hold_arm(legs, bars, after=DAY, execution=execution)

    assert execution.execution_cost_bps == 0.0
    assert execution.round_trip_bps == 32.0  # el coste declarado sigue siendo positivo
    assert real.pnl_currency == 0.0  # fills netos: nada que cobrar
    assert real.realized_r == 0.0
    # El deslizamiento sí sigue aplicándose a los brazos contrafactuales (va en el precio).
    assert hold.pnl_currency is not None and hold.pnl_currency < 0


def test_effective_basis_rejects_cash_cost_double_counting() -> None:
    with pytest.raises(ValueError):
        AsRunExecutionModel(
            commission_bps=5.0, real_fills_cost_basis=REAL_FILLS_COST_EFFECTIVE
        )


def test_market_benchmark_uses_the_same_capital_and_cost_as_the_strategy() -> None:
    """Mismo capital, mismo coste y mismo precio de salida ⇒ mismo PnL que la estrategia."""
    legs = [_leg()]  # 10 × 100 = 1.000 de notional inicial, target 110
    bars = {
        "AAA": [
            OhlcvBar(timestamp="2026-01-02", open=100.0, high=105.0, low=99.0, close=105.0, volume=10_000),
            OhlcvBar(timestamp="2026-01-03", open=105.0, high=110.0, low=104.0, close=110.0, volume=10_000),
        ]
    }
    execution = AsRunExecutionModel(commission_bps=16.0)  # 32 bps round-trip, sin deslizamiento

    hold = run_hold_arm(legs, bars, after=DAY, execution=execution)
    market = run_market_bh_arm(
        bars, after=DAY, execution=execution, universe_instruments=["AAA"], capital=1_000.0
    )

    assert hold.pnl_currency == market.pnl_currency
    assert hold.realized_r is not None
    assert market.realized_r is None  # el benchmark no publica R inventado


def test_market_benchmark_period_is_clipped_to_to_day() -> None:
    bars = {
        "AAA": [
            OhlcvBar(timestamp="2026-01-02", open=100.0, high=101.0, low=99.0, close=100.0, volume=10_000),
            OhlcvBar(timestamp="2026-01-03", open=100.0, high=121.0, low=99.0, close=120.0, volume=10_000),
            OhlcvBar(timestamp="2026-01-04", open=120.0, high=161.0, low=119.0, close=160.0, volume=10_000),
        ]
    }

    clipped = run_market_bh_arm(
        bars, after=DAY, cost_bps=0.0, universe_instruments=["AAA"], to_day="2026-01-03"
    )
    full = run_market_bh_arm(bars, after=DAY, cost_bps=0.0, universe_instruments=["AAA"])

    assert clipped.return_pct == 20.0
    assert full.return_pct == 60.0


def test_market_benchmark_respects_the_declared_universe() -> None:
    bars = {
        "AAA": [
            OhlcvBar(timestamp="2026-01-02", open=100.0, high=101.0, low=99.0, close=100.0, volume=10_000),
            OhlcvBar(timestamp="2026-01-03", open=100.0, high=111.0, low=99.0, close=110.0, volume=10_000),
        ],
        "BBB": [
            OhlcvBar(timestamp="2026-01-02", open=100.0, high=101.0, low=99.0, close=100.0, volume=10_000),
            OhlcvBar(timestamp="2026-01-03", open=100.0, high=91.0, low=89.0, close=90.0, volume=10_000),
        ],
    }

    only_aaa = run_market_bh_arm(
        bars, after=DAY, cost_bps=0.0, universe_instruments=["AAA"]
    )
    both = run_market_bh_arm(bars, after=DAY, cost_bps=0.0)

    assert only_aaa.legs == 1
    assert only_aaa.return_pct == 10.0
    assert both.legs == 2
    assert both.return_pct == 0.0  # (10 % - 10 %) / 2


def test_market_benchmark_liquidity_uses_the_real_quantity() -> None:
    """Con capital declarado la cota se mide sobre la cantidad repartida, no sobre 1 unidad."""
    bars = {
        "AAA": [
            OhlcvBar(timestamp="2026-01-02", open=100.0, high=101.0, low=99.0, close=100.0, volume=50),
            OhlcvBar(timestamp="2026-01-03", open=100.0, high=111.0, low=99.0, close=110.0, volume=50),
        ]
    }
    execution = AsRunExecutionModel(max_participation_pct=0.1)  # capacidad 5 < 10 acciones

    result = run_market_bh_arm(
        bars,
        after=DAY,
        execution=execution,
        universe_instruments=["AAA"],
        capital=1_000.0,
    )

    assert result.measured is False
    assert result.reason == "no_instruments"
    assert "liquidity_insufficient:AAA" in result.reason_codes


def test_bars_do_not_widen_the_declared_universe_for_the_candidate() -> None:
    """Tener barras de un instrumento no lo convierte en parte del universo de D."""
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={
            "AAA": [_bar("2026-01-02", open_=100.0, high=101.0, low=99.0, close=100.0)],
            "BBB": [_bar("2026-01-02", open_=50.0, high=51.0, low=49.0, close=50.0)],
        },
        candidate_legs=[_leg(instrument_id="BBB")],
        candidate_as_of=DAY,
        universe_instruments=["AAA"],
    )

    candidate = next(row for row in artifact["arms"] if row["arm"] == ARM_CANDIDATE)
    assert candidate["measured"] is False
    assert candidate["reason"] == "candidate_outside_universe:BBB"
    assert artifact["audit"]["pointInTime"]["universeSource"] == "declared"


def test_derived_universe_is_declared_as_not_evaluated() -> None:
    artifact = build_as_run_artifact(
        day=DAY,
        account_id="acc-1",
        legs=[_leg()],
        fills=[],
        bars_by_instrument={"AAA": [_bar("2026-01-02", open_=100.0, high=101.0, low=99.0, close=100.0)]},
    )

    certification = certify_artifact(artifact)

    assert artifact["audit"]["pointInTime"]["universeSource"] == "derived"
    assert certification.verdict == "not_certified"
    assert "initial_state" in certification.not_evaluated
    assert "initial_state:universe_not_declared" in certification.reasons


def test_later_bars_do_not_change_earlier_decisions() -> None:
    legs = [_leg()]
    closing = [_bar("2026-01-02", open_=100.0, high=104.0, low=99.0, close=103.0)]
    closing[0] = OhlcvBar(
        timestamp="2026-01-02", open=95.0, high=104.0, low=94.0, close=103.0, volume=1_000
    )
    future = [_bar("2026-01-03", open_=103.0, high=180.0, low=102.0, close=179.0)]

    prefix = run_hold_arm(legs, {"AAA": closing}, after=DAY, cost_bps=0.0)
    full = run_hold_arm(legs, {"AAA": closing + future}, after=DAY, cost_bps=0.0)

    assert prefix.decisions == full.decisions
    assert prefix.realized_r == full.realized_r


def test_verify_bars_manifest_detects_one_changed_bar() -> None:
    bars = {
        "AAA": [
            _bar("2026-01-02", open_=100.0, high=105.0, low=99.0, close=104.0),
            _bar("2026-01-03", open_=104.0, high=111.0, low=103.0, close=110.0),
        ]
    }
    artifact = _certifiable_artifact()

    assert verify_bars_manifest(artifact["audit"]["data"]["barsManifest"], bars) == ()

    tampered = {"AAA": [bars["AAA"][0], _bar("2026-01-03", open_=104.0, high=111.0, low=103.0, close=109.0)]}
    assert verify_bars_manifest(artifact["audit"]["data"]["barsManifest"], tampered) == (
        "bars_hash_mismatch:AAA",
    )


def test_tampered_bar_breaks_real_market_data() -> None:
    artifact = _certifiable_artifact()
    artifact["audit"]["data"]["barsManifest"]["AAA"][0][1] = "b" * 64

    certification = certify_artifact(artifact)

    assert certification.verdict == "not_certified"
    assert "real_market_data" in certification.failures
    assert "real_market_data:bars_hash_mismatch" in certification.reasons


def test_tampered_params_break_audit() -> None:
    artifact = _certifiable_artifact()
    artifact["audit"]["params"]["universe"] = "otro"

    certification = certify_artifact(artifact)

    assert certification.verdict == "not_certified"
    assert "audit" in certification.failures
    assert "audit:params_hash_mismatch" in certification.reasons


def test_tampered_bump_breaks_artifact_integrity() -> None:
    artifact = _certifiable_artifact()
    artifact["audit"]["versions"]["bump"] = "otro-bump"

    certification = certify_artifact(artifact)

    assert certification.verdict == "not_certified"
    assert "artifact_integrity" in certification.failures
    assert "artifact_integrity:artifact_hash_mismatch" in certification.reasons


def test_tampered_result_breaks_artifact_integrity() -> None:
    artifact = _certifiable_artifact()
    as_run_arm = next(row for row in artifact["arms"] if row["arm"] == ARM_AS_RUN)
    as_run_arm["realizedR"] = 99.0

    certification = certify_artifact(artifact)

    assert certification.verdict == "not_certified"
    assert "artifact_integrity" in certification.failures


def test_legacy_artifact_without_manifest_or_params_is_not_certified() -> None:
    artifact = _certifiable_artifact()
    del artifact["audit"]["data"]["barsManifest"]
    del artifact["audit"]["params"]

    certification = certify_artifact(artifact)

    assert certification.verdict == "not_certified"
    assert "real_market_data" in certification.not_evaluated
    assert "audit" in certification.not_evaluated
    assert "real_market_data:bars_manifest_missing" in certification.reasons
    assert "audit:params_not_declared" in certification.reasons
