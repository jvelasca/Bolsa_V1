"""V2.32 / A12 — evidencia shadow ejecutada (autoridad del Promotion Gate).

Hasta V2.31 el Promotion Gate aceptaba ``AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1`` como
sustituto de validación shadow/paper: el sistema **nunca ejecutaba** nada, solo leía un
booleano humano. Esta migración introduce la tabla de evidencia real:

* ``strategy_shadow_validations``: una fila por replay ejecutado de un finalista, con
  métricas contables (trades, retorno, drawdown, win-rate) y el veredicto
  ``passed``/``reasons``. Es la prueba que el Promotion Gate consulta.
* ``strategy_promotions.shadow_validation_id``: enlace auditable de la promoción a la
  evidencia concreta que la autorizó (nullable: las promociones previas no tenían
  evidencia; no se inventa).

Aditivo y nullable. Sin backfill: la ausencia de evidencia es información, no un dato
falso. Guards idempotentes offline-safe (patrón 030/031).

Cadena lineal: ``down_revision = "031_sim_fill_strategy_attr"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "032_shadow_validation"
down_revision = "031_sim_fill_strategy_attr"
branch_labels = None
depends_on = None

_TABLE = "strategy_shadow_validations"
_INDEX = "strategy_shadow_validations_version_idx"
_PROMOTIONS = "strategy_promotions"
_PROMO_COLUMN = "shadow_validation_id"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "c": column_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, _TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("version_id", sa.String(), nullable=False),
            sa.Column("instrument_id", sa.String(), nullable=True),
            sa.Column("trades", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("return_pct", sa.Float(), nullable=True),
            sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
            sa.Column("win_rate", sa.Float(), nullable=True),
            sa.Column("bars_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("as_of", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(_INDEX, _TABLE, ["version_id", "created_at"])

    if _table_exists(bind, _PROMOTIONS) and not _column_exists(
        bind, _PROMOTIONS, _PROMO_COLUMN
    ):
        op.add_column(
            _PROMOTIONS,
            sa.Column(_PROMO_COLUMN, sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, _PROMOTIONS) and _column_exists(
        bind, _PROMOTIONS, _PROMO_COLUMN
    ):
        op.drop_column(_PROMOTIONS, _PROMO_COLUMN)

    if _table_exists(bind, _TABLE):
        if _index_exists(bind, _INDEX):
            op.drop_index(_INDEX, table_name=_TABLE)
        op.drop_table(_TABLE)
