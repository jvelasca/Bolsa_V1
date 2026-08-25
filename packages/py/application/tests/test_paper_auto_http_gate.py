"""Ciclo I3 — HTTP paper_auto fail-closed sin thaw."""

from __future__ import annotations

import pytest

from bolsa_application.paper_auto_http_gate import (
    PAPER_AUTO_ENV_BLOCKED,
    PaperAutoEnvBlockedError,
    require_http_paper_auto_env,
)


def test_inform_alert_live_auto_skip_env_gate():
    require_http_paper_auto_env("inform_only")
    require_http_paper_auto_env("alert")
    require_http_paper_auto_env("live_auto")
    require_http_paper_auto_env(None)
    require_http_paper_auto_env("")


def test_paper_auto_blocked_without_env(monkeypatch):
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    with pytest.raises(PaperAutoEnvBlockedError) as exc:
        require_http_paper_auto_env("paper_auto")
    assert str(exc.value) == PAPER_AUTO_ENV_BLOCKED


def test_paper_auto_allowed_with_env(monkeypatch):
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    require_http_paper_auto_env("paper_auto")
