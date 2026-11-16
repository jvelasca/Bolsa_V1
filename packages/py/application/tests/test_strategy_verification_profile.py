"""Tests del perfil de verificación (pre-registro, hash y fail-closed)."""

from __future__ import annotations

import pytest

from bolsa_application.dia_d_as_run import AsRunExecutionModel
from bolsa_application.strategy_verification_profile import (
    StrategyVerificationProfileV1,
    VerificationCadence,
    VerificationCandidatePolicy,
    VerificationDecisionPolicy,
    VerificationProfileError,
    VerificationSamples,
    VerificationThresholds,
    default_profile,
)

UNIVERSE = ("AAA", "BBB")


def _profile(**overrides: object) -> StrategyVerificationProfileV1:
    base: dict[str, object] = {
        "profile_id": "verif-auto",
        "account_scope": "acct-1",
        "universe_instruments": UNIVERSE,
    }
    base.update(overrides)
    return StrategyVerificationProfileV1(**base)  # type: ignore[arg-type]


def test_defaults_are_literal_and_min_sample_is_twelve() -> None:
    profile = _profile()
    payload = profile.to_dict()
    assert payload["samples"]["minCohortSamples"] == 12
    assert payload["cadence"]["everyDays"] == 30
    assert payload["cadence"]["rollingEnabled"] is True
    assert payload["decision"]["allowAutoActivation"] is False
    assert payload["candidate"]["requirePointInTime"] is True
    assert payload["universeInstruments"] == ["AAA", "BBB"]


def test_hash_is_stable_and_order_independent_for_universe() -> None:
    first = _profile().hash()
    second = _profile(universe_instruments=("BBB", "AAA", "AAA")).hash()
    assert first == second
    assert first == _profile().hash()


def test_changing_a_threshold_changes_the_hash() -> None:
    base = _profile().hash()
    changed = _profile(thresholds=VerificationThresholds(min_excess_mean_r=0.5)).hash()
    assert base != changed


def test_changing_the_execution_model_changes_the_hash() -> None:
    base = _profile().hash()
    changed = _profile(
        execution=AsRunExecutionModel(commission_bps=8.0, max_participation_pct=0.05)
    ).hash()
    assert base != changed


def test_min_cohort_samples_cannot_drop_below_twelve() -> None:
    with pytest.raises(VerificationProfileError):
        VerificationSamples(min_cohort_samples=11)


def test_auto_activation_is_rejected() -> None:
    with pytest.raises(VerificationProfileError):
        VerificationDecisionPolicy(allow_auto_activation=True)


def test_point_in_time_candidate_is_required() -> None:
    with pytest.raises(VerificationProfileError):
        VerificationCandidatePolicy(require_point_in_time=False)


def test_declared_universe_is_mandatory() -> None:
    with pytest.raises(VerificationProfileError):
        _profile(universe_instruments=())


def test_required_arms_are_enforced() -> None:
    with pytest.raises(VerificationProfileError):
        _profile(arms=("as_run", "cash"))


def test_unknown_arms_are_rejected() -> None:
    with pytest.raises(VerificationProfileError):
        _profile(arms=("as_run", "cash", "market_bh", "oracle"))


def test_zero_cost_execution_is_rejected() -> None:
    with pytest.raises(VerificationProfileError):
        _profile(execution=AsRunExecutionModel(commission_bps=0.0, spread_bps=0.0))


def test_cadence_rejects_nonsense_values() -> None:
    with pytest.raises(VerificationProfileError):
        VerificationCadence(every_days=0)
    with pytest.raises(VerificationProfileError):
        VerificationCadence(anchor_day="2026-02-30")
    with pytest.raises(VerificationProfileError):
        VerificationCadence(rolling_lookback_days=0)


def test_cadence_accepts_a_leap_day_anchor() -> None:
    assert VerificationCadence(anchor_day="2028-02-29").anchor_day == "2028-02-29"


def test_thresholds_bounds() -> None:
    with pytest.raises(VerificationProfileError):
        VerificationThresholds(min_share_epochs_not_worse=0.0)
    with pytest.raises(VerificationProfileError):
        VerificationThresholds(min_share_epochs_not_worse=1.5)
    with pytest.raises(VerificationProfileError):
        VerificationThresholds(max_drawdown_pct=0.0)


def test_default_profile_helper_is_valid_and_pure() -> None:
    profile = default_profile(
        profile_id="p1", account_scope="acct", universe_instruments=list(UNIVERSE)
    )
    assert profile.universe_instruments == UNIVERSE
    assert profile.hash() == profile.hash()
    assert "activationAllowed" not in profile.to_dict()
