"""LIVE execution unlock — fail-closed sandbox for VIRTUAL Confirm.

``brokerVenue=live`` enables Confirm LIVE VIRTUAL chrome.
Sending to the XTB bridge requires an explicit unlock (default OFF).
≠ PAPER_D_EXECUTE (paper AUTO only) · ≠ thaw · ≠ Accept LIVE.
"""

from __future__ import annotations

import os

LIVE_EXECUTION_UNLOCK_ENV = "LIVE_EXECUTION_UNLOCKED"


def live_execution_unlocked() -> bool:
    """True only when env opt-in is set. Default fail-closed = False."""
    raw = (os.getenv(LIVE_EXECUTION_UNLOCK_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
