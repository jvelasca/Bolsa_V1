"""``workspaces.user_id`` (R12-AUTH F8d) — scope workspaces por owner JWT.

Columna nullable: filas legacy ``user_id IS NULL`` visibles solo al principal
bootstrap (F7a). Idempotente: omite si la columna ya existe.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "009_workspaces_user_id"
down_revision = "008_users_session_version"
branch_labels = None
depends_on = None

_TABLE = "workspaces"
_COLUMN = "user_id"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table, "c": column}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE) or _column_exists(bind, _TABLE, _COLUMN):
        return
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.String(), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE) and _column_exists(bind, _TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
