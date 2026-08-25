"""Tabla ``custody_obligation`` (ADR 026 / F4a) — obligación de custodia por cuenta.

Elimina la **custodia parcial silenciosa**: una fila por cuenta (PK ``account_id``
FK → ``investment_accounts.id``, ``ondelete=CASCADE``) registra la obligación de
custodia pendiente/aplicada del periodo en curso. ``status`` solo ``PENDING`` |
``APPLIED``; ``outstanding`` = importe pendiente; ``total_fee`` = importe total
original. ``period`` es ``"YYYY"``.

Forward-only (D6): la tabla nace **sin backfill**. No se re-cobra ni se crean
PENDING retroactivos para periodos ya liquidados como ``custody-YYYY``/``fee`` en
v1.2.0. La corrección aplica desde el próximo periodo nuevo.

Idempotente (mismo patrón que ``004``): si la tabla ya existe, no se re-crea.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005_custody_obligation"
down_revision = "004_ledger_reference_unique"
branch_labels = None
depends_on = None

_TABLE_NAME = "custody_obligation"


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
        sa.Column(
            "account_id",
            sa.String(),
            sa.ForeignKey("investment_accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("outstanding", sa.Numeric(18, 6), nullable=False),
        sa.Column("total_fee", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table(_TABLE_NAME)
