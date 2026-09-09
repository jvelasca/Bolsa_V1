"""LIVE real money path — fail-closed sandbox with TWO independent barriers (A8 · M0).

Regla P0 (A8, congelada): ``AUTO → SIMULATED ONLY`` · ``AUTO → NEVER REAL LIVE``.
LIVE real requiere DOS barreras independientes, ambas de autoridad humana y por
configuración de entorno (nunca decidibles/activables por el propio runtime o por
código autónomo/AUTO):

  1. ``LIVE_EXECUTION_AUTHORIZED``  — habilitación/release de capacidad (2ª barrera).
  2. ``LIVE_EXECUTION_UNLOCKED``    — desbloqueo operativo de la vía al bridge (1ª).

La vía real en ``XtbBrokerAdapter.submit`` NO se abre salvo que AMBAS retornen
opt-in (fail-closed). Ninguna ruta AUTO (ExecutionRouter / ExecutePositionPolicy /
PaperDesk / Paper-D) construye jamás un adapter: ver test estructural M0.

≠ ``PAPER_D_EXECUTE`` (paper AUTO only) · ≠ thaw · ≠ Accept LIVE.
NOTA M0/A8: esto NO hace LIVE real "certificado"; lo mantiene *imposible por
arquitectura* salvo autorización humana explícita doble en una fase posterior.
"""

from __future__ import annotations

import os

# 1ª barrera operativa (desbloqueo al vía; ya existente en pre-M0).
LIVE_EXECUTION_UNLOCK_ENV = "LIVE_EXECUTION_UNLOCKED"
# 2ª barrera independiente de capacidad (A8 · M0).
LIVE_EXECUTION_AUTHORIZE_ENV = "LIVE_EXECUTION_AUTHORIZED"

# Tokens de opt-in estrictos (fail-closed: todo lo demás es off).
_OPT_IN = {"1", "true", "yes", "on"}


def _opt_in(raw: str | None) -> bool:
    """Solo tokens explícitos activan; cualquier otro valor es off (fail-closed)."""
    return ((raw or "").strip().lower()) in _OPT_IN


def live_execution_authorized() -> bool:
    """Barrera 2 (capacidad). Default False."""
    return _opt_in(os.getenv(LIVE_EXECUTION_AUTHORIZE_ENV))


def live_execution_unlocked() -> bool:
    """Barrera 1 (operativa). Default False."""
    return _opt_in(os.getenv(LIVE_EXECUTION_UNLOCK_ENV))


def live_execution_ready() -> bool:
    """AMBAS barreras independientes a la vez. Único predicado que abre el POST
    del bridge en producción (XtbBrokerAdapter con checks sin inyectar)."""
    return live_execution_authorized() and live_execution_unlocked()
