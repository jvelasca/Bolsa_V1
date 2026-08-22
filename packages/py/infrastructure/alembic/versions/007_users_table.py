"""Tabla ``users`` (R12-AUTH F5 / ADR-027 C.1) — identidad mínima multi-user.

Columnas: ``id`` (PK, alineado con ``APP_OWNER_ID`` en bootstrap), ``login`` único,
``password_hash`` (bcrypt), ``role`` opcional, ``created_at``, ``disabled_at``.

Idempotente: si la tabla ya existe, no se re-crea. El seed del admin bootstrap
se ejecuta en ``user_bootstrap.ensure_bootstrap_user`` al arranque (no aquí).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "007_users_table"
down_revision = "006_custody_obligations_period"
branch_labels = None
depends_on = None

_TABLE_NAME = "users"
_LOGIN_UNIQUE = "uq_users_login"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE_NAME):
        return
    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("login", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("login", name=_LOGIN_UNIQUE),
    )


def downgrade() -> None:
    op.drop_table(_TABLE_NAME)
