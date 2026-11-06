"""Worker — cola durable de trabajos operativos AUTO (``auto_ops_jobs``).

Un solo proceso (``scheduler_worker``) reclama y ejecuta los jobs encolados por el
scheduler diario o por la UI. El desenlace SIEMPRE queda durable: ``completed`` con
``result`` o ``failed`` con ``error`` (y el ``result`` parcial cuando lo hay).

* ``estudio_daily`` → ``RunEstudioDailyOps`` (universo ESTUDIO, opiniones ``eod_batch``,
  propuestas dry-run). El progreso se publica en sesiones cortas.
* ``dia_d_replay`` → subproceso aislado (``auto_ops_dia_d``).
* ``dia_d_value_replay`` → el MISMO subproceso con ``--watch <símbolo>`` y artefacto propio
  bajo ``…/values/<símbolo>/`` (nunca pisa el del día).

``UNKNOWN != 0``: un job sin resultado deja ``result`` vacío; no se rellena con ceros.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.background.auto_ops_dia_d import DiaDReplayFailed, run_dia_d_replay_job
from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_DIA_D_REPLAY,
    JOB_KIND_DIA_D_VALUE_REPLAY,
    JOB_KIND_ESTUDIO_DAILY,
    AutoOpsJob,
)
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
    SqlAlchemyAutoOpsJobRepository,
)

__all__ = [
    "AutoOpsJobFailed",
    "process_next_auto_ops_job",
    "run_auto_ops_job",
    "start_auto_ops_job_worker",
]

logger = logging.getLogger(__name__)


class AutoOpsJobFailed(RuntimeError):
    """Fallo declarado de un job; puede viajar con el ``result`` parcial."""

    def __init__(self, message: str, *, result: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.result = result or {}


# ── handlers ─────────────────────────────────────────────────────────────────


async def _run_estudio_daily(
    job: AutoOpsJob,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    from bolsa_api.api.dependencies import (
        get_daily_opinion_service,
        get_instrument_composite_use_case,
        get_instrument_fundamentals_use_case,
        get_position_state_repository,
        get_propose_estudio_auto_use_case,
    )
    from bolsa_api.background.estudio_watch import SessionScopedEstudioList
    from bolsa_application.estudio_daily_ops import (
        RunEstudioDailyOps,
        Top3SnapshotsSelector,
    )

    account_id = str(job.account_id or "")
    if not account_id:
        raise AutoOpsJobFailed("El job estudio_daily requiere cuenta")

    async def on_progress(progress: dict[str, Any]) -> None:
        # Sesión corta: el job puede tardar minutos y el progreso debe verse en vivo.
        async with session_factory() as session:
            await SqlAlchemyAutoOpsJobRepository(session).set_progress(
                job.id, progress
            )
            await session.commit()

    async with session_factory() as session:
        service = RunEstudioDailyOps(
            SessionScopedEstudioList(session_factory),
            get_daily_opinion_service(session),
            get_propose_estudio_auto_use_case(session),
            composite=get_instrument_composite_use_case(session),
            fundamentals=get_instrument_fundamentals_use_case(session),
            positions=get_position_state_repository(session),
            # Gap 1 — foto durable del selector cross-asset del día (misma fuente que la
            # evidencia de cadena). Read-only; un fallo se declara en el parte.
            selector=Top3SnapshotsSelector(session),
        )
        report = await service.execute(
            account_id=account_id,
            as_of=job.day,
            on_progress=on_progress,
        )
        result = report.to_dict()
        # Handoff durable ESTUDIO → AUTO (migración 058): las propuestas del parte se
        # persisten en la MISMA transacción que el parte, de modo que lo que el usuario ve
        # en pantalla es exactamente lo que el productor podrá adoptar. Idempotente: una
        # reejecución del día no duplica ni reescribe identidades ya publicadas.
        try:
            from bolsa_application.estudio_daily_proposals import (  # noqa: PLC0415
                PersistEstudioDailyProposals,
            )
            from bolsa_infrastructure.database.repositories.estudio_daily_proposal_repository import (  # noqa: PLC0415, E501
                SqlAlchemyEstudioDailyProposalRepository,
            )

            handoff = await PersistEstudioDailyProposals(
                # La transacción la cierra este handler: el store no commitea solo.
                SqlAlchemyEstudioDailyProposalRepository(session, autocommit=False)
            ).execute(account_id=account_id, report=result)
            result["handoff"] = handoff.to_dict()
        except Exception as exc:  # noqa: BLE001 — sin handoff no hay atribución exacta.
            await session.rollback()
            raise AutoOpsJobFailed(
                f"handoff de propuestas falló: {type(exc).__name__}: {exc}",
                result=result,
            ) from exc
        # Persistir opiniones/propuestas calculadas en esta sesión.
        await session.commit()


    reasons = [
        str(reason)
        for reason in (getattr(report, "degraded_reasons", None) or [])
        if str(reason).strip()
    ]
    status = str(getattr(report, "status", "") or "")
    if status == "partial":
        # R-3/H-145-3 — con mediciones ausentes el parte sigue siendo un RESULTADO válido:
        # se guarda completo con sus huecos declarados y NO se cierra como fallo. El worker
        # deja la traza de qué se degradó.
        logger.warning(
            "estudio_daily %s: parte PARTIAL (degradado: %s)",
            job.id,
            ", ".join(reasons) or "sin motivo declarado",
        )
        return result
    if status != "ok":
        notes = [str(note) for note in (getattr(report, "notes", None) or [])]
        detail = (reasons or notes or ["Universo ESTUDIO no disponible"])[0]
        raise AutoOpsJobFailed(str(detail), result=result)
    return result


async def run_auto_ops_job(
    job: AutoOpsJob,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    dia_d_timeout_seconds: float = 1800.0,
) -> dict[str, Any]:
    """Despacha el job por ``kind``. Un tipo desconocido falla cerrado."""
    if job.kind == JOB_KIND_ESTUDIO_DAILY:
        return await _run_estudio_daily(job, session_factory)
    if job.kind == JOB_KIND_DIA_D_REPLAY:
        return await run_dia_d_replay_job(
            job, session_factory, timeout_seconds=dia_d_timeout_seconds
        )
    if job.kind == JOB_KIND_DIA_D_VALUE_REPLAY:
        # Fail-closed: sin símbolo no hay verificación por valor (no se cae al día completo,
        # que escribiría OTRA evidencia y pisaría la del watch entero).
        symbol = str((job.payload or {}).get("symbol") or "").strip().upper()
        if not symbol:
            raise AutoOpsJobFailed(
                "El job dia_d_value_replay requiere 'symbol' en el payload"
            )
        return await run_dia_d_replay_job(
            job,
            session_factory,
            timeout_seconds=dia_d_timeout_seconds,
            symbol=symbol,
        )
    raise AutoOpsJobFailed(f"kind de job no soportado: {job.kind}")


# ── tick ─────────────────────────────────────────────────────────────────────


async def process_next_auto_ops_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stale_after_seconds: float | None = None,
    dia_d_timeout_seconds: float | None = None,
) -> bool:
    """Reclama y ejecuta UN job. Devuelve ``True`` si había trabajo."""
    settings = get_settings()
    stale = (
        float(stale_after_seconds)
        if stale_after_seconds is not None
        else float(settings.auto_ops_job_stale_seconds)
    )
    timeout = (
        float(dia_d_timeout_seconds)
        if dia_d_timeout_seconds is not None
        else float(settings.auto_ops_dia_d_timeout_seconds)
    )

    async with session_factory() as session:
        repo = SqlAlchemyAutoOpsJobRepository(session)
        attempts = max(1, int(getattr(settings, "auto_ops_job_max_attempts", 5)))
        # H-145-5 — antes de reclamar, cerrar los ABANDONADOS que agotaron el tope: si no,
        # quedarían en la cola sin poder reclamarse y sin desenlace durable.
        await repo.fail_exhausted(
            max_attempts=attempts,
            stale_after_seconds=int(max(60.0, stale)),
        )
        job = await repo.claim_next(
            stale_after_seconds=int(max(60.0, stale)),
            max_attempts=attempts,
        )
        await session.commit()
    if job is None:
        return False

    logger.info(
        "auto_ops_job %s (%s · día %s · cuenta %s) reclamado (intento %s)",
        job.id,
        job.kind,
        job.day,
        job.account_id,
        job.attempt,
    )
    try:
        result = await run_auto_ops_job(
            job, session_factory, dia_d_timeout_seconds=timeout
        )
    except asyncio.CancelledError:
        # Apagado del proceso: el job queda ``running`` y se recupera por latido obsoleto.
        raise
    except (AutoOpsJobFailed, DiaDReplayFailed) as exc:
        async with session_factory() as session:
            await SqlAlchemyAutoOpsJobRepository(session).fail(
                job.id, str(exc), result=getattr(exc, "result", None) or None
            )
            await session.commit()
        logger.warning("auto_ops_job %s falló: %s", job.id, exc)
        return True
    except Exception as exc:  # noqa: BLE001 — un job no puede tumbar el worker
        logger.exception("auto_ops_job %s falló inesperadamente", job.id)
        async with session_factory() as session:
            await SqlAlchemyAutoOpsJobRepository(session).fail(
                job.id, f"{type(exc).__name__}: {exc}"
            )
            await session.commit()
        return True

    async with session_factory() as session:
        await SqlAlchemyAutoOpsJobRepository(session).complete(job.id, result)
        await session.commit()
    logger.info("auto_ops_job %s completado", job.id)
    return True


async def auto_ops_job_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(1.0, float(settings.auto_ops_job_interval_seconds))
    logger.info(
        "Worker AUTO_OPS_JOB iniciado — tick %.1fs, heartbeat obsoleto %.0fs",
        interval,
        float(settings.auto_ops_job_stale_seconds),
    )
    while True:
        try:
            worked = await process_next_auto_ops_job(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — el bucle nunca muere por un tick
            logger.exception("Worker AUTO_OPS_JOB: tick fallido")
            worked = False
        # Con trabajo pendiente se reintenta en seguida; en vacío se duerme el intervalo.
        await asyncio.sleep(0.25 if worked else interval)


def start_auto_ops_job_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.auto_ops_job_worker_enabled:
        logger.info(
            "Worker AUTO_OPS_JOB desactivado (AUTO_OPS_JOB_WORKER_ENABLED=false)"
        )
        return None
    return asyncio.create_task(auto_ops_job_worker_loop(session_factory))
