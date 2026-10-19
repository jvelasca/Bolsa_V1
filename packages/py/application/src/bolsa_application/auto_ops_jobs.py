"""Casos de uso — cola durable de trabajos operativos AUTO.

La generación diaria del universo ESTUDIO, la ejecución manual del sandbox DÍA-D y la
verificación DÍA-D de **un valor** comparten la MISMA cola: el scheduler y el botón de la
UI encolan un job y ambos observan el mismo estado
(``queued``/``running``/``completed``/``failed``), el mismo progreso y el mismo registro de
éxito o fallo.

Reglas duras:

* ``UNKNOWN != 0`` — el progreso y el resultado son datos; un hueco se declara vacío.
* Fail-closed — sin cuenta no se puede leer un job de cuenta (se trata como inexistente).
* Una sola corrida activa por ``(kind, cuenta, día)`` (índice único parcial, migración 056).
  En la verificación **por valor** el símbolo viaja en ``payload``: dos símbolos del mismo
  día se serializan (nunca se ejecutan dos replays a la vez) y el segundo recibe el job
  activo del primero, cuyo ``payload.symbol`` permite declararlo en la UI.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Protocol

from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_DIA_D_REPLAY,
    JOB_KIND_DIA_D_VALUE_REPLAY,
    JOB_KIND_ESTUDIO_DAILY,
    AutoOpsJob,
)

__all__ = [
    "AutoOpsJobRepository",
    "EnqueueAutoOpsJob",
    "GetAutoOpsJob",
    "ListAutoOpsJobs",
    "normalize_day",
]


class AutoOpsJobRepository(Protocol):
    """Puerto mínimo de la cola (implementado por ``SqlAlchemyAutoOpsJobRepository``)."""

    async def get(self, job_id: str) -> AutoOpsJob | None: ...

    async def find_active(
        self, *, kind: str, day: str, account_id: str | None
    ) -> AutoOpsJob | None: ...

    async def enqueue(
        self,
        *,
        kind: str,
        day: str,
        account_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> AutoOpsJob: ...

    async def list_for_account(
        self, *, account_id: str | None, kind: str | None = None, limit: int = 20
    ) -> list[AutoOpsJob]: ...


def normalize_day(raw: str | None) -> str:
    """Día del job en ``YYYY-MM-DD`` (hoy UTC si no se declara); valida el formato."""
    value = str(raw or "").strip()
    if not value:
        return datetime.now(UTC).date().isoformat()
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError as exc:
        raise ValueError("day inválida (YYYY-MM-DD)") from exc


class EnqueueAutoOpsJob:
    """Encola (o recupera) el job activo del mismo ``(kind, cuenta, día)``."""

    def __init__(self, repo: AutoOpsJobRepository) -> None:
        self._jobs = repo

    async def execute(
        self,
        *,
        kind: str,
        account_id: str | None = None,
        day: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AutoOpsJob:
        job_kind = str(kind or "").strip()
        if job_kind not in (
            JOB_KIND_ESTUDIO_DAILY,
            JOB_KIND_DIA_D_REPLAY,
            JOB_KIND_DIA_D_VALUE_REPLAY,
        ):
            raise ValueError(f"kind inválido: {job_kind or '(vacío)'}")
        job_day = normalize_day(day)
        job_payload = dict(payload or {})

        # Ambas tareas son operativas de una cuenta concreta: sin cuenta no hay job.
        if not account_id:
            raise ValueError("account_id requerido para encolar un job operativo")

        if job_kind == JOB_KIND_DIA_D_VALUE_REPLAY:
            # Fail-closed: la verificación por valor NO tiene sentido sin el valor.
            symbol = str(job_payload.get("symbol") or "").strip().upper()
            if not symbol:
                raise ValueError("symbol requerido para la verificación DÍA-D de un valor")
            job_payload["symbol"] = symbol
            job_payload.setdefault("instrumentId", symbol)
        else:
            # El símbolo es exclusivo del job por valor: no se arrastra a otros tipos.
            job_payload.pop("symbol", None)

        if job_kind in (JOB_KIND_DIA_D_REPLAY, JOB_KIND_DIA_D_VALUE_REPLAY):
            if job_day > datetime.now(UTC).date().isoformat():
                raise ValueError("El replay DÍA-D no admite una fecha futura")

        return await self._jobs.enqueue(
            kind=job_kind,
            day=job_day,
            account_id=account_id,
            payload=job_payload,
        )


class GetAutoOpsJob:
    """Lee un job del principal; el de otra cuenta es INDISTINGUIBLE de inexistente."""

    def __init__(self, repo: AutoOpsJobRepository) -> None:
        self._jobs = repo

    async def execute(
        self, job_id: str, *, account_id: str | None
    ) -> AutoOpsJob | None:
        if not account_id:
            return None
        job = await self._jobs.get(job_id)
        if job is None:
            return None
        if job.account_id is not None and job.account_id != account_id:
            return None
        return job


class ListAutoOpsJobs:
    """Últimos jobs visibles para la cuenta activa."""

    def __init__(self, repo: AutoOpsJobRepository) -> None:
        self._jobs = repo

    async def execute(
        self,
        *,
        account_id: str | None,
        kind: str | None = None,
        limit: int = 20,
    ) -> list[AutoOpsJob]:
        if not account_id:
            return []
        return await self._jobs.list_for_account(
            account_id=account_id, kind=kind, limit=limit
        )
