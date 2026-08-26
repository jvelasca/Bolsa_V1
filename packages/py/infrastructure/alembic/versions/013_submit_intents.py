"""DEX-1 — ``submit_intents`` (ADR-035 OR-2 físico / V1.13).

Persistencia durable del intento de envío Confirm antes de ``adapter.submit``.
Idempotente: omite tabla/índices si ya existen.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "013_submit_intents"
down_revision = "012_position_state_hot_columns"
branch_labels = None
depends_on = None

_TABLE = "submit_intents"


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
        sa.Column("decision_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("venue", sa.String(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("venue_order_id", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("send_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("decision_id", name="submit_intents_decision_id_key"),
        sa.UniqueConstraint("intent_id", name="submit_intents_intent_id_key"),
        sa.UniqueConstraint("order_id", name="submit_intents_order_id_key"),
    )
    op.create_index(
        "submit_intents_account_id_idx",
        _TABLE,
        ["account_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if _index_exists(bind, "submit_intents_account_id_idx"):
        op.drop_index("submit_intents_account_id_idx", table_name=_TABLE)
    op.drop_table(_TABLE)
