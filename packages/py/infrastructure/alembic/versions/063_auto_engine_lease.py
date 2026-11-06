"""063 — lease de ownership del ciclo AUTO entre procesos (P7, auditoría .183).

La auditoría .183 dejó abierto el hueco que ni el ``asyncio.Lock`` ni el claim por barra
pueden cerrar solos: dos **procesos** del MISMO ``engine_id`` (dos contenedores del
scheduler, un reinicio solapado, un deploy azul/verde) conducen el mismo motor con RAM
distinta. El lock intra-proceso de #78 serializa dentro de un proceso, pero entre procesos
nadie arbitra: ambos leen ``_open`` de su propia memoria y ambos escriben el ledger.

Esta revisión añade a ``auto_engine_runs`` la terna de lease que ya usa
``execution_events`` (``025``/``026``), con la misma semántica CAS:

* ``lease_owner`` — identidad del proceso que conduce el motor (``auto-sim-<pid>-<rand>``).
  ``NULL`` = sin dueño (nadie conduce o el dueño soltó el lease).
* ``lease_generation`` — contador monótono que se incrementa en CADA adquisición. Es la
  valla (fence): un tick lleva la generación con la que empezó, y el store rechaza la
  escritura si la generación ya no es la suya (el lease fue robado por otro proceso).
* ``lease_expires_at`` — vencimiento (TTL). Sólo un lease vencido (o inexistente) puede
  ser adquirido por otro proceso; el dueño lo renueva antes de cada ciclo.

Aditivo, nullable y con ``server_default`` en la generación: las filas existentes quedan
sin dueño (``lease_generation = 0``) y el primer proceso que arranque lo adquiere.

``downgrade`` retira las tres columnas (nunca la tabla ni los contadores).

Cadena lineal: ``down_revision = "062_sync_settings_check_backfill"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "063_auto_engine_lease"
down_revision = "062_sync_settings_check_backfill"
branch_labels = None
depends_on = None

_RUNS = "auto_engine_runs"
_LEASE_INDEX = "auto_engine_runs_lease_expires_idx"


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


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _RUNS):
        # Base anterior a la 027 (sin espejo durable del motor): nada que alterar. La 027
        # crea la tabla completa y esta revisión no tiene sentido sobre la nada.
        return
    if not _column_exists(bind, _RUNS, "lease_owner"):
        op.add_column(_RUNS, sa.Column("lease_owner", sa.String(), nullable=True))
    if not _column_exists(bind, _RUNS, "lease_generation"):
        op.add_column(
            _RUNS,
            sa.Column(
                "lease_generation",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    if not _column_exists(bind, _RUNS, "lease_expires_at"):
        op.add_column(
            _RUNS,
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
    # Índice de vencimiento: es el predicado de la adquisición (`expires_at <= now`) y el
    # que consulta un operador para distinguir «lease vivo» de «lease abandonado».
    if not _index_exists(bind, _LEASE_INDEX):
        op.create_index(_LEASE_INDEX, _RUNS, ["lease_expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _RUNS):
        return
    if _index_exists(bind, _LEASE_INDEX):
        op.drop_index(_LEASE_INDEX, table_name=_RUNS)
    for column in ("lease_expires_at", "lease_generation", "lease_owner"):
        if _column_exists(bind, _RUNS, column):
            op.drop_column(_RUNS, column)
