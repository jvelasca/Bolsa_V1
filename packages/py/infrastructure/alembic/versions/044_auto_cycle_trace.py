"""AUTO trazas (V2.47) — ``cycle_id`` híbrido: columnas indexadas donde hay que consultar.

El ``cycle_id`` es la identidad financiera del **ciclo completo** (señal → decisión →
reserva → orden → fill → posición → salida → PnL). Se acuña de forma **determinista** por
``(account_id, signal_id)`` en el motor de entrada, de modo que dos workers que planifican la
misma señal convergen en el mismo identificador (mismo criterio que el ``entry_decision_id``
``dec-<hash>``). Donde ya hay JSONB (journal de decisión, ``V2TickPlan``,
``sim_auto_positions.position_state``) viaja sin migración; esta migración añade **solo** las
columnas que hay que poder **indexar y consultar**:

1. ``portfolio_reservations.cycle_id`` — permite resolver "¿qué reservas pertenecen a este
   ciclo?" sin recorrer el libro.
2. ``auto_exit_orders.cycle_id`` — el intent de salida hereda el ciclo de su posición, así
   que el PnL de un ciclo se puede reconstruir desde la salida hacia atrás.
3. ``sim_fill_finance_context.cycle_id`` — sin esta columna el trazado inverso
   posición → fill → reserva → decisión es **imposible**: es la costura donde el fill durable
   se materializa, y es lo que ata el efecto financiero a su ciclo.

Aditiva y **sin backfill**: ``NULL`` significa "fila anterior a 2.47 — desconocido", nunca un
cero fabricado. ``upgrade`` y ``downgrade`` son simétricos e idempotentes (patrón 028–043) y la
cadena es lineal (``down_revision = "043_exit_identity_and_kill_state"``).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "044_auto_cycle_trace"
down_revision = "043_exit_identity_and_kill_state"
branch_labels = None
depends_on = None

_COLUMN = "cycle_id"

_RESERVATIONS = "portfolio_reservations"
_RESERVATIONS_IDX = "portfolio_reservations_cycle_id_idx"

_EXIT_TABLE = "auto_exit_orders"
_EXIT_IDX = "auto_exit_orders_cycle_id_idx"

_FILL_CONTEXT = "sim_fill_finance_context"
_FILL_CONTEXT_IDX = "sim_fill_finance_context_cycle_id_idx"


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


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def _add_cycle_column(bind: sa.engine.Connection, table_name: str, index_name: str) -> None:
    """Añade ``cycle_id`` (nullable) + índice si faltan, de forma idempotente y offline-safe."""
    if not _table_exists(bind, table_name):
        return
    if not _column_exists(bind, table_name, _COLUMN):
        op.add_column(table_name, sa.Column(_COLUMN, sa.String(), nullable=True))
    if _column_exists(bind, table_name, _COLUMN) and not _index_exists(bind, index_name):
        op.create_index(index_name, table_name, [_COLUMN])


def _drop_cycle_column(bind: sa.engine.Connection, table_name: str, index_name: str) -> None:
    if not _table_exists(bind, table_name):
        return
    if _index_exists(bind, index_name):
        op.drop_index(index_name, table_name=table_name)
    if _column_exists(bind, table_name, _COLUMN):
        op.drop_column(table_name, _COLUMN)


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1) La reserva recuerda a qué ciclo pertenece ───────────────────────────
    _add_cycle_column(bind, _RESERVATIONS, _RESERVATIONS_IDX)

    # ── 2) El intent de salida hereda el ciclo de la posición ──────────────────
    _add_cycle_column(bind, _EXIT_TABLE, _EXIT_IDX)

    # ── 3) El fill durable cierra el trazado inverso (posición→fill→reserva) ───
    _add_cycle_column(bind, _FILL_CONTEXT, _FILL_CONTEXT_IDX)


def downgrade() -> None:
    """Retira exactamente lo que creó el upgrade: tres columnas y sus tres índices.

    Simétrico por construcción: el baseline no respalda estos nombres con constraints, así
    que el ``DROP`` es seguro e idempotente sea cual sea el orden.
    """
    bind = op.get_bind()

    _drop_cycle_column(bind, _FILL_CONTEXT, _FILL_CONTEXT_IDX)
    _drop_cycle_column(bind, _EXIT_TABLE, _EXIT_IDX)
    _drop_cycle_column(bind, _RESERVATIONS, _RESERVATIONS_IDX)
