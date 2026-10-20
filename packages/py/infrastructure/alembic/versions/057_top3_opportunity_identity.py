"""057 — ``top3_opportunities``: identidad de la estrategia ganadora del slot.

La foto durable del TOP3 guardaba ``asset_id``, ``combined``, ``components``, ``regime``
y ``reasons``, pero **no** la identidad de la estrategia que produjo el candidato. Por eso
el lector de la cadena no podía comparar el preset ejecutado contra el mejor puntuado y
declaraba el hueco (``bestScoredPresetKey = None``).

Esta migración añade dos columnas **aditivas y nullable** —``strategy_preset_key`` y
``strategy_version``— que la señal ya transporta (``V2Signal``) y que ahora viajan por el
ranking hasta la fila. Sin backfill: las fotos anteriores a esta revisión quedan ``NULL``
y se leen como identidad DESCONOCIDA (la UI lo declara). Nunca se infiere del ticker ni
del rank.

Aditiva e idempotente (comprueba existencia de la tabla y de cada columna antes de
alterar); ``downgrade`` simétrico (elimina solo lo que esta revisión añadió).

Cadena lineal: ``down_revision = "056_auto_ops_jobs"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "057_top3_opportunity_identity"
down_revision = "056_auto_ops_jobs"
branch_labels = None
depends_on = None

_TABLE = "top3_opportunities"
#: Columnas de identidad ADITIVAS. Nullable, sin índice y sin default: el hueco es el
#: estado histórico legítimo y un default afirmaría una identidad que nadie declaró.
_IDENTITY_COLUMNS = ("strategy_preset_key", "strategy_version")


def _table_exists(bind: sa.engine.Connection) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE}) is not None


def _column_exists(bind: sa.engine.Connection, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE, "c": column}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        # La tabla la crea la 052; sin ella no hay nada que ampliar (cadena incompleta).
        return
    for column in _IDENTITY_COLUMNS:
        if _column_exists(bind, column):
            continue
        op.add_column(_TABLE, sa.Column(column, sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    for column in _IDENTITY_COLUMNS:
        if not _column_exists(bind, column):
            continue
        op.drop_column(_TABLE, column)
