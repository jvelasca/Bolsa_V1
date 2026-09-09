"""V2.19 (A7 Iter-2, P2-01) — workflow durable del ExecutionEvent (desc 024).

* ``execution_events``: traza idempotente del fill (022) pasa a tener un
  **estado de workflow durable** para poder probar/infligir crash en medio del
  ``apply`` (C3-C/C3-D) sin perder ni duplicar dinero.

  Hoy la fila es *traza previa* (identity ``execution_id`` única → idempotencia
  de captura real vía ``ON CONFLICT DO NOTHING``). Esta revisión **no enchufa**
  ninguna materialización nueva: añade, de forma aditiva y nullable/default, la
  observabilidad que el dominio ``execution_event`` necesita para coordinar el
  apply **por fases** bajo un go fail-closed nuevo (default OFF):

  * ``status``: ciclo del apply durable —
    ``CAPTURED`` (fila insertada, sin materializar dinero es el default) ·
    ``APPLYING`` (una instancia posee en curso, previa al commit financiero) ·
    ``APPLIED`` (materialización efectiva y durable) ·
    ``FAILED`` (apply no efectivo) · ``RETRY`` (fallo transitorio reaplicable).
  * ``applied_at``: cuándo se materializó (nullable → no-APPLIED).
  * ``attempt_count``: nº de intentos de apply (observabilidad crash/restart).
  * ``last_error``: último error del apply (nullable).

  El **contador no es el mecanismo de idempotencia**: lo sigue siendo la PK
  ``execution_id`` + (en la capa financiera, reusada) la ``idempotency_key`` de
  ``ExecuteTrade``. Este status es el *marco de truth* del workflow para decidir,
  tras un crash/restart, si reaparecer = reaplicar (RETRY/APPLYING stale) o no
  (APPLIED). **No materializa dinero por sí misma** — la materialización queda al
  ``execution_event``/worker bajo su go OFF por defecto (escalera H4/H3 intacta).
  Si el bridge nunca reporta precio/plan (venje LIVE sin fill price) la fila se
  queda en ``CAPTURED`` y nada toca Position/Ledger (fsm_only exacto de V2.18).

Idempotente + standalone (estilo 020/021/013/017/022/023): guards por
tabla/columna sin imports ORM (offline-safe).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "024_execution_events_state"
down_revision = "023_ohlcv_bars_unique_reconcile"
branch_labels = None
depends_on = None

_EXEC = "execution_events"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
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
        # No hay tabla execution_events (BD vieja/parcial): nada que alterar.
        # La 022 ya habría creado la tabla; si no existe aquí es porque la cadena
        # no llegó a crearla → no añadimos columnas sobre la nada.
        return
    if not _column_exists(bind, _EXEC, "status"):
        op.add_column(
            _EXEC,
            sa.Column(
                "status",
                sa.String(16),
                server_default=sa.text("'CAPTURED'"),
                nullable=False,
            ),
        )
    if not _column_exists(bind, _EXEC, "applied_at"):
        op.add_column(
            _EXEC,
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists(bind, _EXEC, "attempt_count"):
        op.add_column(
            _EXEC,
            sa.Column(
                "attempt_count",
                sa.Integer,
                server_default=sa.text("0"),
                nullable=False,
            ),
        )
    if not _column_exists(bind, _EXEC, "last_error"):
        op.add_column(
            _EXEC,
            sa.Column("last_error", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _EXEC):
        return
    for col_name in ("status", "applied_at", "attempt_count", "last_error"):
        if _column_exists(bind, _EXEC, col_name):
            op.drop_column(_EXEC, col_name)
