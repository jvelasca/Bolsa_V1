"""AUTO v2.88.79 — telemetría `activity` del motor (un latido no es una fase).

Cierra «¿Qué está haciendo AUTO?» con un hecho durable emitido por el propio worker en
cada tick: la columna ``activity`` de ``auto_engine_runs`` (y su traza en
``auto_engine_ticks``) lleva la fase operacional REAL del turno, no una inferencia de
``RUNNING``.

Aditiva y **sin backfill**: ``NULL`` significa "todavía no emitido / fila anterior a
2.88.79", y la UI lo declara «Sin dato todavía» — nunca una fase inventada. No se rellena
el pasado con una actividad que el motor no demostró.

Cadena lineal: ``down_revision = "050_idem_key_not_null"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "051_auto_engine_activity"
down_revision = "050_idem_key_not_null"
branch_labels = None
depends_on = None

_RUNS = "auto_engine_runs"
_TICKS = "auto_engine_ticks"
_ACTIVITY = "activity"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "c": column_name}) is not None


def _add_activity(bind: sa.engine.Connection, table_name: str) -> None:
    if not _table_exists(bind, table_name):
        return
    if not _column_exists(bind, table_name, _ACTIVITY):
        op.add_column(table_name, sa.Column(_ACTIVITY, sa.String(32), nullable=True))


def _drop_activity(bind: sa.engine.Connection, table_name: str) -> None:
    if not _table_exists(bind, table_name):
        return
    if _column_exists(bind, table_name, _ACTIVITY):
        op.drop_column(table_name, _ACTIVITY)


def upgrade() -> None:
    bind = op.get_bind()
    _add_activity(bind, _RUNS)
    _add_activity(bind, _TICKS)


def downgrade() -> None:
    bind = op.get_bind()
    _drop_activity(bind, _TICKS)
    _drop_activity(bind, _RUNS)
