"""065 — intención DURABLE del operador sobre AUTO (M10, auditoría .183).

La auditoría señaló que AUTO se habilitaba **sólo** por variable de entorno: tras un
reinicio con ``AUTO_SIMULATION_WORKER_ENABLED=1`` el worker arrancaba aunque el operador
lo hubiera apagado, porque no existía ningún latch durable del apagado.

Esta revisión crea ``auto_engine_intent`` con una fila por ``(account_id, engine_id)``:

* ``desired_state`` — ``ON``/``OFF``. Sólo esos dos valores: un valor desconocido NO es
  una decisión y el store lo trata como ausente (env decide), nunca como ``ON``.
* ``reason``/``actor`` — quién apagó el motor y por qué (auditable).
* ``version`` — cuenta escrituras; la última intención gana.
* ``updated_at`` — instante de la última intención.

Sin backfill a propósito: la ausencia de fila significa «el operador no ha declarado
intención» y el env sigue decidiendo (comportamiento previo intacto). Lo que cambia es que
un ``OFF`` explícito **sobrevive** al reinicio aunque el env siga en ``ON``.

``downgrade`` retira la tabla (con sus filas).

Cadena lineal: ``down_revision = "064_strategy_account_scope"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "065_auto_engine_intent"
down_revision = "064_strategy_account_scope"
branch_labels = None
depends_on = None

_TABLE = "auto_engine_intent"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("engine_id", sa.String(), nullable=False),
        sa.Column("desired_state", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("account_id", "engine_id", name="auto_engine_intent_pkey"),
        sa.CheckConstraint(
            "desired_state IN ('ON', 'OFF')",
            name="auto_engine_intent_desired_state_ck",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        op.drop_table(_TABLE)
