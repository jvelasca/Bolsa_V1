"""V2.33 / A13 — evidencia *forward* de la estrategia ACTIVE (paper forward).

V2.32/A12 cerró la validación *histórica* (shadow sobre un hold-out del LAB), pero nada
medía cómo se comporta la ACTIVE con **mercado nuevo posterior a la promoción**. Esta
migración introduce la tabla de evidencia forward:

* ``paper_forward_results``: una fila por forward ejecutado de una ACTIVE, con métricas
  contables (trades, round-trips, fills, retorno, drawdown, win-rate), veredicto
  ``passed``/``reasons``, vetos de los gates, y el fingerprint reproducible del dataset
  forward (``forward_start``/``forward_end``/``bars_hash``/``strategy_definition_hash``/
  ``engine_version``/``config_hash``/``data_snapshot_id``) más la barrera temporal
  ``promoted_at`` (solo cuentan barras posteriores a la promoción).

Aditivo: tabla nueva, sin tocar tablas previas y sin backfill (no había evidencia
forward antes; no se inventa). Guards idempotentes offline-safe (patrón 030/031/032/034).

Cadena lineal: ``down_revision = "034_shadow_dataset_fingerprint"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "035_paper_forward_evidence"
down_revision = "034_shadow_dataset_fingerprint"
branch_labels = None
depends_on = None

_TABLE = "paper_forward_results"
_INDEX = "paper_forward_results_version_idx"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("instrument_id", sa.String(), nullable=True),
        sa.Column("trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("round_trips", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fills", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("return_pct", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("bars_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("vetoes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("as_of", sa.String(), nullable=True),
        # Identidad reproducible del dataset forward.
        sa.Column("data_snapshot_id", sa.String(), nullable=True),
        sa.Column("forward_start", sa.String(), nullable=True),
        sa.Column("forward_end", sa.String(), nullable=True),
        sa.Column("bars_hash", sa.String(), nullable=True),
        sa.Column("strategy_definition_hash", sa.String(), nullable=True),
        sa.Column("engine_version", sa.String(), nullable=True),
        sa.Column("config_hash", sa.String(), nullable=True),
        sa.Column("promoted_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(_INDEX, _TABLE, ["version_id", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if _index_exists(bind, _INDEX):
        op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
