"""Tests de cadencia: épocas no solapadas, ventana móvil y detector de solape."""

from __future__ import annotations

import pytest

from bolsa_application.strategy_verification_cadence import (
    SAMPLE_KIND_ROLLING,
    STATUS_CLOSED,
    STATUS_OPEN,
    VERDICT_INSUFFICIENT_INDEPENDENT,
    VerificationEpoch,
    assert_non_overlapping,
    build_epochs,
    build_rolling_window,
    independent_sample_gate,
    independent_samples,
    overlaps,
)
from bolsa_application.strategy_verification_profile import (
    VerificationProfileError,
    default_profile,
)


def _profile(every_days: int = 30, anchor: str | None = None):
    return default_profile(
        profile_id="p",
        account_scope="acct",
        universe_instruments=["AAA"],
        every_days=every_days,
        anchor_day=anchor,
    )


def test_epochs_are_contiguous_and_only_the_last_is_open() -> None:
    epochs = build_epochs(_profile(), first_day="2026-01-01", today="2026-04-01")
    assert len(epochs) >= 3
    for previous, current in zip(epochs, epochs[1:], strict=False):
        assert previous.to_day == current.day
        assert not overlaps(previous, current)
    assert [epoch.status for epoch in epochs[:-1]] == [STATUS_CLOSED] * (len(epochs) - 1)
    assert epochs[-1].status == STATUS_OPEN


def test_epochs_do_not_overlap_across_a_leap_year() -> None:
    epochs = build_epochs(_profile(), first_day="2028-01-31", today="2028-05-01")
    assert_non_overlapping(epochs)
    # El 29 de febrero tiene que caer dentro de ALGUNA época, sin duplicarse ni perderse.
    covering = [e for e in epochs if e.day <= "2028-02-29" < e.to_day]
    assert len(covering) == 1


def test_same_day_twice_is_detected_as_overlap() -> None:
    a = VerificationEpoch("e1", 0, "2026-01-01", "2026-01-31", STATUS_CLOSED)
    b = VerificationEpoch("e2", 1, "2026-01-15", "2026-02-15", STATUS_CLOSED)
    assert overlaps(a, b)
    with pytest.raises(VerificationProfileError):
        assert_non_overlapping([a, b])


def test_contiguous_epochs_do_not_overlap() -> None:
    a = VerificationEpoch("e1", 0, "2026-01-01", "2026-01-31", STATUS_CLOSED)
    b = VerificationEpoch("e2", 1, "2026-01-31", "2026-03-02", STATUS_CLOSED)
    assert not overlaps(a, b)


def test_anchor_is_stable_when_the_window_grows() -> None:
    short = build_epochs(_profile(), first_day="2026-01-01", today="2026-03-01")
    long = build_epochs(_profile(), first_day="2026-01-01", today="2026-06-01")
    assert [epoch.day for epoch in short] == [epoch.day for epoch in long[: len(short)]]


def test_open_epoch_is_not_a_sample() -> None:
    epochs = build_epochs(_profile(), first_day="2026-01-01", today="2026-04-01")
    assert epochs[-1].is_sample is False
    assert 0 < len(independent_samples(epochs)) < len(epochs)


def test_rolling_window_is_declared_overlapping_and_never_a_sample() -> None:
    rolling = build_rolling_window(_profile(), today="2026-06-01")
    assert rolling.kind == SAMPLE_KIND_ROLLING
    assert rolling.overlapping is True
    assert rolling.is_sample is False


def test_gate_fails_with_overlapping_windows() -> None:
    overlapping = VerificationEpoch("e1", 0, "2026-01-01", "2026-02-01", STATUS_CLOSED, overlapping=True)
    gate = independent_sample_gate([overlapping] * 12, required=12)
    assert gate["passed"] is False
    assert gate["reason"] == VERDICT_INSUFFICIENT_INDEPENDENT


def test_gate_fails_with_too_few_independent_samples() -> None:
    epochs = build_epochs(_profile(), first_day="2026-01-01", today="2026-05-01")
    gate = independent_sample_gate(epochs, required=12)
    assert gate["passed"] is False
    assert str(gate["reason"]).startswith("insufficient_sample:")


def test_gate_passes_with_enough_independent_epochs() -> None:
    epochs = build_epochs(_profile(every_days=7), first_day="2026-01-01", today="2026-06-01")
    gate = independent_sample_gate(epochs, required=12)
    assert gate["passed"] is True
    assert gate["reason"] is None


def test_empty_window_returns_no_epochs() -> None:
    assert build_epochs(_profile(), first_day="2026-06-01", today="2026-06-01") == ()
