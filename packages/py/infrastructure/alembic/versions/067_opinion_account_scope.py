"""067 — scope de CUENTA en el dictamen diario (``instrument_daily_opinions``).

La postura del dictamen depende de si **esa** cuenta tiene posición abierta, pero la caché
era única por ``(instrument_id, as_of_bar_date, source)``: la primera llamada del día fijaba
la postura y el resto de cuentas heredaban el resultado. Además el cálculo lo alimentaba el
cliente (``hints``), así que la fila podía quedar sellada con ``position_open=null`` o con
scores inventados.

Esta revisión:

* Añade ``position_open BOOLEAN NULL`` — la medición usada al calcular. Permite recomputar
  cuando la posición cambia dentro del mismo día y detectar filas no medidas.
* Rellena ``account_id`` nulo con el sentinel ``__global__`` y lo hace ``NOT NULL``: una fila
  sin cuenta es un hueco heredado, no «la postura de todo el mundo».
* Sustituye la unicidad ``(instrument_id, as_of_bar_date, source)`` por
  ``(instrument_id, as_of_bar_date, source, account_id)`` — el índice del upsert atómico.

``downgrade`` colapsa a la fila más reciente por ``(instrumento, día, fuente)`` (conservar
varias cuentas haría imposible recrear la clave antigua), devuelve ``__global__`` a ``NULL``
y retira ``position_open``.

Cadena lineal: ``down_revision = "066_account_evidence_policy"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "067_opinion_account_scope"
down_revision = "066_account_evidence_policy"
branch_labels = None
depends_on = None

_TABLE = "instrument_daily_opinions"
_NEW_UNIQUE = "instrument_daily_opinions_instrument_asof_source_account_key"
_OLD_UNIQUE_NAMES = (
    # Nombre corto que creó la 041 (índice plano o constraint del baseline).
    "instrument_daily_opinions_instrument_id_asof_source_key",
    # Nombre que declaró la migración Prisma original (65 chars → truncado por PG).
    "instrument_daily_opinions_instrument_id_as_of_bar_date_source_key",
)
_GLOBAL_SCOPE = "__global__"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table, "c": column}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def _backing_constraint(
    bind: sa.engine.Connection, table_name: str, index_name: str
) -> str | None:
    """Constraint que respalda el índice (``DROP INDEX`` falla si existe)."""
    sql = (
        "SELECT c.conname "
        "FROM pg_class idx "
        "JOIN pg_index ix ON ix.indexrelid = idx.oid "
        "JOIN pg_class tbl ON tbl.oid = ix.indrelid "
        "JOIN pg_constraint c ON c.conindid = idx.oid "
        "WHERE idx.relname = :idx AND tbl.relname = :tbl"
    )
    return bind.scalar(sa.text(sql), {"idx": index_name, "tbl": table_name})


def _drop_unique_if_present(bind: sa.engine.Connection, index_name: str) -> None:
    if not _index_exists(bind, index_name):
        return
    constraint = _backing_constraint(bind, _TABLE, index_name)
    if constraint is not None:
        op.drop_constraint(constraint, _TABLE, type_="unique")
    else:
        op.drop_index(index_name, table_name=_TABLE)


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return

    if not _column_exists(bind, _TABLE, "position_open"):
        op.add_column(_TABLE, sa.Column("position_open", sa.Boolean(), nullable=True))

    # Filas sin cuenta = hueco heredado: se declaran en el scope global, no se reparten.
    bind.execute(
        sa.text(
            f"UPDATE {_TABLE} SET account_id = :scope WHERE account_id IS NULL"  # noqa: S608
        ),
        {"scope": _GLOBAL_SCOPE},
    )
    bind.execute(sa.text(f"ALTER TABLE {_TABLE} ALTER COLUMN account_id SET NOT NULL"))  # noqa: S608

    for old_name in _OLD_UNIQUE_NAMES:
        _drop_unique_if_present(bind, old_name)
    if not _index_exists(bind, _NEW_UNIQUE):
        op.create_index(
            _NEW_UNIQUE,
            _TABLE,
            ["instrument_id", "as_of_bar_date", "source", "account_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return

    _drop_unique_if_present(bind, _NEW_UNIQUE)

    # La clave antigua no admite varias cuentas por (instrumento, día, fuente): se
    # conserva la fila más reciente y el resto se descarta.
    bind.execute(
        sa.text(
            f"""
            DELETE FROM {_TABLE} t
            USING (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY instrument_id, as_of_bar_date, source
                    ORDER BY updated_at DESC NULLS LAST,
                             computed_at DESC NULLS LAST,
                             id DESC
                ) AS rn
                FROM {_TABLE}
            ) d
            WHERE t.id = d.id AND d.rn > 1
            """  # noqa: S608 — identificadores internos
        )
    )
    old_name = _OLD_UNIQUE_NAMES[0]
    if not _index_exists(bind, old_name):
        op.create_index(
            old_name,
            _TABLE,
            ["instrument_id", "as_of_bar_date", "source"],
            unique=True,
        )

    # Primero se relaja el NOT NULL: el sentinel `__global__` no es una cuenta y debe
    # volver a NULL (hacerlo al revés viola la restricción).
    bind.execute(sa.text(f"ALTER TABLE {_TABLE} ALTER COLUMN account_id DROP NOT NULL"))  # noqa: S608
    bind.execute(
        sa.text(
            f"UPDATE {_TABLE} SET account_id = NULL WHERE account_id = :scope"  # noqa: S608
        ),
        {"scope": _GLOBAL_SCOPE},
    )

    if _column_exists(bind, _TABLE, "position_open"):
        op.drop_column(_TABLE, "position_open")
