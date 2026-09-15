"""V2.40.2 — claves naturales únicas (reconciliación Prisma→Alembic) sobre PG real.

Incidente que lo motiva (2026-09-14): ``GET /instrument-daily-opinions`` quedó en
``MultipleResultsFound`` **permanente**. La migración Prisma declaraba
``UNIQUE (instrument_id, timeframe)`` en ``instrument_strategy_tops``, pero el baseline
Alembic no la creó (el modelo no la declaraba) y el ``upsert`` era un check-then-insert:
dos escritores concurrentes insertaron ambos y ``get()`` (``scalar_one_or_none``) dejó de
poder leer la fila para siempre. La consola del dev server lo mostró en vivo.

Este fichero certifica las DOS mitades del arreglo, porque ninguna basta sola:

1. **Backstop de BD** — las 8 claves naturales que faltaban existen como índice único
   (migración 041), y siguen existiendo: un test de deriva lo impide re-driftar.
2. **Escritura atómica** — los tres ``upsert`` de esas claves (tops, narrativas,
   opiniones) resuelven el conflicto en PostgreSQL, así que dos escritores concurrentes
   producen UNA fila y no un ``IntegrityError`` ni un duplicado.

También se verifica el dedupe de la migración con duplicados preexistentes: se baja a
040, se insertan duplicados a mano, y al volver a head debe quedar la fila más reciente.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``UNIQUE_NATURAL_KEYS_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el
bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "UNIQUE_NATURAL_KEYS_PG_REQUIRED"
_PREVIOUS_REVISION = "040_auto_v2_durable_state"

# (tabla, nombre canónico del índice único, columnas de la clave natural).
# Los nombres son los que declaró Prisma: si la BD viniera de Prisma, el guard de la
# migración 041 los detecta como existentes y no recrea nada.
_NATURAL_KEYS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("instruments", "instruments_symbol_exchange_key", ("symbol", "exchange")),
    (
        "positions",
        "positions_portfolio_id_instrument_id_key",
        ("portfolio_id", "instrument_id"),
    ),
    (
        "data_snapshots",
        "data_snapshots_instrument_timeframe_version_idx",
        ("instrument_id", "timeframe", "data_version"),
    ),
    (
        "position_policies",
        "position_policies_account_instrument_idx",
        ("account_id", "instrument_id"),
    ),
    (
        "instrument_daily_opinions",
        "instrument_daily_opinions_instrument_id_asof_source_key",
        ("instrument_id", "as_of_bar_date", "source"),
    ),
    (
        "instrument_narratives",
        "instrument_narratives_instrument_id_scope_key",
        ("instrument_id", "scope"),
    ),
    (
        "instrument_strategy_tops",
        "instrument_strategy_tops_instrument_timeframe_uq",
        ("instrument_id", "timeframe"),
    ),
    (
        "instrument_list_items",
        "instrument_list_items_list_id_instrument_id_key",
        ("list_id", "instrument_id"),
    ),
)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para las claves naturales únicas pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (claves naturales) no disponible: {exc}")


@pytest_asyncio.fixture
async def natural_keys_pg_factory() -> async_sessionmaker[AsyncSession]:
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


async def _seed_instrument(session: AsyncSession, symbol: str) -> str:
    """Siembra un instrumento del catálogo (FK de tops/narrativas/opiniones)."""
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    now = datetime.now(UTC)
    instrument_id = f"inst-nk-{uuid.uuid4().hex[:12]}"
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=symbol,
            yahoo_symbol=f"{symbol}.{uuid.uuid4().hex[:6]}",
            isin=None,
            name="NaturalKeys test",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            sector=None,
            profile_snapshot=None,
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    return instrument_id


async def _drop_instruments(factory: async_sessionmaker[AsyncSession], ids: list[str]) -> None:
    """Borra los instrumentos sembrados; sus hijos caen por ON DELETE CASCADE."""
    if not ids:
        return
    from sqlalchemy import delete

    from bolsa_infrastructure.database.models.tables import InstrumentRow

    async with factory() as session:
        await session.execute(delete(InstrumentRow).where(InstrumentRow.id.in_(ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_the_eight_natural_keys_have_a_unique_index(
    natural_keys_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Guardia anti-deriva: las 8 claves naturales existen como índice único.

    Sin este test la reconciliación vuelve a perderse en la siguiente tabla que alguien
    añada "solo en Prisma": el baseline Alembic no copia índices de los modelos.
    """
    async with natural_keys_pg_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT tablename, indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname = 'public'"
                )
            )
        ).all()
    definitions = {(str(t), str(n)): str(d) for t, n, d in rows}

    missing: list[str] = []
    for table, index_name, columns in _NATURAL_KEYS:
        definition = definitions.get((table, index_name))
        if definition is None:
            missing.append(f"{table}: falta el índice {index_name}")
            continue
        if "UNIQUE INDEX" not in definition:
            missing.append(f"{table}: {index_name} no es UNIQUE")
            continue
        for column in columns:
            if not re.search(rf"\b{re.escape(column)}\b", definition):
                missing.append(f"{table}: {index_name} no cubre {column}")

    assert not missing, "claves naturales sin backstop único en la BD: " + "; ".join(missing)


