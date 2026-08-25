"""data_epoch: marca de época/legacy en research_runs/trials (F3b).

Fecha el ``--mark-legacy`` de scripts/research (antes no-op): columnas para
etiquetar los backtest_runs/research_trials producidos antes de la corrección
``next_open`` (F2) como ``legacy`` y los recalaculados bajo la nueva data/engine
como ``next_open``. Permite identificar y, en su caso, descartar resultados
científicos de época anterior sin depender solo del manifest JSON.

Autoridad: Alembic (D2). Esta es la primera migración de DDL real de este repo
(Alembic era un stub con solo la extensión TimescaleDB). ``backtest_runs`` y
``research_trials`` ya existían vía Prisma: aquí solo se añaden columnas.

Guards de idempotencia (D2/F3a): esta migración puede ejecutarse sobre una BD
**limpia** (construida de cero por Alembic) en la que ``003_prisma_schema_baseline``
aún no ha corrido y las tablas objetivo NO existen, o en la que la columna ya fue
creada por el propio baseline. Por eso cada ``add_column`` se guarda: si la tabla
no existe o la columna ya está, se omite. Sobre la BD de Prisma (ya migrada) esta
migración está históricamente aplicada y no se re-ejecuta.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002_research_data_epoch"
down_revision = "001_timescaledb_extension"
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    sql = "SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"
    return bind.scalar(sa.text(sql), {"t": table, "c": column}) is not None


def _table_exists(bind, table: str) -> bool:
    sql = "SELECT 1 FROM information_schema.columns WHERE table_name = :t"
    return bind.scalar(sa.text(sql), {"t": table}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    # Si no existe la tabla aún, es una BD limpia donde el baseline (003) creará
    # la columna junto a la tabla: omitimos y dejamos que 003 la provea.
    if _table_exists(bind, "backtest_runs") and not _column_exists(
        bind, "backtest_runs", "data_epoch"
    ):
        op.add_column("backtest_runs", sa.Column("data_epoch", sa.Text(), nullable=True))
    if _table_exists(bind, "research_trials") and not _column_exists(
        bind, "research_trials", "data_epoch"
    ):
        op.add_column("research_trials", sa.Column("data_epoch", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("research_trials", "data_epoch")
    op.drop_column("backtest_runs", "data_epoch")
