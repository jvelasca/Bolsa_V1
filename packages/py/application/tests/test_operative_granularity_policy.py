"""Tests de la política de granularidad operativa (entorno -> VO, fail-closed)."""

from __future__ import annotations

import pytest

from bolsa_application.operative_granularity_policy import (
    OPERATIVE_GRANULARITY_ENV,
    operative_signal_timeframe,
    resolve_operative_granularity,
)
from bolsa_domain.errors import UnsupportedGranularityError
from bolsa_domain.operative_granularity import (
    DAILY_GRANULARITY,
    GranularityRejection,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(OPERATIVE_GRANULARITY_ENV, raising=False)


def test_default_resolves_to_daily() -> None:
    assert resolve_operative_granularity() is DAILY_GRANULARITY


def test_explicit_env_resolves_to_daily(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OPERATIVE_GRANULARITY_ENV, "1d")
    assert resolve_operative_granularity() is DAILY_GRANULARITY


def test_fallback_is_used_when_env_is_empty() -> None:
    assert resolve_operative_granularity("1d") is DAILY_GRANULARITY


def test_env_takes_precedence_over_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OPERATIVE_GRANULARITY_ENV, "1d")
    assert resolve_operative_granularity("1wk") is DAILY_GRANULARITY


def test_weekly_env_is_rejected_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OPERATIVE_GRANULARITY_ENV, "1wk")
    with pytest.raises(UnsupportedGranularityError) as excinfo:
        resolve_operative_granularity()
    assert excinfo.value.reason is GranularityRejection.DECISION_NOT_ENABLED


def test_weekly_fallback_is_rejected_fail_closed() -> None:
    # La configuración histórica (``AUTO_ENGINE_SIM_V2_TIMEFRAME=1wk``) también pasa
    # por el gate: deja de colarse en silencio.
    with pytest.raises(UnsupportedGranularityError) as excinfo:
        resolve_operative_granularity("1wk")
    assert excinfo.value.reason is GranularityRejection.DECISION_NOT_ENABLED


def test_unknown_granularity_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OPERATIVE_GRANULARITY_ENV, "4h")
    with pytest.raises(UnsupportedGranularityError) as excinfo:
        resolve_operative_granularity()
    assert excinfo.value.reason is GranularityRejection.UNKNOWN_GRANULARITY


def test_signal_timeframe_is_derived_from_decision_clock() -> None:
    assert operative_signal_timeframe(DAILY_GRANULARITY) == "1d"