@pytest.mark.asyncio
async def test_concurrent_top_upsert_yields_a_single_row(
    natural_keys_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regresión del incidente: dos upserts concurrentes = UNA fila, sin excepción.

    Antes: ``get()`` + INSERT en ambos ⇒ duplicado ⇒ ``MultipleResultsFound`` para
    siempre. Ahora el conflicto lo resuelve PostgreSQL contra el índice único.
    """
    from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
        SqlAlchemyInstrumentStrategyTopRepository,
    )

    symbol = f"NKU{uuid.uuid4().hex[:6].upper()}"
    seeded: list[str] = []
    try:
        async with natural_keys_pg_factory() as session:
            instrument_id = await _seed_instrument(session, symbol)
        seeded.append(instrument_id)

        async def _upsert(slots: list[dict[str, object]]) -> None:
            async with natural_keys_pg_factory() as session:
                repository = SqlAlchemyInstrumentStrategyTopRepository(session)
                await repository.upsert(
                    instrument_id=instrument_id,
                    timeframe="1d",
                    slots=slots,
                    symbol=symbol,
                )

        await asyncio.gather(
            _upsert([{"strategy": "A", "stars": 3}]),
            _upsert([{"strategy": "B", "stars": 2}]),
        )

        async with natural_keys_pg_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, version FROM instrument_strategy_tops "
                        "WHERE instrument_id = :i AND timeframe = '1d'"
                    ),
                    {"i": instrument_id},
                )
            ).all()
        assert len(rows) == 1, f"el upsert atómico debe dejar UNA fila, quedaron {rows}"
        assert int(rows[0][1]) in (1, 2)
    finally:
        await _drop_instruments(natural_keys_pg_factory, seeded)


@pytest.mark.asyncio
async def test_top_upsert_keeps_symbol_and_bumps_version(
    natural_keys_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Semántica conservada: sin ``symbol`` explícito se mantiene el guardado."""
    from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
        SqlAlchemyInstrumentStrategyTopRepository,
    )

    symbol = f"NKS{uuid.uuid4().hex[:6].upper()}"
    seeded: list[str] = []
    try:
        async with natural_keys_pg_factory() as session:
            instrument_id = await _seed_instrument(session, symbol)
            repository = SqlAlchemyInstrumentStrategyTopRepository(session)
            first = await repository.upsert(
                instrument_id=instrument_id,
                timeframe="1d",
                slots=[{"strategy": "A"}],
                symbol=symbol,
                period_label="P1",
            )
            second = await repository.upsert(
                instrument_id=instrument_id,
                timeframe="1d",
                slots=[{"strategy": "A"}, {"strategy": "B"}],
                symbol=None,
                period_label="P2",
            )
        seeded.append(instrument_id)

        assert first.id == second.id, "el upsert no debe cambiar el id de la fila"
        assert first.version == 1
        assert second.version == 2
        assert second.symbol == symbol, "el símbolo previo se conserva si no se aporta uno"
        assert second.period_label == "P2"
        assert len(second.slots) == 2
    finally:
        await _drop_instruments(natural_keys_pg_factory, seeded)


