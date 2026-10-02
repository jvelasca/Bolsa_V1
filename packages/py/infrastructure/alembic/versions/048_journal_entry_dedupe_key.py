"""AUTO v2.88.27 — identidad determinista de los hechos durables del spine.

La ventana que cierra. Los hechos M2 (``auto_entry_order``, ``auto_cycle_settlement``,
``auto_protection_event``) se sellaban en ``decision_journal_entries`` con una PK aleatoria
(``JNL-<uuid4>``) y **sin** identidad natural. Un reintento o un rearranque del sumidero de
auditoría —o la recuperación de un ``SETTLEMENT`` que un crash dejó sin publicar— volvía a
insertar el MISMO hecho: la cadena durable se duplicaba y el monitor contaba dos liquidaciones
donde hubo una.

Qué crea:

1. ``decision_journal_entries.dedupe_key`` — ``String(160)`` **nullable**, sin ``server_default``.
   Es la identidad determinista que el productor puede DEMOSTRAR (p. ej.
   ``auto_cycle_settlement:{account}:{engine}:{cycle_id}``). ``NULL`` significa "este hecho no
   declara identidad natural" (todo el histórico anterior a 2.88.27 y el resto de productores):
   no se rellena con un literal inventado.
2. ``uq_decision_journal_entries_dedupe_key`` — índice único **PARCIAL**
   (``WHERE dedupe_key IS NOT NULL``). Es lo que hace del ``append`` un
   ``INSERT ... ON CONFLICT DO NOTHING`` real: los ``NULL`` no colisionan entre sí, así que
   ningún hecho sin identidad (ni una fila histórica) cambia de comportamiento.

Aditiva y **sin backfill**. ``upgrade`` y ``downgrade`` son idempotentes (patrón 028–047) y la
cadena es lineal (``down_revision = "047_fill_price_source"``).

.. warning::

   **DESTRUCTIVE DATA DOWNGRADE — simetría de esquema ≠ reversibilidad de datos.** El ``downgrade``
   deja el esquema EXACTAMENTE como estaba (dropea el índice y la misma columna que creó el
   ``upgrade``), pero los datos no vuelven: las identidades que los productores declararon
   mientras la ``048`` estuvo aplicada se PIERDEN. No hay backfill (la identidad no se puede
   reconstruir desde la fila).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "048_journal_entry_dedupe_key"
down_revision = "047_fill_price_source"
branch_labels = None
depends_on = None

_TABLE = "decision_journal_entries"
_COLUMN = "dedupe_key"
_INDEX = "uq_decision_journal_entries_dedupe_key"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
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
        return
    if not _column_exists(bind, _TABLE, _COLUMN):
        # Nullable y sin server_default: "sin identidad natural" es un HECHO declarado, y
        # rellenarla convertiría el hueco en una identidad afirmada.
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(160), nullable=True))
    if not _index_exists(bind, _INDEX):
        # Único PARCIAL: los ``NULL`` no colisionan (no reescribe ni bloquea el histórico).
        op.create_index(
            _INDEX,
            _TABLE,
            [_COLUMN],
            unique=True,
            postgresql_where=sa.text(f"{_COLUMN} IS NOT NULL"),
        )


def downgrade() -> None:
    """Retira exactamente lo que creó el upgrade: el índice parcial y la columna.

    Simétrico por construcción e idempotente. **DESTRUCTIVE DATA DOWNGRADE (declarado):** dropear
    la columna borra para siempre las identidades deterministas que los productores declararon;
    no existe backfill.
    """
    bind = op.get_bind()

    if _index_exists(bind, _INDEX):
        op.drop_index(_INDEX, table_name=_TABLE)
    if _table_exists(bind, _TABLE) and _column_exists(bind, _TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
