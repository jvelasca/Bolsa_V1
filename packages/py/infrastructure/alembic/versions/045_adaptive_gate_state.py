"""AUTO-15 (V2.56) — la racha de fallos del sink del gate Adaptive, DURABLE.

La ventana que cierra. El gate de evidencia de ``AUTO-13`` graduía la salud de lo que Adaptive
sabe de sí mismo con dos hechos: un **contador de fallos consecutivos del sink** y un **ancla de
antigüedad del journal**. El ancla ya era durable (sale del ``asOf`` de la última fila publicada);
el contador vivía **solo en la memoria del proceso**, así que

    WORKER 1 → 2 fallos del sink (DEGRADED) → CRASH → WORKER 2 → 0 fallos → OK

El sistema olvidaba la racha con la que estaba juzgando su propia evidencia, y con ``3``
consecutivos (``DATA_GATE_SINK_FAILURES_STALE_DEFAULT``) el gate pasa a ``STALE`` (congela el
reparto y no admite reactivaciones nuevas): perderla al reiniciar reabre la ventana que ``AUTO-13``
declaró como límite suyo.

Y **no es reconstruible**: un fallo de escritura no dejó fila en ``decision_journal_entries``, y el
ancla de antigüedad mide *publicación*, no *error*. Deducirla del journal sería inventar la prueba
que el invariante exige. De ahí esta tabla: es el mismo P0 que ``043`` cerró para la parada dura
(``auto_kill_state``), con el mismo patrón.

Qué crea:

1. ``adaptive_gate_state`` — una fila por ``(account_id, engine_id)`` con ``sink_failures``
   (consecutivos), ``last_failure_at``, ``last_success_at`` y ``updated_at``. Aditiva y **sin
   backfill**: la ausencia de fila significa "no hay constancia durable de fallos" (racha 0), nunca
   un cero fabricado. El reset del éxito solo escribe ``WHERE sink_failures > 0``, así que un
   despliegue sano no paga una escritura por tick.
2. Índice ``adaptive_gate_state_account_failures_idx`` sobre ``(account_id, sink_failures)``: "¿qué
   motores de esta cuenta arrastran racha?" sin recorrer la tabla.

``upgrade`` y ``downgrade`` son simétricos e idempotentes (patrón 028–044) y la cadena es lineal
(``down_revision = "044_auto_cycle_trace"``). El contrato de ``decision_journal_entries`` y
``auto_adaptive_journal.py`` no se toca.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "045_adaptive_gate_state"
down_revision = "044_auto_cycle_trace"
branch_labels = None
depends_on = None

_GATE_TABLE = "adaptive_gate_state"
_GATE_ACCOUNT_FAILURES_IDX = "adaptive_gate_state_account_failures_idx"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def _create_gate_state(bind: sa.engine.Connection) -> None:
    """Crea ``adaptive_gate_state`` si falta (idempotente y offline-safe)."""
    if _table_exists(bind, _GATE_TABLE):
        return
    op.create_table(
        _GATE_TABLE,
        sa.Column("account_id", sa.String(), primary_key=True),
        sa.Column("engine_id", sa.String(), primary_key=True),
        # Consecutivos, no acumulados: un éxito lo RESETEA (misma semántica que el contador de
        # proceso que sustituye). ``server_default`` para que un INSERT que solo declare la clave
        # nazca en 0 y no en NULL.
        sa.Column(
            "sink_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def upgrade() -> None:
    bind = op.get_bind()

    _create_gate_state(bind)
    if _table_exists(bind, _GATE_TABLE) and not _index_exists(
        bind, _GATE_ACCOUNT_FAILURES_IDX
    ):
        op.create_index(
            _GATE_ACCOUNT_FAILURES_IDX, _GATE_TABLE, ["account_id", "sink_failures"]
        )


def downgrade() -> None:
    """Retira lo que creó esta migración: primero el índice, después la tabla.

    Simétrico por construcción: la tabla y su índice son de la 045 y ninguno está respaldado por
    una constraint del baseline, así que ``DROP`` es seguro sin la danza de
    ``DependentObjectsStillExist``.
    """
    bind = op.get_bind()

    if _table_exists(bind, _GATE_TABLE):
        if _index_exists(bind, _GATE_ACCOUNT_FAILURES_IDX):
            op.drop_index(_GATE_ACCOUNT_FAILURES_IDX, table_name=_GATE_TABLE)
        op.drop_table(_GATE_TABLE)