@pytest.mark.asyncio
async def test_concurrent_narrative_upsert_yields_a_single_row(
    natural_keys_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Mismo patrón tóxico en narrativas: check-then-insert ⇒ ahora upsert atómico."""
    from bolsa_infrastructure.database.repositories.instrument_narrative_repository import (
        SqlAlchemyInstrumentNarrativeRepository,
    )

    symbol = f"NKN{uuid.uuid4().hex[:6].upper()}"
    seeded: list[str] = []
    try:
        async with natural_keys_pg_factory() as session:
            instrument_id = await _seed_instrument(session, symbol)
        seeded.append(instrument_id)

        async def _upsert(body: str) -> None:
            async with natural_keys_pg_factory() as session:
                repository = SqlAlchemyInstrumentNarrativeRepository(session)
                await repository.upsert(
                    instrument_id=instrument_id,
                    scope="estudio",
                    body=body,
                )

        await asyncio.gather(_upsert("cuerpo A"), _upsert("cuerpo B"))

        async with natural_keys_pg_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, version FROM instrument_narratives "
                        "WHERE instrument_id = :i AND scope = 'estudio'"
                    ),
                    {"i": instrument_id},
                )
            ).all()
        assert len(rows) == 1, f"la narrativa no debe duplicarse, quedaron {rows}"
        assert int(rows[0][1]) in (1, 2)
    finally:
        await _drop_instruments(natural_keys_pg_factory, seeded)


@pytest.mark.asyncio
async def test_concurrent_daily_opinion_upsert_yields_a_single_row(
    natural_keys_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El dictamen diario del Estudio es el que rompía la ruta: una fila por día."""
    from bolsa_infrastructure.database.repositories.instrument_daily_opinion_repository import (
        SqlAlchemyInstrumentDailyOpinionRepository,
    )

    symbol = f"NKO{uuid.uuid4().hex[:6].upper()}"
    seeded: list[str] = []
    try:
        async with natural_keys_pg_factory() as session:
            instrument_id = await _seed_instrument(session, symbol)
        seeded.append(instrument_id)
        as_of = date(2026, 9, 14)

        async def _upsert(stars: int) -> None:
            async with natural_keys_pg_factory() as session:
                repository = SqlAlchemyInstrumentDailyOpinionRepository(session)
                await repository.upsert(
                    {
                        "instrument_id": instrument_id,
                        "as_of_bar_date": as_of,
                        "stance": "neutral",
                        "dictamen_stars": stars,
                        "source": "on_demand",
                    }
                )

        await asyncio.gather(_upsert(3), _upsert(4))

        async with natural_keys_pg_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, dictamen_stars FROM instrument_daily_opinions "
                        "WHERE instrument_id = :i"
                    ),
                    {"i": instrument_id},
                )
            ).all()
        assert len(rows) == 1, f"el dictamen diario no debe duplicarse, quedaron {rows}"
        assert int(rows[0][1]) in (3, 4)
    finally:
        await _drop_instruments(natural_keys_pg_factory, seeded)


