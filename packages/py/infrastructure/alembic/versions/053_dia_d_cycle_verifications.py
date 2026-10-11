"""P2 — Verificación DÍA-D ENLAZADA a un ciclo AUTO (``dia_d_cycle_verifications``).

Registro durable de que la verificación D→hoy del sandbox LAB se lanzó DESDE un
ciclo AUTO concreto, con la identidad EXACTA de estrategia que declara el ciclo
(``strategy_preset_key`` / ``strategy_version`` / ``strategy_definition_id``) y el
resultado declarado (``band`` + ``result`` JSONB).

Aditiva y ``nullable`` a propósito: un ciclo histórico no declara su estrategia y se
persiste el hueco («Sin dato todavía»), sin backfill forzado.

Cadena lineal: ``down_revision = "052_top3_opportunities"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "053_dia_d_cycle_verifications"
down_revision = "052_top3_opportunities"
branch_labels = None
depends_on = None

_TABLE = "dia_d_cycle_verifications"


def _table_exists(bind: sa.engine.Connection) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("cycle_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=True),
        sa.Column("instrument_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("strategy_preset_key", sa.String(), nullable=True),
        sa.Column("strategy_version", sa.String(), nullable=True),
        sa.Column("strategy_definition_id", sa.String(), nullable=True),
        sa.Column("dia_d", sa.String(), nullable=False),
        sa.Column("end_date", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("band", sa.String(), nullable=True),
        sa.Column(
            "result",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("research_evidence_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "cycle_id",
            "dia_d",
            "end_date",
            "mode",
            name="dia_d_cycle_verifications_cycle_key",
        ),
    )
    op.create_index(
        "dia_d_cycle_verifications_cycle_id_idx", _TABLE, ["cycle_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    op.drop_index("dia_d_cycle_verifications_cycle_id_idx", table_name=_TABLE)
    op.drop_table(_TABLE)
