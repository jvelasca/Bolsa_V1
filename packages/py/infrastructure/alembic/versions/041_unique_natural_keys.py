"""Reconciliación Prisma→Alembic de claves naturales únicas (8 tablas).

Incidente que la motiva (2026-09-14): ``GET /instrument-daily-opinions`` quedó en
``sqlalchemy.exc.MultipleResultsFound`` **permanente**. Causa raíz doble:

1. La migración Prisma ``20260727160000_instrument_strategy_tops`` declaró
   ``UNIQUE (instrument_id, timeframe)``, pero el baseline Alembic (003) solo copia
   columnas y constraints de FK/``UniqueConstraint`` de ``tables.py``: al no estar
   declarada en el modelo, el índice nunca se creó. La tabla quedó sin backstop.
2. ``instrument_strategy_top_repository.upsert`` es un check-then-insert
   (``get()`` → INSERT): dos escritores concurrentes ven ``None`` e insertan ambos.
   Quedaron 12 pares duplicados con ``created_at`` a 7-8 ms de distancia.

Como ``get()`` usa ``scalar_one_or_none()``, el duplicado no es un 500 transitorio:
envenena la ruta para siempre (el propio ``upsert`` empieza llamando a ``get()``).

Inventario medido antes de escribir esta migración (BD de desarrollo, 2026-09-15):
de las 10 claves naturales de ``schema.prisma``, 8 faltaban en la BD y **solo**
``instrument_strategy_tops`` tenía duplicados (12 grupos / 24 filas). Las otras 7
están limpias a día de hoy, así que se pueden crear sus índices sin borrar nada.

Diseño del dedupe (conservador y explícito):

* ``instrument_strategy_tops``: la fila es una caché derivada del embudo coach; la
  más reciente (``updated_at``, ``created_at``, ``id``) es la vigente por
  construcción → se conserva esa y se borran las demás.
* Las otras 7: **no se borra nada automáticamente**. Si alguna tuviera duplicados,
  la migración aborta con un error que nombra tabla y filas, porque en ellas el
  borrado no es una decisión de la migración (``instruments``/``positions`` cascadean
  a datos financieros; ``position_policies``/``instrument_narratives`` son contenido
  de usuario). Fail-closed: mejor bloqueo visible que pérdida de datos silenciosa.

Guards idempotentes offline-safe (patrón 028–040): si la BD vino de Prisma, los
nombres de índice son los mismos y se detectan como existentes. Cadena lineal:
``down_revision = "040_auto_v2_durable_state"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "041_unique_natural_keys"
down_revision = "040_auto_v2_durable_state"
branch_labels = None
depends_on = None

# (tabla, columnas de la clave natural, nombre canónico del índice Prisma)
_TARGETS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("instruments", ("symbol", "exchange"), "instruments_symbol_exchange_key"),
    (
        "positions",
        ("portfolio_id", "instrument_id"),
        "positions_portfolio_id_instrument_id_key",
    ),
    (
        "data_snapshots",
        ("instrument_id", "timeframe", "data_version"),
        "data_snapshots_instrument_timeframe_version_idx",
    ),
    (
        "position_policies",
        ("account_id", "instrument_id"),
        "position_policies_account_instrument_idx",
    ),
    (
        "instrument_daily_opinions",
        ("instrument_id", "as_of_bar_date", "source"),
        "instrument_daily_opinions_instrument_id_asof_source_key",
    ),
    (
        "instrument_narratives",
        ("instrument_id", "scope"),
        "instrument_narratives_instrument_id_scope_key",
    ),
    (
        "instrument_strategy_tops",
        ("instrument_id", "timeframe"),
        "instrument_strategy_tops_instrument_timeframe_uq",
    ),
    (
        "instrument_list_items",
        ("list_id", "instrument_id"),
        "instrument_list_items_list_id_instrument_id_key",
    ),
)

# Única tabla cuyo dedupe automático es seguro (caché derivada; la más reciente manda).
_AUTO_DEDUPE = "instrument_strategy_tops"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _columns_exist(bind: sa.engine.Connection, table_name: str, columns: tuple[str, ...]) -> bool:
    sql = (
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    found = {str(name) for name in bind.scalars(sa.text(sql), {"t": table_name})}
    return set(columns).issubset(found)


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def _duplicate_sample(
    bind: sa.engine.Connection, table_name: str, columns: tuple[str, ...]
) -> list[tuple[object, ...]]:
    """Muestra de grupos duplicados (hasta 5) para poder nombrarlos en el error."""
    sel = ", ".join(columns)
    sql = (
        f"SELECT {sel}, COUNT(*) AS n FROM {table_name} "  # noqa: S608 — identificadores internos
        f"GROUP BY {sel} HAVING COUNT(*) > 1 ORDER BY n DESC, {sel} LIMIT 5"
    )
    return [tuple(row) for row in bind.execute(sa.text(sql)).all()]


def _dedupe_keep_newest(
    bind: sa.engine.Connection, table_name: str, columns: tuple[str, ...]
) -> int:
    """Borra duplicados conservando la fila más reciente. Devuelve cuántas borró."""
    partition = ", ".join(columns)
    sql = f"""
        DELETE FROM {table_name} t
        USING (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY {partition}
                ORDER BY updated_at DESC NULLS LAST,
                         created_at DESC NULLS LAST,
                         id DESC
            ) AS rn
            FROM {table_name}
        ) d
        WHERE t.id = d.id AND d.rn > 1
    """  # noqa: S608 — identificadores internos
    result = bind.execute(sa.text(sql))
    return int(result.rowcount or 0)


def upgrade() -> None:
    bind = op.get_bind()

    for table_name, columns, index_name in _TARGETS:
        # Offline-safe: si la tabla/columnas no existen (BD anterior al baseline) se omite.
        if not _table_exists(bind, table_name):
            continue
        if not _columns_exist(bind, table_name, columns):
            continue
        if _index_exists(bind, index_name):
            continue

        if table_name == _AUTO_DEDUPE:
            _dedupe_keep_newest(bind, table_name, columns)
        else:
            duplicates = _duplicate_sample(bind, table_name, columns)
            if duplicates:
                raise RuntimeError(
                    f"041: {table_name} tiene duplicados en {columns} y el borrado automático "
                    f"no es seguro. Resuélvelos a mano y reintenta. Muestra: {duplicates}"
                )

        op.create_index(index_name, table_name, list(columns), unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, _columns, index_name in _TARGETS:
        if _index_exists(bind, index_name):
            op.drop_index(index_name, table_name=table_name)
