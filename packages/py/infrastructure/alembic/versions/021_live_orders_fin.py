"""V2.13 — live_orders restricciones financieras + lease de recovery (desc. 021).

Revision id corto (19 chars) por constraint ``alembic_version.version_num
varchar(32)`` (Prisma) — convención del repo (precedente 004).

Consolida la segunda línea de defensa sobre la máquina LiveOrder durable:
* ``quantity/filled_quantity/remaining_quantity`` → ``NUMERIC(18,6)`` (determinismo
  numérico, semántica idéntica al ledger financiero; deja de ser Float adánico).
* CHECK constraints financieras de invariante (jamás una fila corrupta tipo
  filled=120 / remaining=-20 / status=PARTIAL).
* Columnas de lease técnico del ``LiveOrderRecoveryWorker`` cross-PID
  (``recovery_worker_id`` / ``recovery_claimed_at``). No son estado de negocio.

Idempotente + standalone (estilo 020/013/017): guards por tabla/columna/constraint
sin imports de ORM (offline-safe).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "021_live_orders_fin"
down_revision = "020_live_orders"
branch_labels = None
depends_on = None

_TABLE = "live_orders"

# CHECK constraints financieras.
_CHECK_QUANTITY_POS = "live_orders_quantity_pos_check"
_CHECK_FILLED_BOUNDS = "live_orders_filled_bounds_check"
_CHECK_REMAINING = "live_orders_remaining_nonneg_check"
_CHECK_SUM = "live_orders_filled_remaining_sum_check"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE, "c": column}) is not None


def _constraint_exists(bind: sa.engine.Connection, constraint: str) -> bool:
    sql = (
        "SELECT 1 FROM pg_constraint"
        " WHERE conname = :n"
    )
    return bind.scalar(sa.text(sql), {"n": constraint}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return

    # 1) Lease técnico de recovery (nullable; no alter de datos).
    if not _column_exists(bind, "recovery_worker_id"):
        op.add_column(
            _TABLE,
            sa.Column("recovery_worker_id", sa.String(), nullable=True),
        )
    if not _column_exists(bind, "recovery_claimed_at"):
        op.add_column(
            _TABLE,
            sa.Column(
                "recovery_claimed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    # Cancellation docs / broker-confirm (V2.13 honest-cancel): quién/cuándo/por
    # qué pidió cancelar (decisión local) y, cuanto exista, confirm broker-side.
    if not _column_exists(bind, "cancel_requested_by"):
        op.add_column(_TABLE, sa.Column("cancel_requested_by", sa.String(), nullable=True))
    if not _column_exists(bind, "cancel_reason"):
        op.add_column(_TABLE, sa.Column("cancel_reason", sa.String(), nullable=True))
    if not _column_exists(bind, "cancel_requested_at"):
        op.add_column(
            _TABLE,
            sa.Column(
                "cancel_requested_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
    if not _column_exists(bind, "broker_cancel_confirmed_at"):
        op.add_column(
            _TABLE,
            sa.Column(
                "broker_cancel_confirmed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    # 2) Determinismo numérico: Float → NUMERIC(18,6) en cantidades.
    for col in ("quantity", "filled_quantity", "remaining_quantity"):
        op.alter_column(
            _TABLE,
            col,
            type_=sa.Numeric(18, 6),
            existing_type=sa.Float(),
            nullable=False,
        )

    # 3) Invariantes financieras (segunda línea de defensa sobre Python).
    if not _constraint_exists(bind, _CHECK_QUANTITY_POS):
        op.create_check_constraint(
            _CHECK_QUANTITY_POS,
            _TABLE,
            "quantity > 0",
        )
    if not _constraint_exists(bind, _CHECK_FILLED_BOUNDS):
        op.create_check_constraint(
            _CHECK_FILLED_BOUNDS,
            _TABLE,
            "filled_quantity >= 0 AND filled_quantity <= quantity",
        )
    if not _constraint_exists(bind, _CHECK_REMAINING):
        op.create_check_constraint(
            _CHECK_REMAINING,
            _TABLE,
            "remaining_quantity >= 0",
        )
    if not _constraint_exists(bind, _CHECK_SUM):
        op.create_check_constraint(
            _CHECK_SUM,
            _TABLE,
            "filled_quantity + remaining_quantity = quantity",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    for name in (
        _CHECK_SUM,
        _CHECK_REMAINING,
        _CHECK_FILLED_BOUNDS,
        _CHECK_QUANTITY_POS,
    ):
        if _constraint_exists(bind, name):
            op.drop_constraint(name, _TABLE, type_="check")
    for col in ("quantity", "filled_quantity", "remaining_quantity"):
        op.alter_column(
            _TABLE,
            col,
            type_=sa.Float(),
            existing_type=sa.Numeric(18, 6),
            nullable=False,
        )
    for col in ("recovery_claimed_at", "recovery_worker_id"):
        if _column_exists(bind, col):
            op.drop_column(_TABLE, col)
    for col in (
        "broker_cancel_confirmed_at",
        "cancel_requested_at",
        "cancel_reason",
        "cancel_requested_by",
    ):
        if _column_exists(bind, col):
            op.drop_column(_TABLE, col)
