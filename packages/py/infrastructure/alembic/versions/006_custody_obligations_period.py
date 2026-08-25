"""Tabla ``custody_obligations`` (R-11 C1 / R-10.6) — obligaciones de custodia MULTI-periodo.

Reemplaza la tabla ``custody_obligation`` (005, ADR 026 / F4a) como fuente de
verdad de la deuda de custodia. La 005 tenía PK ``account_id`` (una fila por
cuenta): el ``upsert`` sobrescribía ``period/status/outstanding/total_fee``, de
modo que si una cuenta quedaba ``cash<fee`` en 2026 (PENDING) y al llegar 2027
seguía sin saldo, el upsert del nuevo periodo PISABA la fila y se perdía la deuda
de 2026. Esta tabla usa PK ``id`` autoincremental + ``UNIQUE(account_id, period)``
para representar UNA obligación por (cuenta, año) sin sobrescribir los pendientes
históricos.

La tabla ``custody_obligation`` (005) queda **OBSOLETA y no debe usarse**: la
fuente de verdad pasa a ``custody_obligations``. NO se borra en ``upgrade`` para
mantener forward-only (D6) y evitar destruir datos; ``downgrade`` aísla la nueva.

Idempotente (mismo patrón que ``004``/``005``): si la tabla ya existe, no se
re-crea. Migra las filas existentes de la 005 preservando
``period/status/outstanding/total_fee``, de modo que los PENDING actuales no se
pierden.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006_custody_obligations_period"
down_revision = "005_custody_obligation"
branch_labels = None
depends_on = None

_TABLE_NAME = "custody_obligations"
_LEGACY_TABLE_NAME = "custody_obligation"
_UNIQUE_NAME = "uq_custody_obligations_account_period"


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
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "account_id",
            sa.String(),
            sa.ForeignKey("investment_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("outstanding", sa.Numeric(18, 6), nullable=False),
        sa.Column("total_fee", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_id", "period", name=_UNIQUE_NAME),
    )
    # Migra las filas de la antigua tabla (una por cuenta, PENDING/APPLIED del
    # periodo que fuera en curso) preservando su deuda — no se pierden pendientes.
    # ``_LEGACY_TABLE_NAME`` nació con PK ``account_id``, así que no hay colisión
    # de ``(account_id, period)``: se copia intacto el periodo de cada fila.
    if _table_exists(bind, _LEGACY_TABLE_NAME):
        op.execute(
            sa.text(
                f"INSERT INTO {_TABLE_NAME} "
                "(account_id, period, status, outstanding, total_fee) "
                "SELECT account_id, period, status, outstanding, total_fee "
                f"FROM {_LEGACY_TABLE_NAME}"
            )
        )


def downgrade() -> None:
    op.drop_table(_TABLE_NAME)
