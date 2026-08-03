"""Tests del circuit breaker Yahoo (sin red)."""

from __future__ import annotations

import pytest

from bolsa_market.yahoo_circuit_breaker import (
    CircuitState,
    YahooCircuitBreaker,
    YahooCircuitOpenError,
)


def test_opens_after_threshold_failures() -> None:
    cb = YahooCircuitBreaker(failure_threshold=3, cooldown_sec=60)
    for _ in range(3):
        cb.before_call()
        cb.record_failure()
    assert cb.state == CircuitState.OPEN
    with pytest.raises(YahooCircuitOpenError):
        cb.before_call()


def test_half_open_then_close_on_successes() -> None:
    cb = YahooCircuitBreaker(failure_threshold=2, cooldown_sec=0.0, success_threshold=2)
    cb.before_call()
    cb.record_failure()
    cb.before_call()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    # cooldown 0 → half_open en el siguiente before_call
    cb.before_call()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    cb.before_call()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_snapshot_keys() -> None:
    cb = YahooCircuitBreaker()
    snap = cb.snapshot()
    assert snap["state"] == "closed"
    assert "total_requests" in snap
