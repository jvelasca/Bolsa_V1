"""067 — scope de CUENTA del dictamen diario sobre PostgreSQL real (base scratch).

Cierra la comprobación que faltaba para el cierre de Fase 4: la migración
``067_opinion_account_scope`` no se había ejercitado **con datos existentes**. El
roundtrip de ``test_unique_natural_keys_pg.py`` cubre la ``041``, no esta revisión.

Por qué una BD scratch y no ``DATABASE_URL``: el ``downgrade`` de la 067 **descarta**
filas (la clave antigua de tres columnas no admite varias cuentas por instrumento/día/
fuente). Ejecutarlo contra la base de desarrollo borraría dictámenes reales. La scratch
la crea y la borra el propio test.

Aviso de linaje (el mismo que documenta la 041): el baseline ``003`` construye las tablas
desde ``Base.metadata``, es decir, desde el **modelo vivo**. Por eso una base nueva ya
nace con ``position_open``, ``account_id NOT NULL`` y el índice de cuatro columnas, y la
067 es un no-op sobre ella. El escenario que importa —una base provisionada antes de la
067, que es la que existe en producción— se **construye explícitamente** bajando la tabla
a su forma previa antes de sembrar las filas heredadas.

Casos:

1. **Base nueva**: la 067 no rompe ni duplica lo que el baseline ya creó.
2. **Base heredada en 066 con datos**: ``account_id`` nulo pasa a ``__global__``, se
   conservan todas las filas y el ``NOT NULL`` rechaza un nulo crudo.
3. **``downgrade`` con varias cuentas**: colapsa a la fila más reciente, devuelve
   ``__global__`` a ``NULL`` sin ``NotNullViolation`` y restaura la clave de tres columnas.
4. **Reversibilidad**: volver a ``upgrade head`` recupera la forma de la 067 y rellena los
   nulos sin violar la restricción.

Gate: ``OPINION_ACCOUNT_SCOPE_PG_REQUIRED=1`` convierte el skip en fallo duro.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

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

_REQUIRED_ENV = "OPINION_ACCOUNT_SCOPE_PG_REQUIRED"
_PREVIOUS_REVISION = "066_account_evidence_policy"
_TARGET_REVISION = "067_opinion_account_scope"
_TABLE = "instrument_daily_opinions"
_NEW_UNIQUE = "instrument_daily_opinions_instrument_asof_source_account_key"
#: Nombre corto que crea la 041 (y que el baseline deja como constraint en base nueva).
_OLD_UNIQUE = "instrument_daily_opinions_instrument_id_asof_source_key"
_GLOBAL_SCOPE = "__global__"


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
            what="migración 067 del dictamen por cuenta sobre BD scratch",
        )


# --------------------------------------------------------------------------- sondas


def _column(url: str, column: str) -> tuple[bool, bool] | None:
    """``(existe, es_nullable)`` de una columna de ``instrument_daily_opinions``."""
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
            (_TABLE, column),
        ).fetchone()
    return None if row is None else (True, str(row[0]) == "YES")


def _indexdef(url: str, index_name: str) -> str | None:
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname = %s",
            (index_name,),
        ).fetchone()
    return None if row is None else str(row[0])


def _backing_constraint(url: str, index_name: str) -> str | None:
    """Constraint que respalda el índice (``DROP INDEX`` falla si existe)."""
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT c.conname FROM pg_class idx "
            "JOIN pg_index ix ON ix.indexrelid = idx.oid "
            "JOIN pg_class tbl ON tbl.oid = ix.indrelid "
            "JOIN pg_constraint c ON c.conindid = idx.oid "
            "WHERE idx.relname = %s AND tbl.relname = %s",
            (index_name, _TABLE),
        ).fetchone()
    return None if row is None else str(row[0])


def _drop_unique(url: str, index_name: str) -> None:
    with psycopg.connect(url, autocommit=True) as conn:
        constraint = _backing_constraint(url, index_name)
        if constraint is not None:
            conn.execute(
                f'ALTER TABLE {_TABLE} DROP CONSTRAINT "{constraint}"'  # noqa: S608
            )
        conn.execute(f'DROP INDEX IF EXISTS "{index_name}"')  # noqa: S608


def _rows(url: str) -> list[tuple[str, str | None, date, str]]:
    """``(id, account_id, día, fuente)`` de todas las filas del dictamen."""
    with psycopg.connect(url, autocommit=True) as conn:
        rows = conn.execute(
            "SELECT id, account_id, as_of_bar_date, source FROM "
            f"{_TABLE} ORDER BY id"  # noqa: S608
        ).fetchall()
    return [
        (str(r[0]), None if r[1] is None else str(r[1]), r[2], str(r[3]))  # type: ignore[arg-type]
        for r in rows
    ]


def _seed_instrument(url: str, symbol: str) -> str:
    instrument_id = f"inst-067-{uuid4().hex[:12]}"
    now = datetime.now(UTC)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO instruments (id, symbol, yahoo_symbol, name, exchange, country,"
            " currency, type, is_active, created_at, updated_at) VALUES"
            " (%s, %s, %s, 'Migración 067', 'BMAD', 'ES', 'EUR', 'stock', true, %s, %s)",
            (instrument_id, symbol, symbol.lower(), now, now),
        )
    return instrument_id


def _seed_opinion(
    url: str,
    *,
    row_id: str,
    instrument_id: str,
    account_id: str | None,
    day: date,
    source: str = "on_demand",
    updated_at: datetime,
    position_open: bool | None = False,
    with_position_open: bool = True,
) -> None:
    """Siembra un dictamen por SQL crudo (sin pasar por el modelo, que ya es post-067)."""
    columns = (
        "id, instrument_id, account_id, as_of_bar_date, stance, dictamen_stars,"
        " distress, reasons, source, engine_version, idempotency_key,"
        " computed_at, created_at, updated_at"
    )
    values: list[object] = [
        row_id,
        instrument_id,
        account_id,
        day,
        "neutral",
        3,
        False,
        "[]",
        source,
        "opinion_v1",
        f"{row_id}|key",
        updated_at,
        updated_at,
        updated_at,
    ]
    placeholders = "%s, %s, %s, %s, %s, %s, %s, CAST(%s AS jsonb), %s, %s, %s, %s, %s, %s"
    if with_position_open:
        columns += ", position_open"
        placeholders += ", %s"
        values.append(position_open)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            f"INSERT INTO {_TABLE} ({columns}) VALUES ({placeholders})",  # noqa: S608
            values,
        )


def _shape_to_pre_067(url: str) -> None:
    """Devuelve la tabla a la forma que tiene en producción antes de la 067.

    Necesario porque el baseline ``003`` la construye desde el modelo vivo: una base
    *nueva* ya nace con ``position_open``, ``account_id NOT NULL`` y la clave de cuatro
    columnas. Sin este paso el test heredado no probaría nada (la 067 sería un no-op).

    Ojo con la deriva que delata este paso: como el baseline ya crea la clave de cuatro
    columnas, la ``041`` encuentra ausente la de tres y la crea también, así que a ``066``
    conviven AMBOS índices en una base nueva. La base heredada real solo tiene el viejo,
    así que aquí se retiran los dos y se recrea únicamente el de tres columnas.
    """
    _drop_unique(url, _NEW_UNIQUE)
    _drop_unique(url, _OLD_UNIQUE)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f"ALTER TABLE {_TABLE} ALTER COLUMN account_id DROP NOT NULL")  # noqa: S608
        conn.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS position_open")  # noqa: S608
        conn.execute(
            f"CREATE UNIQUE INDEX {_OLD_UNIQUE} "  # noqa: S608
            f"ON {_TABLE} (instrument_id, as_of_bar_date, source)"
        )


# --------------------------------------------------------------------------- casos


def test_new_database_reaches_head_without_breaking_the_baseline_shape() -> None:
    """Base nueva: la 067 es idempotente sobre lo que el baseline ya creó."""
    with scratch_database("bolsa_067_new") as url:
        migrate_to("head", database_url=url)

        assert alembic_head() == _TARGET_REVISION
        assert current_revision(url) == _TARGET_REVISION

        position_open = _column(url, "position_open")
        assert position_open == (True, True), "position_open debe existir y admitir NULL"
        assert _column(url, "account_id") == (True, False), "account_id debe ser NOT NULL"

        new_def = _indexdef(url, _NEW_UNIQUE)
        assert new_def is not None and "UNIQUE INDEX" in new_def
        for column in ("instrument_id", "as_of_bar_date", "source", "account_id"):
            assert column in new_def, f"{_NEW_UNIQUE} no cubre {column}"
        assert _indexdef(url, _OLD_UNIQUE) is None, "la clave de tres columnas no debe sobrevivir"


def test_legacy_rows_without_account_are_backfilled_to_global_scope() -> None:
    """Datos heredados en 066: los ``account_id`` nulos se declaran en el scope global."""
    with scratch_database("bolsa_067_legacy") as url:
        migrate_to(_PREVIOUS_REVISION, database_url=url)
        _shape_to_pre_067(url)

        # La base está realmente en la forma previa, no en la del modelo vivo.
        assert current_revision(url) == _PREVIOUS_REVISION
        assert _column(url, "position_open") is None
        assert _column(url, "account_id") == (True, True)
        assert _indexdef(url, _NEW_UNIQUE) is None
        assert _indexdef(url, _OLD_UNIQUE) is not None

        symbol = f"LEG{uuid4().hex[:6].upper()}"
        instrument_id = _seed_instrument(url, symbol)
        now = datetime.now(UTC)
        seeded = (
            ("ido_legacy_1", None, date(2026, 11, 3), "on_demand"),
            ("ido_legacy_2", None, date(2026, 11, 4), "on_demand"),
            ("ido_legacy_3", None, date(2026, 11, 4), "eod"),
            # Una fila que YA tenía cuenta (no debe reescribirse). Va en otro día porque la
            # clave heredada de tres columnas NO admite dos filas por instrumento/día/fuente:
            # ese es exactamente el límite que la 067 elimina.
            ("ido_legacy_4", "acc-legacy-067", date(2026, 11, 5), "on_demand"),
        )
        for index, (row_id, account_id, day, source) in enumerate(seeded):
            _seed_opinion(
                url,
                row_id=row_id,
                instrument_id=instrument_id,
                account_id=account_id,
                day=day,
                source=source,
                updated_at=now + timedelta(minutes=index),
                with_position_open=False,
            )

        migrate_to("head", database_url=url)

        assert current_revision(url) == _TARGET_REVISION
        rows = {row[0]: row for row in _rows(url)}
        assert set(rows) == {row_id for row_id, *_ in seeded}, "el upgrade perdió filas"
        for row_id, account_id, _day, _source in seeded:
            stored = rows[row_id][1]
            if account_id is None:
                assert stored == _GLOBAL_SCOPE, f"{row_id}: nulo no declarado en el scope global"
            else:
                assert stored == account_id, f"{row_id}: se reescribió una cuenta real"

        # Filas heredadas = no medidas al calcular, nunca «sin posición».
        with psycopg.connect(url, autocommit=True) as conn:
            position_values = conn.execute(
                f"SELECT DISTINCT position_open FROM {_TABLE}"  # noqa: S608
            ).fetchall()
        assert position_values == [(None,)], "las filas heredadas no deben inventar posición"

        assert _column(url, "account_id") == (True, False)
        assert _indexdef(url, _OLD_UNIQUE) is None
        new_def = _indexdef(url, _NEW_UNIQUE)
        assert new_def is not None and "account_id" in new_def

        # El NOT NULL es real: un escritor que se salte el repositorio no puede reintroducir nulos.
        with pytest.raises(psycopg.errors.NotNullViolation):
            _seed_opinion(
                url,
                row_id="ido_legacy_null",
                instrument_id=instrument_id,
                account_id=None,
                day=date(2026, 11, 5),
                updated_at=now,
            )


def test_downgrade_collapses_accounts_and_relaxes_not_null_before_backfill() -> None:
    """``downgrade``: conserva la fila más reciente y devuelve ``__global__`` a ``NULL``."""
    with scratch_database("bolsa_067_down") as url:
        migrate_to("head", database_url=url)

        symbol = f"DWN{uuid4().hex[:6].upper()}"
        instrument_id = _seed_instrument(url, symbol)
        now = datetime.now(UTC)
        day = date(2026, 11, 4)
        # Misma clave de tres columnas, dos cuentas: la antigua clave no admite ambas.
        _seed_opinion(
            url,
            row_id="ido_acc_a",
            instrument_id=instrument_id,
            account_id="acc-a",
            day=day,
            updated_at=now - timedelta(hours=2),
        )
        _seed_opinion(
            url,
            row_id="ido_acc_b",
            instrument_id=instrument_id,
            account_id="acc-b",
            day=day,
            updated_at=now,
        )
        # Fila en el scope global, en otro día: debe volver a NULL sin violar el NOT NULL.
        _seed_opinion(
            url,
            row_id="ido_global",
            instrument_id=instrument_id,
            account_id=_GLOBAL_SCOPE,
            day=date(2026, 11, 3),
            updated_at=now,
        )

        downgrade_to(_PREVIOUS_REVISION, database_url=url)

        assert current_revision(url) == _PREVIOUS_REVISION
        rows = {row[0]: row for row in _rows(url)}
        assert set(rows) == {"ido_acc_b", "ido_global"}, (
            f"el downgrade debe conservar la fila más reciente por clave; quedaron {sorted(rows)}"
        )
        assert rows["ido_acc_b"][1] == "acc-b"
        assert rows["ido_global"][1] is None, "el sentinel __global__ debe volver a NULL sin violar NOT NULL"

        assert _column(url, "position_open") is None, "el downgrade debe retirar position_open"
        assert _column(url, "account_id") == (True, True), "el downgrade debe relajar el NOT NULL"
        assert _indexdef(url, _NEW_UNIQUE) is None
        old_def = _indexdef(url, _OLD_UNIQUE)
        assert old_def is not None and "account_id" not in old_def
        for column in ("instrument_id", "as_of_bar_date", "source"):
            assert column in old_def, f"{_OLD_UNIQUE} no cubre {column}"

        # El esquema previo vuelve a aceptar una fila sin cuenta.
        _seed_opinion(
            url,
            row_id="ido_after_down",
            instrument_id=instrument_id,
            account_id=None,
            day=date(2026, 11, 6),
            updated_at=now,
            with_position_open=False,
        )


def test_upgrade_after_downgrade_is_reversible_and_refills_the_null_again() -> None:
    """Reversibilidad: el segundo ``upgrade`` repone la 067 sobre lo que dejó el ``downgrade``."""
    with scratch_database("bolsa_067_roundtrip") as url:
        migrate_to("head", database_url=url)

        symbol = f"RND{uuid4().hex[:6].upper()}"
        instrument_id = _seed_instrument(url, symbol)
        now = datetime.now(UTC)
        _seed_opinion(
            url,
            row_id="ido_rt_global",
            instrument_id=instrument_id,
            account_id=_GLOBAL_SCOPE,
            day=date(2026, 11, 4),
            updated_at=now,
        )

        downgrade_to(_PREVIOUS_REVISION, database_url=url)
        assert _column(url, "account_id") == (True, True)
        assert {row[0]: row[1] for row in _rows(url)} == {"ido_rt_global": None}

        # Ya en 066, el esquema vuelve a admitir filas sin cuenta (el hueco heredado).
        _seed_opinion(
            url,
            row_id="ido_rt_null",
            instrument_id=instrument_id,
            account_id=None,
            day=date(2026, 11, 5),
            updated_at=now,
            with_position_open=False,
        )

        migrate_to("head", database_url=url)

        assert current_revision(url) == _TARGET_REVISION
        assert _column(url, "position_open") == (True, True)
        assert _column(url, "account_id") == (True, False)
        assert _indexdef(url, _NEW_UNIQUE) is not None
        assert _indexdef(url, _OLD_UNIQUE) is None
        assert {row[0]: row[1] for row in _rows(url)} == {
            "ido_rt_global": _GLOBAL_SCOPE,
            "ido_rt_null": _GLOBAL_SCOPE,
        }, "el segundo upgrade debe rellenar los nulos sin NotNullViolation"
