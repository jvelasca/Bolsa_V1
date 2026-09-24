"""AUTO-16 (V2.57) — la REFERENCIA con la que el simulador construyó el precio del fill.

La ventana que cierra. El R neto de un ciclo se calcula descontando un **coste**, y ese coste llevaba
tres fases siendo el que el decisor **SUPUSO** (``TradingCost``: ``spread_bps=2`` / ``slippage_bps=5``
/ ``commission_bps=10``), nunca el que el simulador **APLICÓ**. El simulador no lo esconde: construye
el precio con una fricción determinista y adversa sobre un mid de referencia

    ``px = base_mid ± |adverse_slippage_bps·i + spread_bps/2|``

así que la fricción aplicada es ``|price − base_mid| × qty`` por fill — **medible**, y **no**
reconstruible desde el precio solo (el precio ya la lleva dentro).

Por qué hace falta una columna y no basta calcularlo en memoria: la pata de **ENTRADA** de un ciclo se
liquidó en un tick **anterior** —otra sesión, posiblemente otro proceso—, y entonces su ``base_mid``
viajaba en una variable del settlement y se tiraba. Sin persistirla, medio ciclo se mide y la otra
mitad se pierde al reiniciar: exactamente la lección que ``AUTO-15`` pagó con la racha del gate.

Qué crea:

1. ``sim_fill_finance_context.reference_mid`` — ``Numeric(18,6)`` **nullable**: el mid de referencia
   con el que ESE fill se construyó. Aditiva y **sin backfill**: ``NULL`` significa "fila anterior a
   2.57 — la referencia no se midió", nunca un ``0`` (un ``0`` ahí diría "fricción gratis", que es
   regalar R). La fricción aplicada **no** se persiste: es una función pura de ``(price, side, qty,
   reference_mid)`` y se computa pura, para que haya una sola fuente de verdad.

No se añade índice: la lectura es por ``cycle_id``, que ya está indexado desde ``044``
(``sim_fill_finance_context_cycle_id_idx``), y la referencia se lee con la fila que ese índice
devuelve. ``upgrade`` y ``downgrade`` son simétricos e idempotentes (patrón 028–045) y la cadena es
lineal (``down_revision = "045_adaptive_gate_state"``). El contrato de ``decision_journal_entries`` y
``auto_adaptive_journal.py`` no se toca.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "046_fill_reference_mid"
down_revision = "045_adaptive_gate_state"
branch_labels = None
depends_on = None

_FILL_CONTEXT = "sim_fill_finance_context"
_COLUMN = "reference_mid"


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
        # Nullable y sin server_default: la referencia ausente es un HECHO ("no se midió"), y
        # rellenarla con 0 convertiría el hueco en "fricción cero".
        op.add_column(
            _FILL_CONTEXT, sa.Column(_COLUMN, sa.Numeric(18, 6), nullable=True)
        )


def downgrade() -> None:
    """Retira exactamente lo que creó el upgrade: la columna ``reference_mid``.

    Simétrico por construcción: la columna no está respaldada por ninguna constraint del baseline,
    así que el ``DROP`` es seguro e idempotente.
    """
    bind = op.get_bind()

    if _table_exists(bind, _FILL_CONTEXT) and _column_exists(bind, _FILL_CONTEXT, _COLUMN):
        op.drop_column(_FILL_CONTEXT, _COLUMN)
