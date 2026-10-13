"""V2.88.123 / S2 — acoplamiento (env-gated) del watch diario AUTO al universo ESTUDIO.

La lane de **operación diaria** (``auto_simulation_worker`` / ``paper_auto_engine_worker``)
nacía desacoplada del universo canónico: su watch salía de un **CSV estático**
(``AUTO_ENGINE_SIMULATED_WATCH`` / ``AUTO_ENGINE_DRY_WATCH``, default ``AAA,IBEX``) y un
valor añadido a ESTUDIO no entraba solo en el día AUTO (hallazgo ``S2`` declarado en
``v2.88.122``).

Este módulo aporta la composición que cierra el hueco **sin duplicar** la lógica de
ESTUDIO: reutiliza ``resolve_estudio_universe`` (el MISMO resolver del Paper Desk y del
orquestador) sobre un puerto session-scoped. El contrato es el del orquestador
(``auto_orchestrator_worker._instruments_for_cycle``):

* ESTUDIO es el universo **canónico**; el CSV pasa a **allowlist que intersecta**
  (vacío ⇒ universo completo; sin intersección ⇒ watch vacío).
* **Fail-closed**: ``unavailable``/``empty``/error/lista vacía ⇒ watch vacío (no se
  opera); la allowlist **nunca** sustituye al universo.

Con el flag ``AUTO_ENGINE_SIMULATED_WATCH_FROM_ESTUDIO`` OFF (default) esta composición
no se invoca y la lane diaria se comporta byte-idéntica a hoy (CSV estático).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bolsa_application.paper_desk_entry import (
    EstudioListPort,
    resolve_estudio_universe,
)

__all__ = [
    "DailyWatchResolution",
    "SessionScopedEstudioList",
    "resolve_daily_watch",
]

#: Estados del resolver canónico (mismos que ``daily_ops_report``/``paper_desk_entry``).
_STATUS_OK = "ok"
_STATUS_UNAVAILABLE = "unavailable"


class SessionScopedEstudioList:
    """``EstudioListPort`` real: abre una sesión por ``execute`` (lista ``estudio``).

    ``resolve_estudio_universe`` solo necesita un objeto con ``execute(list_id)``;
    este adaptador materializa el puerto con ``GetInstrumentList`` y una sesión
    propia por llamada, sin retener sesiones de larga vida.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def execute(self, list_id: str) -> Any:
        from bolsa_api.api.dependencies import get_list_repository
        from bolsa_application.lists import GetInstrumentList

        async with self._session_factory() as session:
            return await GetInstrumentList(get_list_repository(session)).execute(list_id)


@dataclass(frozen=True)
class DailyWatchResolution:
    """Resolución del watch diario: universo ESTUDIO ∩ allowlist (fail-closed).

    ``status`` es el del resolver canónico (``ok``/``empty``/``unavailable``).
    ``instrument_ids`` es el watch efectivo (ya intersectado con ``allowlist``);
    queda vacío cuando el universo no está ``ok`` (nunca se cae a la allowlist).
    """

    status: str
    instrument_ids: tuple[str, ...] = ()
    allowlist: tuple[str, ...] = field(default_factory=tuple)


async def resolve_daily_watch(
    estudio_list: EstudioListPort | None,
    *,
    allowlist: tuple[str, ...] = (),
) -> DailyWatchResolution:
    """Universo ESTUDIO ∩ allowlist. Fail-closed: sin ``ok`` ⇒ watch vacío.

    Reutiliza ``resolve_estudio_universe`` (no reimplementa ESTUDIO). La allowlist
    solo **intersecta**: un CSV sin intersección deja el watch vacío, jamás sustituye
    al universo. ``estudio_list is None`` no lanza: devuelve ``unavailable`` (watch
    vacío), de modo que el llamante queda fail-closed.
    """
    resolution = await resolve_estudio_universe(estudio_list)
    status = str(getattr(resolution, "status", "") or "") or _STATUS_UNAVAILABLE
    ids = tuple(str(i) for i in (getattr(resolution, "instrument_ids", None) or []) if i)
    allowed = tuple(s for s in allowlist if s)
    if status != _STATUS_OK or not ids:
        return DailyWatchResolution(status=status, allowlist=allowed)
    if allowed:
        wanted = set(allowed)
        ids = tuple(i for i in ids if i in wanted)
    return DailyWatchResolution(status=status, instrument_ids=ids, allowlist=allowed)
