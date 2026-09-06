"""XL-3 — ``live_orders`` durable (V2.12 UNKNOWN recovery cross-PID).

Rastro LIVE real persistido cuando el adapter LIVE confirma ``submitted`` o
``unknown`` (bridge lo retiene o no sabemos si existe). ``LiveOrderRecoveryWorker``
lo relee para resolver UNKNOWN vía query_broker (NUNCA re-POST) sin depender del
worker/request que creó la fila. Idempotente: omite tabla/índices si ya existen.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "020_live_orders"
down_revision = "019_outbox_position_fifo"
branch_labels = None
depends_on = None

_TABLE = "live_orders"
_ACCOUNT_STATUS_IDX = "live_orders_account_id_status_idx"
_UPDATED_AT_IDX = "live_orders_updated_at_idx"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("order_id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("venue", sa.String(), nullable=False),
        sa.Column("instrument_id", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("filled_quantity", sa.Float(), nullable=False),
        sa.Column("remaining_quantity", sa.Float(), nullable=False),
        sa.Column("venue_order_id", sa.String(), nullable=True),
        sa.Column("intent_id", sa.String(), nullable=True),
        sa.Column("financial_apply_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(_ACCOUNT_STATUS_IDX, _TABLE, ["account_id", "status"])
    op.create_index(_UPDATED_AT_IDX, _TABLE, ["updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if _index_exists(bind, _ACCOUNT_STATUS_IDX):
        op.drop_index(_ACCOUNT_STATUS_IDX, table_name=_TABLE)
    if _index_exists(bind, _UPDATED_AT_IDX):
        op.drop_index(_UPDATED_AT_IDX, table_name=_TABLE)
    op.drop_table(_TABLE)
