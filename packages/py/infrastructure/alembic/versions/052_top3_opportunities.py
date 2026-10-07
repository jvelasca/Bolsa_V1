"""AUTO v2.88 — TOP3 de oportunidades (activos) cross-asset.

Instantánea durable de «qué 3 activos decidió AUTO y por qué»: una fila por slot del
TOP3 (``rank``), con su score combinado, sus componentes explicables (``components``),
el régimen de mercado con el que se computó (``regime``) y los motivos (``reasons``).

A DIFERENCIA de ``instrument_strategy_tops`` (per-instrumento, FK ``instruments.id`` y
clave natural ``(instrument_id, timeframe)`` reconciliada en la migración 041), ésta es
**cross-asset**: no reutiliza ni repurposea esa tabla — cada ``run_id`` es una foto del
universo decidido, y ``asset_id`` es un identificador de activo (puede no ser una FK a
``instruments``; el TOP3 cruza activos y no está subordinado a un instrumento).

Cadena lineal: ``down_revision = "051_auto_engine_activity"``.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "052_top3_opportunities"
down_revision = "051_auto_engine_activity"
branch_labels = None
depends_on = None

_TABLE = "top3_opportunities"


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
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("combined", sa.Float(), nullable=False),
        sa.Column("components", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("regime", sa.String(), nullable=True),
        sa.Column("reasons", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("top3_opportunities_run_id_idx", _TABLE, ["run_id"])
    op.create_index("top3_opportunities_run_rank_idx", _TABLE, ["run_id", "rank"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    op.drop_index("top3_opportunities_run_rank_idx", table_name=_TABLE)
    op.drop_index("top3_opportunities_run_id_idx", table_name=_TABLE)
    op.drop_table(_TABLE)
