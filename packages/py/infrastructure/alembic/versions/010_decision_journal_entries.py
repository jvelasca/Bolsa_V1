"""``decision_journal_entries`` (ADR-029 F1) — audit trail append-only del spine.

Idempotente: omite si la tabla ya existe.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "010_decision_journal_entries"
down_revision = "009_workspaces_user_id"
branch_labels = None
depends_on = None

_TABLE = "decision_journal_entries"
_SESSIONS = "decision_sessions"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("decision_id", sa.String(), nullable=False),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey(f"{_SESSIONS}.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("account_id", sa.String(), nullable=True),
        sa.Column("instrument_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "decision_journal_entries_account_created_idx",
        _TABLE,
        ["account_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "decision_journal_entries_decision_id_idx",
        _TABLE,
        ["decision_id"],
    )
    op.create_index(
        "decision_journal_entries_session_id_idx",
        _TABLE,
        ["session_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    op.drop_index("decision_journal_entries_session_id_idx", table_name=_TABLE)
    op.drop_index("decision_journal_entries_decision_id_idx", table_name=_TABLE)
    op.drop_index("decision_journal_entries_account_created_idx", table_name=_TABLE)
    op.drop_table(_TABLE)
