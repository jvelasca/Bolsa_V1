"""Ciclo I3 — HTTP ``paper_auto`` exige ``PAPER_D_EXECUTE`` (sin thaw).

Paper D ya bloquea execute sin env. ``POST /execution-policies/{id}/route`` y
``POST /scans/jobs/{id}/execute`` no lo hacían.

Este gate **no** vive en ``ExecutionRouter``: la batería spine llama al Router
sin el env. ``inform_only`` / ``alert`` / ``live_auto`` no pasan por aquí.
"""

from __future__ import annotations

from bolsa_application.paper_d_propose import paper_d_execute_allowed

PAPER_AUTO_ENV_BLOCKED = "paper_auto_env_blocked"


class PaperAutoEnvBlockedError(Exception):
    """Fill ``paper_auto`` por HTTP bloqueado: flag off."""

    def __init__(self) -> None:
        super().__init__(PAPER_AUTO_ENV_BLOCKED)


def require_http_paper_auto_env(policy_mode: str | None) -> None:
    """No-op salvo ``paper_auto`` sin ``PAPER_D_EXECUTE``."""
    if str(policy_mode or "") != "paper_auto":
        return
    if not paper_d_execute_allowed():
        raise PaperAutoEnvBlockedError()
