"""AUTO-3 cierre de fiabilidad (V2.43.3) — kill state durable + identidad de salida.

Cierra los dos P0 de la auditoría de ``v2.43.2-beta``: la parada DURA y la identidad de
una orden de salida pertenecían a la MEMORIA del proceso, así que un crash las olvidaba.

1. ``auto_kill_state`` — el latcheo del ``HardKillSwitch`` como propiedad del SISTEMA, no
   del proceso. Una fila por ``(account_id, engine_id)`` con el motivo tipificado, el
   instante de activación, la identidad de la activación (``engagement_id``), el contador
   de reengagements y el rastro de la liberación. Sin fila ⇒ la parada nunca se activó.
   El arranque LEE esta tabla ANTES de readoptar posición: un reinicio no puede olvidar el
   HALT (invariante que el in-memory no podía dar).
2. ``auto_exit_orders`` — el INTENT de salida con identidad propia (``exit_order_id``,
   ULID) que sobrevive a decisión → reserva → orden → fills parciales → reintento →
   reinicio. Antes la identidad era ``exit:{engine}:{symbol}:{seq}`` con ``seq`` de un
   contador de proceso (``_v2_exit_seq``) que volvía a 0 en cada arranque, así que un
   reinicio podía REUTILIZAR una identidad histórica. La columna ``emergency`` marca el
   intent de emergencia que se persiste cuando la reserva NO llega a ser durable (política
   B de la auditoría): una salida protectora sigue emitiéndose, pero nunca sin identidad.
3. ``portfolio_reservations.exit_order_id`` — columna nullable que enlaza la reserva con su
   intent. Nullable a propósito: las reservas históricas (compra y filas previas) no tienen
   intent y siguen siendo válidas. El índice permite resolver "¿qué reserva es de este
   intent?" sin recorrer el libro.

Aditiva y sin backfill: la ausencia de fila es información (no hay parada, no hay intent),
nunca un cero inventado. ``upgrade`` y ``downgrade`` son simétricos e idempotentes
(patrón 028–042), y la cadena es lineal (``down_revision = "042_portfolio_reservations"``).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "043_exit_identity_and_kill_state"
down_revision = "042_portfolio_reservations"
branch_labels = None
depends_on = None

_KILL_TABLE = "auto_kill_state"
_KILL_ACCOUNT_ENGAGED_IDX = "auto_kill_state_account_engaged_idx"

_EXIT_TABLE = "auto_exit_orders"
_EXIT_ACCOUNT_STATE_IDX = "auto_exit_orders_account_state_idx"
_EXIT_ACCOUNT_INSTRUMENT_IDX = "auto_exit_orders_account_instrument_idx"

_RESERVATIONS = "portfolio_reservations"
_EXIT_ORDER_COLUMN = "exit_order_id"
_RESERVATIONS_EXIT_ORDER_IDX = "portfolio_reservations_exit_order_id_idx"


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


def _create_kill_state(bind: sa.engine.Connection) -> None:
    """Crea ``auto_kill_state`` si falta (idempotente y offline-safe)."""
    if _table_exists(bind, _KILL_TABLE):
        return
    op.create_table(
        _KILL_TABLE,
        sa.Column("account_id", sa.String(), primary_key=True),
        sa.Column("engine_id", sa.String(), primary_key=True),
        sa.Column(
            "engaged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # 32 y no 16: los motivos canónicos de ``hard_kill_switch`` son más largos que eso
        # (``RECONCILIATION_FAILURE``/``DUPLICATE_EXECUTION``) y ``String(16)`` abortaría
        # la activación con ``StringDataRightTruncation``.
        sa.Column("reason", sa.String(32), nullable=True),
        sa.Column("engaged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engagement_id", sa.String(), nullable=True),
        sa.Column(
            "reengagements",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_actor", sa.String(), nullable=True),
        sa.Column("release_reconciliation_id", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def _create_exit_orders(bind: sa.engine.Connection) -> None:
    """Crea ``auto_exit_orders`` si falta (idempotente y offline-safe)."""
    if _table_exists(bind, _EXIT_TABLE):
        return
    op.create_table(
        _EXIT_TABLE,
        sa.Column("exit_order_id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), nullable=True),
        sa.Column("engine_id", sa.String(), nullable=True),
        sa.Column("instrument_id", sa.String(), nullable=True),
        sa.Column("side", sa.String(16), nullable=True),
        sa.Column("requested_qty", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "filled_qty",
            sa.Numeric(18, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "remaining_qty",
            sa.Numeric(18, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("reservation_id", sa.String(), nullable=True),
        sa.Column("venue_order_id", sa.String(), nullable=True),
        sa.Column(
            "state",
            sa.String(32),
            nullable=False,
            server_default="INTENT",
        ),
        sa.Column(
            "emergency",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1) El latcheo durable de la parada dura ────────────────────────────────
    _create_kill_state(bind)
    if _table_exists(bind, _KILL_TABLE) and not _index_exists(
        bind, _KILL_ACCOUNT_ENGAGED_IDX
    ):
        op.create_index(_KILL_ACCOUNT_ENGAGED_IDX, _KILL_TABLE, ["account_id", "engaged"])

    # ── 2) El INTENT de salida con identidad duradera ──────────────────────────
    _create_exit_orders(bind)
    if _table_exists(bind, _EXIT_TABLE):
        if not _index_exists(bind, _EXIT_ACCOUNT_STATE_IDX):
            op.create_index(
                _EXIT_ACCOUNT_STATE_IDX, _EXIT_TABLE, ["account_id", "state"]
            )
        if not _index_exists(bind, _EXIT_ACCOUNT_INSTRUMENT_IDX):
            op.create_index(
                _EXIT_ACCOUNT_INSTRUMENT_IDX,
                _EXIT_TABLE,
                ["account_id", "instrument_id"],
            )

    # ── 3) El enlace reserva → intent (nullable: las históricas no tienen) ─────
    if _table_exists(bind, _RESERVATIONS):
        if not _column_exists(bind, _RESERVATIONS, _EXIT_ORDER_COLUMN):
            op.add_column(
                _RESERVATIONS,
                sa.Column(_EXIT_ORDER_COLUMN, sa.String(), nullable=True),
            )
        if not _index_exists(bind, _RESERVATIONS_EXIT_ORDER_IDX) and _column_exists(
            bind, _RESERVATIONS, _EXIT_ORDER_COLUMN
        ):
            op.create_index(
                _RESERVATIONS_EXIT_ORDER_IDX,
                _RESERVATIONS,
                [_EXIT_ORDER_COLUMN],
            )


def downgrade() -> None:
    """Retira lo que creó esta migración: índice y columna, después las tablas.

    Simétrico por construcción: el baseline ``003`` no copia los ``Index`` de
    ``__table_args__``, así que los cuatro nombres de este upgrade son de la 043 y ninguno
    está respaldado por una constraint; ``DROP`` es seguro sin la danza de
    ``DependentObjectsStillExist``.
    """
    bind = op.get_bind()

    if _table_exists(bind, _RESERVATIONS):
        if _index_exists(bind, _RESERVATIONS_EXIT_ORDER_IDX):
            op.drop_index(_RESERVATIONS_EXIT_ORDER_IDX, table_name=_RESERVATIONS)
        if _column_exists(bind, _RESERVATIONS, _EXIT_ORDER_COLUMN):
            op.drop_column(_RESERVATIONS, _EXIT_ORDER_COLUMN)

    if _table_exists(bind, _EXIT_TABLE):
        for index_name in (_EXIT_ACCOUNT_INSTRUMENT_IDX, _EXIT_ACCOUNT_STATE_IDX):
            if _index_exists(bind, index_name):
                op.drop_index(index_name, table_name=_EXIT_TABLE)
        op.drop_table(_EXIT_TABLE)

    if _table_exists(bind, _KILL_TABLE):
        if _index_exists(bind, _KILL_ACCOUNT_ENGAGED_IDX):
            op.drop_index(_KILL_ACCOUNT_ENGAGED_IDX, table_name=_KILL_TABLE)
        op.drop_table(_KILL_TABLE)
