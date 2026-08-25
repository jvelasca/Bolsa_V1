"""P1 — ``position_states`` (ADR-033) + snapshot TradePlan en pending_orders.

Idempotente: omite tabla/columna/índices si ya existen.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "011_position_states"
down_revision = "010_decision_journal_entries"
branch_labels = None
depends_on = None

_TABLE = "position_states"
_PENDING = "pending_orders"
_SNAPSHOT_COL = "trade_plan_snapshot"


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


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, _PENDING, _SNAPSHOT_COL) and _table_exists(bind, _PENDING):
        op.add_column(
            _PENDING,
            sa.Column(_SNAPSHOT_COL, postgresql.JSONB(), nullable=True),
        )

    if _table_exists(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(),
            sa.ForeignKey("investment_accounts.id"),
            nullable=False,
        ),
        sa.Column(
            "instrument_id",
            sa.String(),
            sa.ForeignKey("instruments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ledger_position_id",
            sa.String(),
            sa.ForeignKey("positions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "open_transaction_id",
            sa.String(),
            sa.ForeignKey("transactions.id"),
            nullable=False,
        ),
        sa.Column("trade_plan_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("trade_plan_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("position_state", postgresql.JSONB(), nullable=False),
        sa.Column("birth_override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "open_transaction_id",
            name="position_states_open_transaction_id_key",
        ),
    )
    op.create_index(
        "position_states_account_instrument_open_uidx",
        _TABLE,
        ["account_id", "instrument_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'CLOSED'"),
    )
    op.create_index(
        "position_states_account_created_idx",
        _TABLE,
        ["account_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        if _index_exists(bind, "position_states_account_created_idx"):
            op.drop_index("position_states_account_created_idx", table_name=_TABLE)
        if _index_exists(bind, "position_states_account_instrument_open_uidx"):
            op.drop_index(
                "position_states_account_instrument_open_uidx",
                table_name=_TABLE,
            )
        op.drop_table(_TABLE)
    if _column_exists(bind, _PENDING, _SNAPSHOT_COL):
        op.drop_column(_PENDING, _SNAPSHOT_COL)
