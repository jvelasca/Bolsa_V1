"""041 — roundtrip del backstop de claves naturales sobre una BD scratch efímera.

Reproduce el incidente del 2026-09-14 (``MultipleResultsFound`` permanente en
``GET /instrument-daily-opinions``): la tabla queda SIN unicidad en la clave natural —el
escenario real, porque la 041 todavía no había corrido—, se siembran dos filas de la MISMA
clave con ``updated_at`` distinto y, al volver a head, el dedupe debe conservar solo la más
reciente y el índice único debe existir.

**Por qué vive aquí y no en ``apps/api-python/tests/test_unique_natural_keys_pg.py``.**
Ese fichero ejecutaba el ``downgrade`` **contra ``DATABASE_URL``**. Desde que la head es
``067_opinion_account_scope``, bajar a ``040`` arrastra también el ``downgrade`` de la 067,
que (a) retira ``position_open`` de todas las filas y (b) **descarta filas** cuando hay más
de una cuenta para el mismo ``(instrumento, día, fuente)``. Es decir: un test de la 041
pasó a ser destructivo sobre la base de desarrollo. Aquí la BD la crea y la borra el propio
test, y nunca se toca ``DATABASE_URL`` más allá de conectarse a ``postgres`` como
administrador para ``CREATE/DROP DATABASE``.

El test es consciente del **linaje** del nombre (ver docstring de la 041): en una BD nueva
el baseline ``003`` lo crea como *constraint* al construir las tablas desde el modelo, y en
una BD antigua lo crea la 041 como *índice plano*. El ``downgrade`` de la 041 solo retira
los planos —los suyos—, así que aquí se comprueba el contrato para cada linaje y se retira
el backstop a mano cuando el linaje lo deja en pie.

Gate: ``UNIQUE_NATURAL_KEYS_PG_REQUIRED=1`` convierte el skip en fallo duro.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from _profile_pg_helpers import (
    admin_url,
    current_revision,
    require_or_skip,
    scratch_database,
)

from bolsa_infrastructure.database.migrations import (
    alembic_head,
    downgrade_to,
    migrate_to,
)

_REQUIRED_ENV = "UNIQUE_NATURAL_KEYS_PG_REQUIRED"
_PREVIOUS_REVISION = "040_auto_v2_durable_state"
_TABLE = "instrument_strategy_tops"
_INDEX = "instrument_strategy_tops_instrument_timeframe_uq"


@pytest.fixture(scope="module", autouse=True)
def _require_scratch_database() -> None:
    """Skip honesto sin PostgreSQL; fallo duro si el job PG exige la certificación."""
    try:
        with psycopg.connect(admin_url(), autocommit=True) as conn:
            row = conn.execute(
                "SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
        if not row or not row[0]:
            raise RuntimeError("el usuario de BD no puede crear bases scratch (rolcreatedb)")
    except Exception as exc:  # noqa: BLE001 - el llamante decide skip/fail
        require_or_skip(
            exc,
            required_env=_REQUIRED_ENV,
            what="roundtrip de la migración 041 sobre BD scratch",
        )


def _index_present(url: str) -> bool:
    with psycopg.connect(url, autocommit=True) as conn:
        found = conn.execute(
            "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = %s",
            (_INDEX,),
        ).fetchone()
    return found is not None


def _backing_constraint(url: str) -> str | None:
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT c.conname FROM pg_class idx "
            "JOIN pg_index ix ON ix.indexrelid = idx.oid "
            "JOIN pg_class tbl ON tbl.oid = ix.indrelid "
            "JOIN pg_constraint c ON c.conindid = idx.oid "
            "WHERE idx.relname = %s AND tbl.relname = %s",
            (_INDEX, _TABLE),
        ).fetchone()
    return None if row is None else str(row[0])


def _backstop(url: str) -> str:
    """``"constraint"``, ``"indice"`` o ``"ausente"``: quién sostiene la clave natural.

    El mismo nombre tiene dos linajes posibles (docstring de la 041): el baseline ``003``
    lo crea como *constraint* al construir las tablas desde el modelo (BD nueva) y la 041
    como *índice plano* en una BD antigua.
    """
    if not _index_present(url):
        return "ausente"
    return "constraint" if _backing_constraint(url) is not None else "indice"


def _drop_backstop(url: str) -> None:
    """Deja la tabla SIN unicidad en la clave natural: el escenario real del incidente.

    El roundtrip no puede depender del linaje: ``downgrade`` a 040 retira lo que creó la
    041 (índice plano), pero **no** la constraint del baseline (no es suya, y ``DROP
    INDEX`` sobre ella aborta con ``DependentObjectsStillExist``). Se retira aquí,
    explícitamente, para poder sembrar las dos filas duplicadas que la 041 debe
    deduplicar al volver a head.
    """
    with psycopg.connect(url, autocommit=True) as conn:
        conname = _backing_constraint(url)
        if conname is not None:
            conn.execute(f'ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS "{conname}"')  # noqa: S608
        conn.execute(f'DROP INDEX IF EXISTS "{_INDEX}"')  # noqa: S608


def test_migration_041_dedupes_existing_duplicates_and_recreates_indexes() -> None:
    """Roundtrip 041 con duplicados preexistentes: dedupe conservador + índice único."""
    with scratch_database("bolsa_041_roundtrip") as url:
        migrate_to("head", database_url=url)
        assert current_revision(url) == alembic_head()

        lineage = _backstop(url)
        assert lineage != "ausente", "la 041 (o el baseline) debe sostener la clave natural"

        downgrade_to(_PREVIOUS_REVISION, database_url=url)
        assert current_revision(url) == _PREVIOUS_REVISION

        # Contrato del ``downgrade``: retira solo lo que creó la 041. Un nombre que
        # respalda una constraint del baseline 003 sobrevive (no es de la 041).
        expected = "ausente" if lineage == "indice" else "constraint"
        actual = _backstop(url)
        assert actual == expected, f"downgrade de la 041 deja el backstop en '{actual}'"

        _drop_backstop(url)
        assert _backstop(url) == "ausente", "no se pudo simular la tabla sin backstop"

        symbol = f"NKR{uuid.uuid4().hex[:6].upper()}"
        instrument_id = f"inst-nk-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(
                "INSERT INTO instruments (id, symbol, yahoo_symbol, name, exchange, country,"
                " currency, type, is_active, created_at, updated_at) VALUES"
                " (%s, %s, %s, 'Roundtrip 041', 'BMAD', 'ES', 'EUR', 'stock', true, %s, %s)",
                (instrument_id, symbol, symbol.lower(), now, now),
            )
            # Dos filas con la MISMA clave natural: la vieja y la vigente.
            for row_id, updated in (
                ("ist_old", now - timedelta(hours=5)),
                ("ist_new", now),
            ):
                conn.execute(
                    "INSERT INTO instrument_strategy_tops (id, instrument_id, symbol, timeframe,"
                    " status, version, evidence_level, slots, created_at, updated_at) VALUES"
                    " (%s, %s, %s, '1d', 'semifinal', 1, 'in_sample_only',"
                    " CAST('[]' AS jsonb), %s, %s)",
                    (row_id, instrument_id, symbol, updated, updated),
                )

        migrate_to("head", database_url=url)

        assert _index_present(url) is True, "el upgrade recrea el índice único"
        with psycopg.connect(url, autocommit=True) as conn:
            remaining = [
                str(row[0])
                for row in conn.execute(
                    "SELECT id FROM instrument_strategy_tops WHERE instrument_id = %s",
                    (instrument_id,),
                ).fetchall()
            ]
        assert remaining == ["ist_new"], (
            f"el dedupe conserva la fila más reciente, quedaron {remaining}"
        )
        assert alembic_head() != _PREVIOUS_REVISION
        # La tabla vuelve a rechazar un duplicado crudo: el backstop es real.
        with pytest.raises(psycopg.errors.UniqueViolation):
            with psycopg.connect(url, autocommit=True) as conn:
                conn.execute(
                    "INSERT INTO instrument_strategy_tops (id, instrument_id, symbol, timeframe,"
                    " status, version, evidence_level, slots, created_at, updated_at) VALUES"
                    " ('ist_dup', %s, %s, '1d', 'semifinal', 1, 'in_sample_only',"
                    " CAST('[]' AS jsonb), %s, %s)",
                    (instrument_id, symbol, now, now),
                )
