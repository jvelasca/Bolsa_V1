"""V2.20 (A7 Iter-3 · P1-01/P2-01) — lease de ownership del ExecutionEvent (desc 025).

* ``execution_events``: para que ``start_apply`` sea un CAS EXCLUSIVO real (sin
  auto-reclaim de un ``APPLYING`` en curso por otro worker) y para poder distinguir
  un ``APPLYING`` **stale** (dueño muerto) de uno **vivo** (dueño en marcha), se
  añade la columna **lease** de ownership *por proceso* al workflow durable (024):

  * ``lease_owner`` : identidad del worker/proceso (``live-recovery-<pid>``) que
    posee el derecho a materializar (``APPLYING``). Quien gana ``start_apply``
    adquiere el lease; quien libera/termina se lo quita. ``NULL`` sin owner.
  * ``updated_at`` : último instante de transición (se rellena en cada
    ``start_apply``/``mark_*``/reclaim). Es el reloj del reaper: una fila
    ``APPLYING`` cuyo ``updated_at`` envejece más allá del timeout con su
    dueño/reclamador caído pasa a poder ser reclamada como **stale**.

  Esto NO cambia la identidad de idempotencia (PK ``execution_id``): la siguen
  siendo la fila única por fill + (en la capa financiera reusada) la
  ``idempotency_key`` de ``ExecuteTrade``. Solo aporta la llave del single-owner.

Guard + standalone (estilo 022/023/024): guards por tabla/columna sin imports ORM
(offline-safe). Aditivo y nullable (no toca filas existentes).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "025_execution_events_lease"
down_revision = "024_execution_events_state"
branch_labels = None
depends_on = None

_EXEC = "execution_events"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table, "c": column}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _EXEC):
        # Sin tabla execution_events (BD vieja/parcial): nada que alterar. La 022 la
        # crearía; si no existe aquí la cadena no llegó → no añadimos sobre la nada.
        return
    col_specs = [("lease_owner", sa.String()), ("updated_at", sa.DateTime(timezone=True))]
    for col_name, col_type in col_specs:
        if not _column_exists(bind, _EXEC, col_name):
            op.add_column(_EXEC, sa.Column(col_name, col_type, nullable=True))
    idx = "ix_execution_events_status_updated_at"
    existing = bind.scalar(
        sa.text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
        {"n": idx},
    )
    if existing is None:
        if _column_exists(bind, _EXEC, "status") and _column_exists(bind, _EXEC, "updated_at"):
            op.create_index(idx, _EXEC, ["status", "updated_at"])
    # Backfill del reloj de lease: filas pre-existentes (p.ej. un APPLYING stall de
    # V2.19 sin 025) toman como updated_at su captured_at para que el reaper pueda
    # envejecerlas de forma determinista (no updated_at NULL = "desconocido").
    if _column_exists(bind, _EXEC, "updated_at") and _column_exists(bind, _EXEC, "captured_at"):
        conn = op.get_bind()
        conn.execute(
            sa.text(
                "UPDATE execution_events SET updated_at = captured_at "
                "WHERE updated_at IS NULL AND captured_at IS NOT NULL"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _EXEC):
        return
    # Índice primero (si existe), luego columnas (forward-only recomendado en prod:
    # ver nota en traspaso — no hacer downgrade sobre BD con execution history).
    idx = "ix_execution_events_status_updated_at"
    existing_index = bind.scalar(
        sa.text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
        {"n": idx},
    )
    if existing_index is not None:
        op.drop_index(idx, table_name=_EXEC)
    for col_name in ("updated_at", "lease_owner"):
        if _column_exists(bind, _EXEC, col_name):
            op.drop_column(_EXEC, col_name)
