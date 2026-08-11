"""data_epoch: marca de época/legacy en research_runs/trials (F3b).

Fecha el ``--mark-legacy`` de scripts/research (antes no-op): columnas para
etiquetar los backtest_runs/research_trials producidos antes de la corrección
``next_open`` (F2) como ``legacy`` y los recalaculados bajo la nueva data/engine
como ``next_open``. Permite identificar y, en su caso, descartar resultados
científicos de época anterior sin depender solo del manifest JSON.

Autoridad: Alembic (D2). Esta es la primera migración de DDL real de este repo
(Alembic era un stub con solo la extensión TimescaleDB). ``backtest_runs`` y
``research_trials`` ya existían vía Prisma: aquí solo se añaden columnas.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002_research_data_epoch"
down_revision = "001_timescaledb_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backtest_runs", sa.Column("data_epoch", sa.Text(), nullable=True))
    op.add_column("research_trials", sa.Column("data_epoch", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("research_trials", "data_epoch")
    op.drop_column("backtest_runs", "data_epoch")
