"""V1.86 — ``lifecycle_events`` append-only event store.

Idempotente: omite tabla/índices si ya existen.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "015_lifecycle_events"
down_revision = "014_operational_incidents"
branch_labels = None
depends_on = None

_TABLE = "lifecycle_events"
_FILL_UIDX = "lifecycle_events_fill_id_uidx"
_POS_IDX = "lifecycle_events_position_at_idx"
_ACC_IDX = "lifecycle_events_account_id_idx"


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
    if _table_exists(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("position_id", sa.String(), nullable=False),
        sa.Column("instrument_id", sa.String(), nullable=False),
        sa.Column("decision_id", sa.String(), nullable=False),
        sa.Column("trade_plan_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False, server_default="LONG"),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fill_id", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("fees", sa.Numeric(18, 6), nullable=True),
        sa.Column("venue", sa.String(), nullable=True),
        sa.Column("venue_order_id", sa.String(), nullable=True),
        sa.Column("previous_stop", sa.Numeric(18, 6), nullable=True),
        sa.Column("new_stop", sa.Numeric(18, 6), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("revision_id", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("causation_id", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", name="lifecycle_events_event_id_key"),
    )
    op.create_index(_ACC_IDX, _TABLE, ["account_id"])
    op.create_index(_POS_IDX, _TABLE, ["position_id", "at"])
    op.create_index(
        _FILL_UIDX,
        _TABLE,
        ["fill_id"],
        unique=True,
        postgresql_where=sa.text("fill_id IS NOT NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    for name in (_FILL_UIDX, _POS_IDX, _ACC_IDX):
        if _index_exists(bind, name):
            op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
