"""V1.91 — lifecycle_outbox claim/backoff columns (processing + next_attempt_at)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "018_lifecycle_outbox_worker"
down_revision = "017_lifecycle_outbox"
branch_labels = None
depends_on = None

_TABLE = "lifecycle_outbox"
_STATUS_NEXT_IDX = "lifecycle_outbox_status_next_attempt_idx"


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table, "c": column}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, _TABLE, "next_attempt_at"):
        op.add_column(
            _TABLE,
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists(bind, _TABLE, "claimed_at"):
        op.add_column(
            _TABLE,
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _index_exists(bind, _STATUS_NEXT_IDX):
        op.create_index(
            _STATUS_NEXT_IDX,
            _TABLE,
            ["status", "next_attempt_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, _STATUS_NEXT_IDX):
        op.drop_index(_STATUS_NEXT_IDX, table_name=_TABLE)
    if _column_exists(bind, _TABLE, "claimed_at"):
        op.drop_column(_TABLE, "claimed_at")
    if _column_exists(bind, _TABLE, "next_attempt_at"):
        op.drop_column(_TABLE, "next_attempt_at")
