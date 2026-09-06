"""LIVE_EXECUTION_UNLOCKED — fail-closed sandbox gate."""

from __future__ import annotations

import pytest

from bolsa_application.live_execution_runtime import (
    LIVE_EXECUTION_UNLOCK_ENV,
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
