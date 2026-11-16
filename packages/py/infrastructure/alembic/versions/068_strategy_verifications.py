"""068 — índice durable de la verificación periódica de estrategia (ADR-050).

Qué añade
---------
``strategy_verification_runs``: una fila por run de verificación (época o ventana móvil), con
el perfil pre-registrado que lo produjo y el veredicto advisory. El artefacto JSON sigue siendo
la fuente de verdad de la medición; esta tabla es el índice consultable y el candado de
identidad.

Por qué ``measurement_hash`` y no el ``hash`` del artefacto
----------------------------------------------------------
El hash del artefacto incluye ``meta.generatedAt``: dos rejuegos idénticos producen hashes
distintos y no se podría demostrar que la medición es la misma. ``measurement_hash`` se calcula
solo sobre la medición (barras, patas, brazos y versión), así que es reproducible.

Unicidad
--------
``(account_id, profile_id, kind, day, to_day)``: la misma época con el mismo perfil no se
cuenta dos veces. ``kind`` separa ``epoch`` (decide) de ``rolling`` (solo historial), de modo
que la ventana móvil no puede colarse en el veredicto por la puerta de la base de datos.

``downgrade`` elimina la tabla: es un índice reconstruible desde los artefactos.

Cadena lineal: ``down_revision = "067_opinion_account_scope"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "068_strategy_verifications"
down_revision = "067_opinion_account_scope"
branch_labels = None
depends_on = None

_TABLE = "strategy_verification_runs"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("profile_hash", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("to_day", sa.Date(), nullable=False),
        sa.Column("measurement_hash", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("strategy_version", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["investment_accounts.id"],
            name="strategy_verification_runs_account_fkey",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "account_id",
            "profile_id",
            "kind",
            "day",
            "to_day",
            name="strategy_verification_runs_natural_key",
        ),
    )
    op.create_index(
        "strategy_verification_runs_account_day_idx",
        _TABLE,
        ["account_id", "profile_id", "day"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    op.drop_index("strategy_verification_runs_account_day_idx", table_name=_TABLE)
    op.drop_table(_TABLE)
