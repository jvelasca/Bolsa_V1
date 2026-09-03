"""V1.92 — lifecycle_outbox index for FIFO claim by position_id."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "019_outbox_position_fifo"
down_revision = "018_lifecycle_outbox_worker"
branch_labels = None
depends_on = None

_TABLE = "lifecycle_outbox"
_POS_CREATED_IDX = "lifecycle_outbox_position_created_idx"


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _index_exists(bind, _POS_CREATED_IDX):
        op.create_index(
            _POS_CREATED_IDX,
            _TABLE,
            ["position_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, _POS_CREATED_IDX):
        op.drop_index(_POS_CREATED_IDX, table_name=_TABLE)
