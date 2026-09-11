"""V2.39 (incremento 4) — regimen de mercado por trial.

La evidencia adaptativa de V2.36-V2.38 se agrega por **familia** (``preset_key``) y, desde
V2.38, por **region de parametros** (``familia|region``). El incremento 4 anade la segunda
dimension de granularidad: el **regimen de mercado** bajo el que se evaluo cada trial,
clasificado de forma determinista y versionada (``discovery_market_regime_v0``) a partir de
las **barras del propio trial** (as-of, en el punto del LAB que las tiene).

Por que un regimen DERIVADO DE BARRAS y no el regimen macro cognitivo: ``market_state`` se
alimenta de un feed macro *live* de Yahoo (``date.today()``, ``closes[-1]``) que no persiste
serie historica, por lo que NO es calculable as-of; etiquetar un trial pasado con el regimen
de hoy seria inventar dato. Ver docstring de ``bolsa_application.discovery_market_regime``.

Aditivo: una columna nullable ``regime`` en ``research_trials``, sin backfill (los trials
historicos quedan a ``NULL``: no se inventa el regimen de corridas pasadas, y la agregacion
sin regimen sigue siendo exactamente la de antes). Guards idempotentes offline-safe
(patron 030-038).

Cadena lineal: ``down_revision = "038_research_trials_param_region"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "039_research_trials_regime"
down_revision = "038_research_trials_param_region"
branch_labels = None
depends_on = None

_TABLE = "research_trials"
_COLUMN = "regime"


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "c": column_name}) is not None


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if _column_exists(bind, _TABLE, _COLUMN):
        return
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if not _column_exists(bind, _TABLE, _COLUMN):
        return
    op.drop_column(_TABLE, _COLUMN)
