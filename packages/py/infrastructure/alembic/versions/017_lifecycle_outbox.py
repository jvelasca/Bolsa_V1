"""V1.90 — lifecycle_outbox durable pending appends (fail-soft without loss)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "017_lifecycle_outbox"
down_revision = "016_lifecycle_sequence"
branch_labels = None
depends_on = None

_TABLE = "lifecycle_outbox"
_TX_UIDX = "lifecycle_outbox_transaction_id_uidx"
_STATUS_IDX = "lifecycle_outbox_status_idx"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("position_id", sa.String(), nullable=False),
            sa.Column("account_id", sa.String(), nullable=False),
            sa.Column("transaction_id", sa.String(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column(
                "status",
                sa.String(),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not _index_exists(bind, _TX_UIDX):
        op.create_index(
            _TX_UIDX,
            _TABLE,
            ["transaction_id"],
            unique=True,
        )
    if not _index_exists(bind, _STATUS_IDX):
        op.create_index(_STATUS_IDX, _TABLE, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, _STATUS_IDX):
        op.drop_index(_STATUS_IDX, table_name=_TABLE)
    if _index_exists(bind, _TX_UIDX):
        op.drop_index(_TX_UIDX, table_name=_TABLE)
    if _table_exists(bind, _TABLE):
        op.drop_table(_TABLE)
