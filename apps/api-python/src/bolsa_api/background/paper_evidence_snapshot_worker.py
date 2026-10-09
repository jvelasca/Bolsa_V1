"""Worker — captura periódica de la foto durable de evidencia PAPER (protocolo longitudinal).

Frente B (`ADR-046`): la serie longitudinal de la evidencia PAPER se materializa como filas
append-only del spine (``decision_journal_entries``, ``event_type = auto_paper_evidence_snapshot``),
idempotentes por ``(cuenta, día)``. El endpoint ``POST /api/auto/paper-evidence/snapshot`` es el
driver manual; este worker añade el **driver periódico** que la evidencia declaraba pendiente, sin
convertir la captura en parte del producto certificado (sigue tras un flag).

Reglas duras:

* **Off-by-default** (``PAPER_EVIDENCE_SNAPSHOT_ENABLED=false``): con el flag apagado no se construye
  tarea ⇒ ``Δ motor = 0``.
* **Read-only respecto al dinero.** Compone la evidencia con ``read_paper_evidence`` (solo ``SELECT``)
  y **solo** escribe la traza del protocolo (el snapshot). Nunca toca ``sim_auto_positions``,
  reservas, órdenes ni la decisión.
* **Fail-closed por cuenta.** Enumera las cuentas del owner y captura una foto por cuenta; una cuenta
  sin identidad no se finge. Un error de una cuenta no tumba el tick de las demás.
* **Sin promoción.** El ``verdict`` del snapshot es siempre el literal ``NO_CONFIRMED`` (lo impone
  ``build_paper_evidence_snapshot_entry``); la promoción a ``CONFIRMED`` es humana.

@see packages/py/application/src/bolsa_application/paper_evidence_protocol.py
@see docs/adr/046-protocolo-longitudinal-paper.md
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.paper_evidence_protocol import build_paper_evidence_snapshot_entry
from bolsa_application.paper_evidence_reader import read_paper_evidence
from bolsa_infrastructure.config import get_settings

logger = logging.getLogger(__name__)

_NO_ACCOUNT = "no_account_scope"


def _account_id_of(account: Any) -> str | None:
    value = getattr(account, "id", None) or getattr(account, "account_id", None)
    text = str(value).strip() if value is not None else ""
    return text or None


async def _record_snapshots_once(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """Captura UNA foto por cuenta en una transacción por cuenta (aislada)."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    recorded = 0
    skipped = 0
    async with session_factory() as session:
        accounts = await SqlAlchemyAccountRepository(session).list_accounts()

    for account in accounts:
        account_id = _account_id_of(account)
        if account_id is None:
            skipped += 1
            continue
        async with session_factory() as session:
            try:
                payload = await read_paper_evidence(session, account_id)
                entry = build_paper_evidence_snapshot_entry(
                    account_id=account_id, evidence=payload
                )
                if entry is None:
                    skipped += 1
                    await session.rollback()
                    continue
                await SqlAlchemyJournalRepository(session).append(entry)
                await session.commit()
                recorded += 1
            except Exception:
                await session.rollback()
                logger.exception(
                    "Worker PAPER snapshot: error capturando la foto de la cuenta %s", account_id
                )
    return {"recorded": recorded, "skipped": skipped, "accounts": len(accounts)}


async def paper_evidence_snapshot_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(300, int(settings.paper_evidence_snapshot_interval_seconds))
    logger.info("Worker PAPER snapshot iniciado — intervalo %ds", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            result = await _record_snapshots_once(session_factory)
            if result["recorded"]:
                logger.info(
                    "PAPER snapshot: recorded=%s skipped=%s accounts=%s",
                    result["recorded"],
                    result["skipped"],
                    result["accounts"],
                )
        except Exception:
            logger.exception("Error en worker PAPER snapshot")


def start_paper_evidence_snapshot_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.paper_evidence_snapshot_enabled:
        logger.info(
            "Worker PAPER snapshot desactivado (PAPER_EVIDENCE_SNAPSHOT_ENABLED=false)"
        )
        return None
    return asyncio.create_task(paper_evidence_snapshot_worker_loop(session_factory))
