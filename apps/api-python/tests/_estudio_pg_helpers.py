"""Arnés compartido (PostgreSQL real) — verificación ESTUDIO ↔ AUTO (V2.88.123).

Factoriza lo que comparten la verificación ``S1`` (cobertura del universo ESTUDIO,
``test_auto_estudio_universe_coverage_pg.py``) y la ``S2`` (watch diario desde ESTUDIO,
``test_auto_daily_watch_from_estudio_pg.py``):

* siembra de un instrumento con una serie OHLCV con tendencia (el campeón del LAB pasa
  los gates y el ciclo deja evaluación persistida);
* edición **NO destructiva** de la lista ESTUDIO (añadir/retirar preservando el resto);
* limpieza de las filas del instrumento.

NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"


def require_or_skip(exc: Exception, *, required_env: str, what: str) -> None:
    """Skip honesto sin PG; FALLO duro si el job PG exige la certificación (gate)."""
    if os.environ.get(required_env) == "1":
        raise AssertionError(f"PostgreSQL requerido para {what} pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic ({what}) no disponible: {exc}")


@contextlib.asynccontextmanager
async def pg_session_factory() -> AsyncIterator[Any]:
    """Fábrica de sesiones sobre PostgreSQL real (migrado); cierra el engine al salir.

    ``get_settings``/``ensure_migrated`` pueden lanzar si PG/Alembic no están: el
    llamante decide el fail-if-skipped con ``require_or_skip``.
    """
    factory, engine = await make_pg_session_factory()
    try:
        yield factory
    finally:
        await engine.dispose()


async def make_pg_session_factory() -> tuple[Any, Any]:
    """Abre PostgreSQL real (migrado) y devuelve ``(session_factory, engine)``.

    Lanza si PG/Alembic no están disponibles; el llamante decide el fail-if-skipped.
    """
    from dotenv import load_dotenv

    if _DOTENV.exists():
        load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    return create_session_factory(engine), engine


async def seed_instrument_with_trend(
    factory: Any,
    *,
    instrument_id: str,
    symbol: str,
) -> None:
    """Siembra un instrumento con una serie OHLCV con tendencia + oscilación.

    El mismo patrón que ``test_strategy_lifecycle_pg.py`` (drift dominante sobre una
    sinusoide): el campeón del LAB pasa los 4 gates ``lab_validated`` (CPCV/WF) y el
    ciclo deja evaluación persistida. Sin serie, el LAB devuelve «sin evidencia» y el
    valor NO deja el hecho durable que la verificación exige.
    """
    from bolsa_infrastructure.database.models.tables import InstrumentRow, OhlcvBarRow

    async with factory() as session:
        if await session.get(InstrumentRow, instrument_id) is not None:
            return
        now = datetime.now(UTC)
        session.add(
            InstrumentRow(
                id=instrument_id,
                symbol=symbol,
                yahoo_symbol=f"{symbol}.MC",
                name=f"ESTCO Test {symbol}",
                exchange="MCE",
                country="ES",
                currency="EUR",
                type="stock",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        base = Decimal("10.00")
        for day in range(420):
            wave = Decimal(str(round(2.0 * math.sin(2 * math.pi * day / 60.0), 4)))
            drift = Decimal(day) * Decimal("0.08")
            price = base + drift + wave
            session.add(
                OhlcvBarRow(
                    id=uuid.uuid4().hex,
                    instrument_id=instrument_id,
                    timeframe="1d",
                    timestamp=now - timedelta(days=419 - day),
                    open=price,
                    high=price + Decimal("0.10"),
                    low=price - Decimal("0.10"),
                    close=price,
                    volume=1000,
                    adj_close=price,
                    source="yahoo",
                    created_at=now,
                )
            )
        await session.commit()


async def set_estudio(factory: Any, instrument_ids: list[str]) -> list[str]:
    """Fija la lista ESTUDIO a ``instrument_ids``; devuelve los originales (para restaurar).

    No destructivo: el cleanup restaura la lista original. Lanza si la lista no admite
    edición (catálogo), que sería un cambio de contrato ajeno a este sello.
    """
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    async with factory() as session:
        repo = SqlAlchemyListRepository(session)
        existing = await repo.ensure_estudio_list()
        originals = list(existing.instrument_ids)
        await repo.update(
            SqlAlchemyListRepository.ESTUDIO_LIST_ID,
            instrument_ids=list(dict.fromkeys(instrument_ids)),
        )
        await session.commit()
        return originals


async def add_to_estudio(factory: Any, instrument_ids: list[str]) -> list[str]:
    """AÑADE valores a ESTUDIO preservando los existentes; devuelve los originales."""
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    async with factory() as session:
        repo = SqlAlchemyListRepository(session)
        existing = await repo.ensure_estudio_list()
        originals = list(existing.instrument_ids)
        merged = list(dict.fromkeys([*originals, *instrument_ids]))
        if merged != originals:
            await repo.update(
                SqlAlchemyListRepository.ESTUDIO_LIST_ID,
                instrument_ids=merged,
            )
        await session.commit()
        return originals


async def restore_estudio(factory: Any, originals: list[str]) -> None:
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )

    async with factory() as session:
        repo = SqlAlchemyListRepository(session)
        await repo.ensure_estudio_list()
        await repo.update(
            SqlAlchemyListRepository.ESTUDIO_LIST_ID,
            instrument_ids=originals,
        )
        await session.commit()


async def cleanup_instrument(factory: Any, instrument_id: str) -> None:
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import (
        InstrumentRow,
        OhlcvBarRow,
        StrategyCandidateRow,
        StrategyEvaluationRow,
    )

    async with factory() as session:
        await session.execute(
            delete(StrategyEvaluationRow).where(
                StrategyEvaluationRow.instrument_id == instrument_id
            )
        )
        await session.execute(
            delete(StrategyCandidateRow).where(StrategyCandidateRow.instrument_id == instrument_id)
        )
        await session.execute(delete(OhlcvBarRow).where(OhlcvBarRow.instrument_id == instrument_id))
        await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
        await session.commit()
