"""AUTO v2.88.25 — la FUENTE de precio que construyó el precio de un fill.

La ventana que cierra. El header del monitor declaraba ``realPriceEnabled``, que es la
**configuración** (``AUTO_ENGINE_SIM_REAL_PRICE``), NO la fuente que de verdad se usó en una
operación. Una operación podía sellarse con el ``100.0`` hermético mientras la configuración decía
ON, y ese hueco no tenía dónde viajar: ``sim_fill_finance_context`` guardaba ``price`` y
``reference_mid``, pero no de dónde salió el precio.

Qué crea:

1. ``sim_fill_finance_context.price_source`` — ``String(32)`` **nullable**: el literal canónico
   (``MARKET_CLOSE``/``SYNTHETIC``/``SCRIPT``/``MAPPING``/``REPLAY``/``XTB``) de la fuente que
   construyó ESE fill. Aditiva y **sin backfill**: ``NULL`` significa "fila anterior a 2.88.25 —
   la fuente no se midió", nunca un literal inventado. El vocabulario vive en
   ``bolsa_application.price_source_kind`` y se normaliza al persistir.

No se añade índice: la lectura es por ``cycle_id`` (ya indexado desde ``044``) y la fuente se lee
con la fila que ese índice devuelve. ``upgrade`` y ``downgrade`` son simétricos e idempotentes
(patrón 028–046) y la cadena es lineal (``down_revision = "046_fill_reference_mid"``). El contrato
de ``decision_journal_entries`` no se toca.

.. warning::

   **DESTRUCTIVE DATA DOWNGRADE — simetría de esquema ≠ reversibilidad de datos.** El ``downgrade``
   deja el esquema EXACTAMENTE como estaba (dropea la misma columna que creó el ``upgrade``), pero
   los datos no vuelven: las fuentes que el settlement persistió mientras la ``047`` estuvo aplicada
   se PIERDEN. No hay backfill (la fuente no se puede reconstruir desde el precio).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "047_fill_price_source"
down_revision = "046_fill_reference_mid"
branch_labels = None
depends_on = None

_FILL_CONTEXT = "sim_fill_finance_context"
_COLUMN = "price_source"


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


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, _FILL_CONTEXT):
        return
    if not _column_exists(bind, _FILL_CONTEXT, _COLUMN):
        # Nullable y sin server_default: la fuente ausente es un HECHO ("no se midió"), y
        # rellenarla convertiría el hueco en una fuente afirmada.
        op.add_column(_FILL_CONTEXT, sa.Column(_COLUMN, sa.String(32), nullable=True))


def downgrade() -> None:
    """Retira exactamente lo que creó el upgrade: la columna ``price_source``.

    Simétrico por construcción e idempotente. **DESTRUCTIVE DATA DOWNGRADE (declarado):** dropear
    la columna borra para siempre las fuentes que el settlement persistió; no existe backfill.
    """
    bind = op.get_bind()

    if _table_exists(bind, _FILL_CONTEXT) and _column_exists(bind, _FILL_CONTEXT, _COLUMN):
        op.drop_column(_FILL_CONTEXT, _COLUMN)
