"""``users.session_version`` (R12-AUTH F10) — revocación JWT por usuario.

Incrementar ``session_version`` invalida todos los JWT emitidos con un ``sv``
anterior (logout-all, cambio de contraseña). Idempotente: omite si la columna
ya existe.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "008_users_session_version"
down_revision = "007_users_table"
branch_labels = None
depends_on = None

_TABLE = "users"
_COLUMN = "session_version"


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
        sa.Column(
            _COLUMN,
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE) and _column_exists(bind, _TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
