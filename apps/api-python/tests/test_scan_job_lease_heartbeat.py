"""DS-1 offline — latido del lease de un scan job ``processing``.

Lo que se puede certificar SIN PostgreSQL (el camino SQL se mide en
``test_scan_job_lease_pg.py``):

* la cadencia se deriva del umbral de caducidad y respeta el suelo;
* el latido usa su PROPIA sesión (nunca la del job) y la cierra en cada tick;
* se detiene en cuanto el job deja de estar ``processing`` (el reaper lo reencoló o terminó);
* un fallo del latido NO tumba el trabajo: sigue intentándolo.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from bolsa_api.background.scan_job_lease import (
    MIN_LEASE_HEARTBEAT_SECONDS,
    lease_heartbeat_interval_seconds,
    scan_job_lease_heartbeat,
    start_scan_job_lease_heartbeat,
    stop_scan_job_lease_heartbeat,
)
from bolsa_infrastructure.database.repositories.scan_job_repository import ScanJobRecord


def _record(job_id: str = "job-1", *, status: str = "processing") -> ScanJobRecord:
    return ScanJobRecord(
        id=job_id,
        status=status,  # type: ignore[arg-type]
        payload={},
        result=None,
        error=None,
        cache_hits=None,
        cache_misses=None,
        tracker_definition_id=None,
        created_at="2026-11-03T09:00:00+00:00",
        updated_at="2026-11-03T09:00:00+00:00",
        completed_at=None,
    )


class _FakeSession:
    """Sesión de mentira: registra commits y cierres, y delega en el repositorio falso."""

    def __init__(self, owner: _FakeFactory) -> None:
        self._owner = owner
        self.commits = 0
        self.closed = False
        self.entered = False

    async def __aenter__(self) -> _FakeSession:
        self.entered = True
        self._owner.opened += 1
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True

    async def commit(self) -> None:
        self.commits += 1


class _FakeFactory:
    """``session_factory`` que crea sesiones nuevas por tick (contrato que el latido exige)."""

    def __init__(self) -> None:
        self.sessions: list[_FakeSession] = []
        self.opened = 0

    def __call__(self) -> _FakeSession:
        session = _FakeSession(self)
        self.sessions.append(session)
        return session


class _FakeRepository:
    """Repositorio falso: por cada llamada consume el siguiente resultado programado."""

    results: list[Any] = []
    calls: list[str] = []

    def __init__(self, _session: Any) -> None:
        pass

    async def renew_processing_lease(self, job_id: str) -> Any:
        type(self).calls.append(job_id)
        if type(self).results:
            return type(self).results.pop(0)
        return None


@pytest.fixture(autouse=True)
def _reset_fake_repository() -> None:
    _FakeRepository.results = []
    _FakeRepository.calls = []


def test_interval_derives_from_the_lease_and_respects_the_floor() -> None:
    """DS-1 — tres latidos caben en la vida del lease; nunca por debajo del suelo."""
    assert lease_heartbeat_interval_seconds(stale_after_seconds=3600.0) == 1200.0
    assert lease_heartbeat_interval_seconds(stale_after_seconds=90.0) == 30.0
    # Umbrales muy cortos no convierten el latido en un bucle que gasta conexiones.
    assert lease_heartbeat_interval_seconds(stale_after_seconds=3.0) == MIN_LEASE_HEARTBEAT_SECONDS


@pytest.mark.asyncio
async def test_heartbeat_stops_as_soon_as_the_job_is_no_longer_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DS-1 — el latido no refresca un job que el reaper ya reencoló (le impediría reclamarlo)."""
    from bolsa_api.background import scan_job_lease as module

    monkeypatch.setattr(module, "SqlAlchemyScanJobRepository", _FakeRepository)
    _FakeRepository.results = [_record(), None]  # segundo tick: ya no está processing
    factory = _FakeFactory()

    await asyncio.wait_for(
        scan_job_lease_heartbeat(factory, "job-1", interval_seconds=0.01), timeout=2.0
    )

    # Dos ticks: el que renovó y el que descubrió que el job ya no era suyo.
    assert _FakeRepository.calls == ["job-1", "job-1"]
    assert len(factory.sessions) == 2
    assert all(session.closed for session in factory.sessions)
    assert all(session.commits == 1 for session in factory.sessions)


@pytest.mark.asyncio
async def test_heartbeat_uses_its_own_session_each_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DS-1 — nunca reutiliza la sesión del job (ahí el UPDATE se encolaría tras el turno)."""
    from bolsa_api.background import scan_job_lease as module

    monkeypatch.setattr(module, "SqlAlchemyScanJobRepository", _FakeRepository)
    _FakeRepository.results = [_record(), _record(), None]
    factory = _FakeFactory()

    await asyncio.wait_for(
        scan_job_lease_heartbeat(factory, "job-1", interval_seconds=0.01), timeout=2.0
    )

    assert len(_FakeRepository.calls) == 3
    assert len(factory.sessions) == 3, "una sesión nueva por tick"
    assert len({id(session) for session in factory.sessions}) == 3


@pytest.mark.asyncio
async def test_a_failing_tick_does_not_kill_the_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DS-1 — un error transitorio de BD no detiene el latido ni tumba el scan."""
    from bolsa_api.background import scan_job_lease as module

    class _FlakyRepository:
        calls = 0

        def __init__(self, _session: Any) -> None:
            pass

        async def renew_processing_lease(self, _job_id: str) -> Any:
            type(self).calls += 1
            if type(self).calls == 1:
                raise RuntimeError("conexión perdida")
            if type(self).calls == 2:
                return _record()
            return None

    monkeypatch.setattr(module, "SqlAlchemyScanJobRepository", _FlakyRepository)
    factory = _FakeFactory()

    await asyncio.wait_for(
        scan_job_lease_heartbeat(factory, "job-1", interval_seconds=0.01), timeout=2.0
    )

    # Falló el primero, renovó el segundo y paró en el tercero: siguió vivo tras el error.
    assert _FlakyRepository.calls == 3


@pytest.mark.asyncio
async def test_stop_cancels_a_running_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    """DS-1 — al terminar el job el latido se cancela y no queda ninguna tarea viva."""
    from bolsa_api.background import scan_job_lease as module

    monkeypatch.setattr(module, "SqlAlchemyScanJobRepository", _FakeRepository)
    _FakeRepository.results = []
    factory = _FakeFactory()

    task = start_scan_job_lease_heartbeat(factory, "job-1", interval_seconds=60.0)
    await asyncio.sleep(0.01)  # deja que arranque y entre en el sleep largo
    assert not task.done()

    await stop_scan_job_lease_heartbeat(task)
    assert task.done()
    assert task.cancelled()

    # Idempotente: parar dos veces no explota.
    await stop_scan_job_lease_heartbeat(task)
