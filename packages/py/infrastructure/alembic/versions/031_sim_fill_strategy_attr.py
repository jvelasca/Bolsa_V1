"""V2.28 / A10 (P1-02 real) — atribución de fills SIM a la versión de estrategia ACTIVE.

Cierra el bloqueo estructural que impedía la *vigilancia real*: el ``version_id`` de
la estrategia ACTIVE solo existía como string en memoria (``DecisionPackage.source``
= ``active-strategy:<version_id>``) y el worker SIM lo descartaba, de modo que ningún
fill/posición/ledger podía atribuirse a una versión concreta. Sin atribución, cualquier
métrica de salud sería de la *cuenta*, no de la *estrategia*.

Aquí se añade ``strategy_version_id`` (nullable) a ``sim_fill_finance_context``: la fila
durable por ``execution_id`` que ya se escribe ANTES de mover dinero. Es un cambio
estrictamente aditivo:

* La columna es NULLABLE: los fills previos a esta migración (y los que no provengan de
  una estrategia, p. ej. el spine determinista sin ACTIVE) quedan en ``NULL`` — no se
  inventa atribución.
* NO se altera la identidad de ejecución (``execution_id``/``venue_order_id``), ni la PK,
  ni la semántica de settlement. Solo se añade el dato de procedencia.
* Índice ``(strategy_version_id, created_at)`` para reconstruir la serie temporal de
  fills de una versión (métricas observadas de la vigilancia).

Convenciones: ``String`` (sin ENUM DDL), guards idempotentes ``_table_exists``/
``_column_exists``/``_index_exists`` (offline-safe).

Cadena lineal: ``down_revision = "030_strategy_lifecycle"``.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "031_sim_fill_strategy_attr"
down_revision = "030_strategy_lifecycle"
branch_labels = None
depends_on = None

_FIN_CTX = "sim_fill_finance_context"
_COLUMN = "strategy_version_id"
_INDEX = "sim_fill_finance_context_strategy_created_idx"


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
    if not _table_exists(bind, _FIN_CTX):
        return

    if not _column_exists(bind, _FIN_CTX, _COLUMN):
        # Nullable a propósito: la ausencia de atribución es información, no un error.
        op.add_column(
            _FIN_CTX,
            sa.Column(_COLUMN, sa.String(), nullable=True),
        )

    if not _index_exists(bind, _INDEX):
        op.create_index(
            _INDEX,
            _FIN_CTX,
            [_COLUMN, "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _FIN_CTX):
        return

    if _index_exists(bind, _INDEX):
        op.drop_index(_INDEX, table_name=_FIN_CTX)
    if _column_exists(bind, _FIN_CTX, _COLUMN):
        op.drop_column(_FIN_CTX, _COLUMN)
