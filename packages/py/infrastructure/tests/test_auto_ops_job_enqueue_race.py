"""D-4 (auditoría 2) — recuperación de la carrera del índice único, sin PostgreSQL.

El índice parcial ``auto_ops_jobs_active_job_key`` resuelve la carrera real, pero la
RELECTURA del perdedor puede llegar tarde: si el ganador termina (``completed``/``failed``)
entre el choque y la relectura, ``find_active`` no encuentra nada y el código anterior
re-lanzaba ``IntegrityError`` ⇒ un 500 en el POST. Este módulo fija el contrato nuevo:

* un choque seguido de un hueco YA LIBRE se reintenta y la petición SÍ encola
  (``created=True``);
* dos choques seguidos devuelven el activo que ocupa el hueco (``created=False``);
* si ni siquiera tras dos choques hay un activo que devolver, el error se propaga (nunca
  se silencia un fallo de integridad).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from bolsa_domain.entities.auto_ops_job import JOB_KIND_ESTUDIO_DAILY
from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
    SqlAlchemyAutoOpsJobRepository,
)


class _Result:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any:
        return self._row


class _Nested:
    async def __aenter__(self) -> _Nested:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _RaceSession:
    """Sesión falsa: ``find_active`` consume la secuencia y ``flush`` choca N veces."""

    def __init__(self, *, actives: list[Any], flush_failures: int) -> None:
        self._actives = list(actives)
        self._flush_failures = flush_failures
        self.flushes = 0

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(self._actives.pop(0) if self._actives else None)

    def begin_nested(self) -> _Nested:
        return _Nested()

    def add(self, _row: Any) -> None:
        return None

    async def flush(self) -> None:
        self.flushes += 1
        if self.flushes <= self._flush_failures:
            raise IntegrityError("INSERT", {}, Exception("active_job_key"))


@pytest.mark.asyncio
async def test_a_collision_followed_by_a_freed_slot_reinserts_and_reports_created() -> None:
    """El ganador terminó antes de la relectura ⇒ se reintenta y ESTA petición encola."""
    session = _RaceSession(actives=[None, None], flush_failures=1)
    repo = SqlAlchemyAutoOpsJobRepository(session)  # type: ignore[arg-type]

    outcome = await repo.enqueue_with_outcome(
        kind=JOB_KIND_ESTUDIO_DAILY, day="2026-10-18", account_id="acc-1"
    )

    assert outcome.created is True
    assert session.flushes == 2, "el hueco liberado debe reintentar el INSERT"
    assert outcome.job.kind == JOB_KIND_ESTUDIO_DAILY
    assert outcome.job.account_id == "acc-1"


@pytest.mark.asyncio
async def test_two_collisions_return_the_active_job_that_owns_the_slot() -> None:
    """El hueco sigue ocupado tras el reintento ⇒ se devuelve el activo (``created=False``)."""
    winner = type(
        "Row",
        (),
        {
            "id": "job-winner",
            "kind": JOB_KIND_ESTUDIO_DAILY,
            "status": "queued",
            "day": "2026-10-18",
            "account_id": "acc-1",
            "payload": {"symbol": "AAA"},
            "progress": {},
            "result": {},
            "error": None,
            "attempt": 0,
            "created_at": None,
            "started_at": None,
            "finished_at": None,
            "heartbeat_at": None,
        },
    )()
    session = _RaceSession(actives=[None, None, winner], flush_failures=2)
    repo = SqlAlchemyAutoOpsJobRepository(session)  # type: ignore[arg-type]

    outcome = await repo.enqueue_with_outcome(
        kind=JOB_KIND_ESTUDIO_DAILY, day="2026-10-18", account_id="acc-1"
    )

    assert outcome.created is False
    assert outcome.job.id == "job-winner"


@pytest.mark.asyncio
async def test_no_active_after_two_collisions_propagates_the_integrity_error() -> None:
    """Sin activo que devolver, el ``IntegrityError`` NO se silencia (no se inventa un job)."""
    session = _RaceSession(actives=[None, None, None], flush_failures=2)
    repo = SqlAlchemyAutoOpsJobRepository(session)  # type: ignore[arg-type]

    with pytest.raises(IntegrityError):
        await repo.enqueue_with_outcome(
            kind=JOB_KIND_ESTUDIO_DAILY, day="2026-10-18", account_id="acc-1"
        )
