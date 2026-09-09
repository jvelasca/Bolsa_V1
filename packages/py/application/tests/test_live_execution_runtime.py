"""LIVE money path — fail-closed sandbox con DOS barreras independientes (A8·M0).

Regla P0 (A8): ``AUTO → SIMULATED ONLY`` · ``AUTO → NEVER REAL LIVE``. El POST
real exige AMBAS ``LIVE_EXECUTION_AUTHORIZED`` y ``LIVE_EXECUTION_UNLOCKED``.
"""

from __future__ import annotations

import pytest

from bolsa_application.live_execution_runtime import (
    LIVE_EXECUTION_AUTHORIZE_ENV,
    LIVE_EXECUTION_UNLOCK_ENV,
    live_execution_authorized,
    live_execution_ready,
    live_execution_unlocked,
)


def test_live_execution_unlocked_default_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_EXECUTION_UNLOCK_ENV, raising=False)
    assert live_execution_unlocked() is False


@pytest.mark.parametrize("raw", ["1", "true", "YES", "on"])
def test_live_execution_unlocked_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    monkeypatch.setenv(LIVE_EXECUTION_UNLOCK_ENV, raw)
    assert live_execution_unlocked() is True


@pytest.mark.parametrize("raw", ["0", "false", "", "maybe"])
def test_live_execution_unlocked_rejects_non_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    monkeypatch.setenv(LIVE_EXECUTION_UNLOCK_ENV, raw)
    assert live_execution_unlocked() is False


def test_live_execution_authorized_default_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_EXECUTION_AUTHORIZE_ENV, raising=False)
    assert live_execution_authorized() is False


@pytest.mark.parametrize("raw", ["1", "true", "YES", "on"])
def test_live_execution_authorized_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    monkeypatch.setenv(LIVE_EXECUTION_AUTHORIZE_ENV, raw)
    assert live_execution_authorized() is True


@pytest.mark.parametrize("raw", ["0", "false", "", "maybe", "off", "enabled"])
def test_live_execution_authorized_rejects_non_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    monkeypatch.setenv(LIVE_EXECUTION_AUTHORIZE_ENV, raw)
    assert live_execution_authorized() is False


@pytest.mark.parametrize(
    "authorized, unlocked, expect_ready",
    [
        # Una sola barrera nunca abre la vía (fail-closed).
        (None, None, False),
        ("1", None, False),
        (None, "1", False),
        ("0", "1", False),
        ("1", "0", False),
        # AMBAS opt-in → ready.
        ("1", "1", True),
        ("true", "yes", True),
    ],
)
def test_live_execution_ready_two_independent_gates(
    monkeypatch: pytest.MonkeyPatch,
    authorized: str | None,
    unlocked: str | None,
    expect_ready: bool,
) -> None:
    for var, val in (
        (LIVE_EXECUTION_AUTHORIZE_ENV, authorized),
        (LIVE_EXECUTION_UNLOCK_ENV, unlocked),
    ):
        if val is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv(var, val)
    assert live_execution_ready() is expect_ready