@pytest.mark.asyncio
async def test_the_unique_index_rejects_a_raw_duplicate_row(
    natural_keys_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El backstop es real: un INSERT duplicado crudo falla con IntegrityError.

    Certifica la propiedad fail-closed sin pasar por el repositorio: si la clave natural
    no fuera única en la BD, un escritor que se salte el upsert volvería a duplicar la
    fila y a envenenar la lectura. Aquí el duplicado tiene que ser imposible.
    """
    from sqlalchemy.exc import IntegrityError

    symbol = f"NKD{uuid.uuid4().hex[:6].upper()}"
    seeded: list[str] = []
    try:
        async with natural_keys_pg_factory() as session:
            instrument_id = await _seed_instrument(session, symbol)
        seeded.append(instrument_id)

        insert_sql = text(
            "INSERT INTO instrument_strategy_tops (id, instrument_id, symbol, timeframe, status,"
            " version, evidence_level, slots, created_at, updated_at) VALUES"
            " (:id, :iid, :symbol, '1d', 'semifinal', 1, 'in_sample_only', CAST('[]' AS jsonb),"
            " :now, :now)"
        )
        now = datetime.now(UTC)
        async with natural_keys_pg_factory() as session:
            await session.execute(
                insert_sql,
                {"id": "ist_nk_first", "iid": instrument_id, "symbol": symbol, "now": now},
            )
            await session.commit()

        with pytest.raises(IntegrityError):
            async with natural_keys_pg_factory() as session:
                await session.execute(
                    insert_sql,
                    {"id": "ist_nk_second", "iid": instrument_id, "symbol": symbol, "now": now},
                )
                await session.commit()
    finally:
        await _drop_instruments(natural_keys_pg_factory, seeded)


@pytest.mark.asyncio
async def test_migration_041_dedupes_existing_duplicates_and_recreates_indexes() -> None:
    """Roundtrip 041 con duplicados preexistentes: dedupe conservador + índice único.

    Se baja a 040, se deja la tabla SIN backstop (el escenario real del incidente: la BD en
    la que la 041 todavía no había corrido), se insertan dos filas de la MISMA clave natural
    con ``updated_at`` distinto, y al volver a head debe quedar solo la más reciente y el
    índice debe existir. Es la reproducción exacta de las 24 filas del 2026-09-14.

    El test es consciente del **linaje** del nombre (ver docstring de la migración): en una
    BD nueva el baseline ``003`` lo crea como *constraint* al construir las tablas desde el
    modelo, y en una BD antigua lo crea la 041 como *índice plano*. El ``downgrade`` de la
    041 solo retira los planos —los suyos—, así que aquí se comprueba el contrato para cada
    linaje y se retira el backstop a mano cuando el linaje lo deja en pie.
    """
    pytest.importorskip("alembic")
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)

    from alembic import command
    from sqlalchemy import create_engine

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import _alembic_config, alembic_head

    get_settings.cache_clear()
    settings = get_settings()
    url = settings.database_url
    assert url is not None
    url = url.replace("postgresql://", "postgresql+psycopg://", 1).split("?", 1)[0]

    index_name = "instrument_strategy_tops_instrument_timeframe_uq"
    symbol = f"NKR{uuid.uuid4().hex[:6].upper()}"
    instrument_id = f"inst-nk-{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)

    def _index_present(connection: object) -> bool:
        found = connection.execute(  # type: ignore[attr-defined]
            text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
            {"n": index_name},
        ).scalar_one_or_none()
        return found is not None

    def _backing_constraint(connection: object) -> str | None:
        return connection.execute(  # type: ignore[attr-defined]
            text(
                "SELECT c.conname FROM pg_class idx "
                "JOIN pg_index ix ON ix.indexrelid = idx.oid "
                "JOIN pg_constraint c ON c.conindid = idx.oid "
                "WHERE idx.relname = :n"
            ),
            {"n": index_name},
        ).scalar_one_or_none()

    def _backstop(connection: object) -> str:
        """``"constraint"``, ``"indice"`` o ``"ausente"``: quién sostiene la clave natural.

        El mismo nombre tiene dos linajes posibles (docstring de la 041): el baseline ``003``
        lo crea como *constraint* al construir las tablas desde el modelo (BD nueva) y la 041
        como *índice plano* en una BD antigua.
        """
        if not _index_present(connection):
            return "ausente"
        return "constraint" if _backing_constraint(connection) is not None else "indice"

    def _drop_backstop(connection: object) -> None:
        """Deja la tabla SIN unicidad en la clave natural: el escenario real del incidente.

        El roundtrip no puede depender del linaje: ``downgrade`` a 040 retira lo que creó la
        041 (índice plano), pero **no** la constraint del baseline (no es suya, y ``DROP
        INDEX`` sobre ella aborta con ``DependentObjectsStillExist``). Se retira aquí,
        explícitamente, para poder sembrar las dos filas duplicadas que la 041 debe
        deduplicar al volver a head.
        """
        conname = _backing_constraint(connection)
        if conname is not None:
            connection.execute(  # type: ignore[attr-defined]
                text(f'ALTER TABLE instrument_strategy_tops DROP CONSTRAINT IF EXISTS "{conname}"')
            )
        connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))  # type: ignore[attr-defined]

    engine = create_engine(url)
    cfg = _alembic_config()
    try:
        with engine.connect() as connection:
            lineage = _backstop(connection)
            assert lineage != "ausente", "la 041 (o el baseline) debe sostener la clave natural"

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, _PREVIOUS_REVISION)
            cfg.attributes.pop("connection", None)
        with engine.connect() as connection:
            # Contrato del ``downgrade``: retira solo lo que creó la 041. Un nombre que
            # respalda una constraint del baseline 003 sobrevive (no es de la 041).
            expected = "ausente" if lineage == "indice" else "constraint"
            actual = _backstop(connection)
            assert actual == expected, f"downgrade de la 041 deja el backstop en '{actual}'"
            _drop_backstop(connection)
            connection.execute(
                text(
                    "INSERT INTO instruments (id, symbol, yahoo_symbol, name, exchange, country,"
                    " currency, type, is_active, created_at, updated_at) VALUES"
                    " (:id, :symbol, :yahoo, 'Roundtrip 041', 'BMAD', 'ES', 'EUR', 'stock', true,"
                    " :now, :now)"
                ),
                {"id": instrument_id, "symbol": symbol, "yahoo": symbol.lower(), "now": now},
            )
            # Dos filas con la MISMA clave natural: la vieja y la vigente.
            for row_id, updated in (
                ("ist_old", now - timedelta(hours=5)),
                ("ist_new", now),
            ):
                connection.execute(
                    text(
                        "INSERT INTO instrument_strategy_tops (id, instrument_id, symbol, timeframe,"
                        " status, version, evidence_level, slots, created_at, updated_at) VALUES"
                        " (:id, :iid, :symbol, '1d', 'semifinal', 1, 'in_sample_only',"
                        " CAST('[]' AS jsonb), :updated, :updated)"
                    ),
                    {"id": row_id, "iid": instrument_id, "symbol": symbol, "updated": updated},
                )
            connection.commit()

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert _index_present(connection) is True, "el upgrade recrea el índice único"
            remaining = (
                connection.execute(
                    text("SELECT id FROM instrument_strategy_tops WHERE instrument_id = :i"),
                    {"i": instrument_id},
                )
                .scalars()
                .all()
            )
            assert list(remaining) == ["ist_new"], (
                f"el dedupe conserva la fila más reciente, quedaron {remaining}"
            )
        assert alembic_head() != _PREVIOUS_REVISION
    finally:
        with engine.connect() as connection:
            connection.execute(text("DELETE FROM instruments WHERE id = :i"), {"i": instrument_id})
            connection.commit()
        engine.dispose()
