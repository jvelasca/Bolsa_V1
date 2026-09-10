"""V2.27 / A10 — cableado real del universo ESTUDIO al Auto Orchestrator.

El ``AutoOrchestrator`` depende de ``resolve_universe: Callable[[], Awaitable[Any]]``
y espera un objeto con ``status`` (``ok``/``empty``/``unavailable``) e
``instrument_ids``. Ese contrato ya lo cumple ``resolve_estudio_universe`` (Paper
Desk), pero nunca se había cableado al proceso AUTO.

Este módulo es **solo composición**: reutiliza el resolver existente en lugar de
duplicar la lógica de ESTUDIO. El universo canónico del AUTO pasa a ser la lista
Estudio; ``AUTO_ORCHESTRATOR_INSTRUMENTS`` queda como allowlist/fallback opcional.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bolsa_application.paper_desk_entry import (
    EstudioListPort,
    resolve_estudio_universe,
)

__all__ = ["make_estudio_universe_resolver"]


def make_estudio_universe_resolver(
    estudio_list: EstudioListPort | None,
) -> Callable[[], Any]:
    """Devuelve el ``resolve_universe`` async para ``OrchestratorDeps``.

    ``estudio_list is None`` no lanza: el resolver devuelve ``unavailable`` y el
    orquestador queda fail-closed (sin candidatas inventadas).
    """

    async def _resolve() -> Any:
        return await resolve_estudio_universe(estudio_list)

    return _resolve
