"""V2.32 / A12 — atribución de estrategia que sobrevive a crash/readopt.

V2.28 atribuyó los fills SIM a la versión de estrategia en ``sim_fill_finance_context``,
pero esa atribución se perdía al reiniciar: ``AutoSimulationWorker._position_version``
vive en RAM y ``readopt_positions`` restauraba cantidad/entrada/high-watermark, no la
versión. Los cierres de posiciones readoptadas quedaban con ``strategy_version_id=NULL``
y la serie observada de la versión aparecía truncada (compras sin ventas).

Esta migración añade la atribución durable a las dos superficies que faltaban:

* ``sim_auto_positions.strategy_version_id``: la proyección durable que ``readopt``
  lee; al restaurarla, los cierres posteriores vuelven a atribuirse.
* ``ledger_entries.strategy_version_id``: la serie contable primaria, para que la
  vigilancia no dependa en exclusiva de ``sim_fill_finance_context``.

Ambas columnas son NULLABLE y sin backfill: la ausencia de atribución es información,
no un dato falso. Guards idempotentes offline-safe (patrón 030/031/032).

Cadena lineal: ``down_revision = "032_shadow_validation"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "033_position_strategy_attr"
down_revision = "032_shadow_validation"
branch_labels = None
depends_on = None

_COLUMN = "strategy_version_id"
_TARGETS: tuple[tuple[str, str | None], ...] = (
    ("sim_auto_positions", "sim_auto_positions_strategy_idx"),
    ("ledger_entries", "ledger_entries_strategy_idx"),
)


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
    for table, index_name in _TARGETS:
        if not _table_exists(bind, table):
            continue
        if not _column_exists(bind, table, _COLUMN):
            op.add_column(table, sa.Column(_COLUMN, sa.String(), nullable=True))
        if index_name and not _index_exists(bind, index_name):
            op.create_index(index_name, table, [_COLUMN])


def downgrade() -> None:
    bind = op.get_bind()
    for table, index_name in _TARGETS:
        if not _table_exists(bind, table):
            continue
        if index_name and _index_exists(bind, index_name):
            op.drop_index(index_name, table_name=table)
        if _column_exists(bind, table, _COLUMN):
            op.drop_column(table, _COLUMN)
