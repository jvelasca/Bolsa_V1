"""AUTO 2.0 · V2.40.1 — contexto de cartera del catálogo sobre PostgreSQL real.

Certifica la lectura que alimenta los gates fail-closed del tick AUTO: ``sector``,
ADV notional y **frescura** de los fundamentales de cada instrumento, en UNA query
(``list_trade_context_by_ids``). Es la pieza que convierte "no tengo dato" en un VETO
en vez de en una entrada, así que su contrato tiene que ser explícito:

- el mapa responde por ``id`` **y** por ``symbol`` (el worker del AUTO se keya por símbolo);
- un instrumento sin fila NO aparece (el motor lo trata como desconocido);
- un instrumento con fila pero sin ``sector``/``advUsd``/``fetchedAt`` devuelve ``None``
  en ese campo, **nunca un valor por defecto** (la decisión de asumir o vetar es del motor).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real/credenciales hace
``pytest.skip``; con ``INSTRUMENT_TRADE_CONTEXT_PG_REQUIRED=1`` un skip silencioso es un
FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "INSTRUMENT_TRADE_CONTEXT_PG_REQUIRED"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el contexto de cartera pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (contexto de cartera) no disponible: {exc}")


@pytest_asyncio.fixture
async def trade_context_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_instrument(
    session: AsyncSession,
    *,
    symbol: str,
    sector: str | None,
    adv_usd: float | None,
    fetched_at: datetime | None,
) -> str:
    """Siembra un instrumento del catálogo con (o sin) bloque ``fundamentals``."""
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    now = datetime.now(UTC)
    instrument_id = f"inst-tc-{uuid.uuid4().hex[:10]}"
    fundamentals: dict[str, object] = {}
    if adv_usd is not None:
        fundamentals["advUsd"] = adv_usd
    if fetched_at is not None:
        fundamentals["fetchedAt"] = fetched_at.isoformat()
    profile_snapshot = {"fundamentals": fundamentals} if fundamentals else None
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=symbol,
            yahoo_symbol=f"{symbol}.{uuid.uuid4().hex[:6]}",
            isin=None,
            name="AUTO-TradeContext",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            sector=sector,
            profile_snapshot=profile_snapshot,
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    return instrument_id


@pytest.mark.asyncio
async def test_list_trade_context_by_ids_reports_sector_adv_and_freshness(
    trade_context_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import InstrumentRow
    from bolsa_infrastructure.database.repositories.instrument_repository import (
        SqlAlchemyInstrumentRepository,
    )

    suffix = uuid.uuid4().hex[:6].upper()
    fresh_symbol = f"TCF{suffix}"
    opaque_symbol = f"TCO{suffix}"
    fresh_at = datetime.now(UTC) - timedelta(days=1)
    stale_at = datetime.now(UTC) - timedelta(days=400)
    seeded: list[str] = []
    unknown_id = f"inst-tc-missing-{uuid.uuid4().hex[:8]}"
    try:
        async with trade_context_pg_factory() as session:
            repository = SqlAlchemyInstrumentRepository(session)
            fresh_id = await _seed_instrument(
                session,
                symbol=fresh_symbol,
                sector="Technology",
                adv_usd=42_000_000.0,
                fetched_at=fresh_at,
            )
            stale_id = await _seed_instrument(
                session,
                symbol=f"TCS{suffix}",
                sector="Utilities",
                adv_usd=1_500_000.0,
                fetched_at=stale_at,
            )
            opaque_id = await _seed_instrument(
                session,
                symbol=opaque_symbol,
                sector=None,
                adv_usd=None,
                fetched_at=None,
            )
            seeded = [fresh_id, stale_id, opaque_id]

            contexts = await repository.list_trade_context_by_ids(
                [fresh_id, fresh_symbol, stale_id, opaque_id, unknown_id, "  "]
            )

            # El instrumento fresco responde por id Y por símbolo (misma fila).
            for key in (fresh_id, fresh_symbol):
                context = contexts[key]
                assert context.sector == "Technology"
                assert context.adv_usd == 42_000_000.0
                assert context.observed_at is not None
                assert datetime.fromisoformat(context.observed_at) == fresh_at
            assert contexts[fresh_id] == contexts[fresh_symbol]

            # La frescura es un DATO, no un juicio: el repositorio reporta el instante
            # observado y el motor decide (``sector_stale``) contra sus días máximos.
            stale = contexts[stale_id]
            assert stale.observed_at is not None
            assert datetime.fromisoformat(stale.observed_at) == stale_at

            # Fila presente pero dato ausente ⇒ ``None`` explícito, nunca un default.
            opaque = contexts[opaque_id]
            assert opaque.sector is None
            assert opaque.adv_usd is None
            assert opaque.observed_at is None

            # Sin fila no hay contexto (el motor lo veta como desconocido).
            assert unknown_id not in contexts
            assert "  " not in contexts
    finally:
        if seeded:
            async with trade_context_pg_factory() as session:
                await session.execute(
                    delete(InstrumentRow).where(InstrumentRow.id.in_(seeded))
                )
                await session.commit()
