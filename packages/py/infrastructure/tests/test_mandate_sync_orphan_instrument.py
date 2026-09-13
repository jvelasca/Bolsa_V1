"""Regresión — ``sync_account`` no debe reventar con instrumentos huérfanos.

Contexto (bug observado en el arranque real de la API):

El cliente construye el payload del mandato desde su cache (``localStorage``) y puede
referenciar instrumentos de un catálogo ANTERIOR ya inexistentes en ``instruments``. La
validación previa solo miraba ``if not instrument_id`` (string vacío), así que un id NO
vacío pero ausente pasaba el filtro, llegaba a la FK
``mandate_tenures_instrument_id_fkey`` y abortaba el ``PUT /mandates`` con 500
(``psycopg.errors.ForeignKeyViolation``).

El contrato esperado es **fail-soft**: descartar las filas huérfanas y conservar las
válidas (mismo espíritu tolerante que la comprobación original). Este test fija ese
contrato para tenures Y para links (cuya FK apunta a ``mandate_tenures``).

Requiere PostgreSQL (mismas convenciones que el resto de tests de infraestructura).
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.repositories.mandate_repository import (
    SqlAlchemyMandateRepository,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ACCOUNT_ID = "default-account-seed"
ORPHAN_INSTRUMENT_ID = "cmqsm5fye0007xnz44o28ik8o"  # id real del 500, ausente en BD


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


async def _first_real_instrument_id(session: AsyncSession) -> str:
    row = (
        await session.execute(text("SELECT id FROM instruments ORDER BY id LIMIT 1"))
    ).first()
    assert row is not None, "premisa: el catálogo debe tener instrumentos sembrados"
    return str(row[0])


@pytest.mark.asyncio
async def test_orphan_instrument_is_dropped_instead_of_raising(
    db_session: AsyncSession,
) -> None:
    """Un tenures huérfano NO debe lanzar; se descarta y sobrevive el válido.

    Antes del fix esto lanzaba ``IntegrityError``/``ForeignKeyViolation`` (500 en la API).
    """
    repo = SqlAlchemyMandateRepository(db_session)
    real_instrument = await _first_real_instrument_id(db_session)

    orphan_tenure_id = "regression-orphan-tenure"
    valid_tenure_id = "regression-valid-tenure"
    await _delete_tenures(db_session, [orphan_tenure_id, valid_tenure_id])

    tenures = [
        {
            "id": orphan_tenure_id,
            "instrumentId": ORPHAN_INSTRUMENT_ID,
            "timeframe": "1d",
            "effectiveFrom": "2026-08-21T10:50:13+00:00",
            "effectiveTo": None,
            "actor": "user",
            "reason": "adopt",
        },
        {
            "id": valid_tenure_id,
            "instrumentId": real_instrument,
            "timeframe": "1d",
            "effectiveFrom": "2026-08-21T10:50:13+00:00",
            "effectiveTo": None,
            "actor": "user",
            "reason": "adopt",
        },
    ]

    # Antes del fix: ForeignKeyViolation. Después: descarta el huérfano y persiste el válido.
    out_tenures, _ = await repo.sync_account(ACCOUNT_ID, tenures, [])

    ids = {t.id for t in out_tenures}
    assert valid_tenure_id in ids, "el tenure con instrumento real debe persistir"
    assert orphan_tenure_id not in ids, "el tenure huérfano debe descartarse"

    persisted = (
        await db_session.execute(
            text("SELECT count(*) FROM mandate_tenures WHERE id = :id"),
            {"id": orphan_tenure_id},
        )
    ).scalar_one()
    assert persisted == 0, "el huérfano no debe quedar en BD"

    await _delete_tenures(db_session, [valid_tenure_id])
    await db_session.commit()


@pytest.mark.asyncio
async def test_link_to_dropped_tenure_is_dropped_too(
    db_session: AsyncSession,
) -> None:
    """Un link que apunta a un tenure huérfano también se descarta (su FK lo haría fallar).

    ``mandate_trade_links.mandate_tenure_id`` referencia ``mandate_tenures``: si el tenure
    se descarta por instrumento ausente, sus links quedarían colgando y reventarían el PUT.
    """
    repo = SqlAlchemyMandateRepository(db_session)
    real_instrument = await _first_real_instrument_id(db_session)

    orphan_tenure_id = "regression-orphan-tenure-link"
    await _delete_tenures(db_session, [orphan_tenure_id])
    await db_session.execute(
        text("DELETE FROM mandate_trade_links WHERE transaction_id = :tid"),
        {"tid": "regression-link-orphan"},
    )
    await db_session.commit()

    tenures = [
        {
            "id": orphan_tenure_id,
            "instrumentId": ORPHAN_INSTRUMENT_ID,
            "timeframe": "1d",
            "effectiveFrom": "2026-08-21T10:50:13+00:00",
            "effectiveTo": None,
            "actor": "user",
            "reason": "adopt",
        }
    ]
    links = [
        {
            "transactionId": "regression-link-orphan",
            "mandateTenureId": orphan_tenure_id,
            "instrumentId": real_instrument,
            "linkedAt": "2026-08-21T10:50:13+00:00",
        }
    ]

    # No debe lanzar aunque el tenure referenciado no sobreviva al filtro.
    _, out_links = await repo.sync_account(ACCOUNT_ID, tenures, links)

    assert all(l.transaction_id != "regression-link-orphan" for l in out_links)


async def _delete_tenures(session: AsyncSession, ids: list[str]) -> None:
    for tenure_id in ids:
        await session.execute(
            text("DELETE FROM mandate_trade_links WHERE mandate_tenure_id = :id"),
            {"id": tenure_id},
        )
        await session.execute(
            text("DELETE FROM mandate_tenures WHERE id = :id"), {"id": tenure_id}
        )
    await session.commit()
