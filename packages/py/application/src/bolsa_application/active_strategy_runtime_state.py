"""ActiveStrategyRuntimeState — estados operativos de una estrategia ACTIVE (AUTO 2.0 · P2).

La máquina de estados del embudo (``StrategyLifecycleState``) termina en ACTIVE. Este
módulo añade, ENCIMA de ACTIVE y sin tocarla, el estado **operativo/runtime** que
gobierna cuánto puede operar una estrategia activa en cada turno::

    ACTIVE → ACTIVE_PAUSED | ACTIVE_EXIT_ONLY | ACTIVE_DEGRADED | RETIRED

- ``ACTIVE``           — operando con normalidad (entra y gestiona).
- ``ACTIVE_PAUSED``    — no entra (pausa administrativa), pero gestiona posiciones.
- ``ACTIVE_EXIT_ONLY`` — no entra; solo gestiona/cierra posiciones (régimen adverso).
- ``ACTIVE_DEGRADED``  — salud degradada; no entra (vuelve al LAB por el ciclo de
  vigilancia), gestiona/cierra lo abierto.
- ``RETIRED``          — terminal; ninguna actividad.

Fail-closed: sin estado reconocible ⇒ ``ACTIVE_EXIT_ONLY`` (no se inventa permiso de
entrada). Este módulo NO ejecuta transiciones del embudo: solo clasifica el estado
operativo a partir de señales de salud/régimen/pausa.
"""

from __future__ import annotations

from typing import Literal

ActiveStrategyRuntimeState = Literal[
    "ACTIVE",
    "ACTIVE_PAUSED",
    "ACTIVE_EXIT_ONLY",
    "ACTIVE_DEGRADED",
    "RETIRED",
]

# Estados que NO permiten entradas nuevas (fail-closed).
_NO_ENTRY_STATES: frozenset[str] = frozenset(
    {"ACTIVE_PAUSED", "ACTIVE_EXIT_ONLY", "ACTIVE_DEGRADED", "RETIRED"}
)


def derive_runtime_state(
    *,
    retired: bool = False,
    paused: bool = False,
    degraded: bool = False,
    regime_exit_only: bool = False,
) -> ActiveStrategyRuntimeState:
    """Clasifica el estado operativo de una estrategia activa (precedencia documentada).

    Orden de precedencia (el primero que aplica gana):

    1. ``retired`` → RETIRED (terminal).
    2. ``degraded`` → ACTIVE_DEGRADED (salud insuficiente).
    3. ``paused`` → ACTIVE_PAUSED (pausa administrativa).
    4. ``regime_exit_only`` → ACTIVE_EXIT_ONLY (régimen adverso).
    5. si no → ACTIVE.
    """
    if retired:
        return "RETIRED"
    if degraded:
        return "ACTIVE_DEGRADED"
    if paused:
        return "ACTIVE_PAUSED"
    if regime_exit_only:
        return "ACTIVE_EXIT_ONLY"
    return "ACTIVE"


def runtime_allows_new_entries(state: ActiveStrategyRuntimeState | str | None) -> bool:
    """True solo si el estado operativo permite entradas nuevas (fail-closed)."""
    return str(state or "ACTIVE_EXIT_ONLY").strip().upper() == "ACTIVE"


def runtime_allows_position_management(state: ActiveStrategyRuntimeState | str | None) -> bool:
    """True si el estado permite gestionar/cerrar posiciones (todo menos RETIRED)."""
    return str(state or "RETIRED").strip().upper() != "RETIRED"
