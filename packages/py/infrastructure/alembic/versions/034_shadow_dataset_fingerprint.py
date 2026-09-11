"""V2.32.1 / A12.1 — fingerprint reproducible de la evidencia shadow.

Hasta V2.32.1 la tabla ``strategy_shadow_validations`` guardaba las métricas contables
(trades, retorno, drawdown, win-rate) y el veredicto, pero NO la identidad del dataset:
no se podía demostrar *con qué barras exactas* se autorizó una promoción, solo cuántas.

Esta migración añade la evidencia reproducible (todas nullable: las filas previas no
tenían el dato y no se inventa un valor falso):

* ``round_trips``: operaciones **cerradas** (la guarda de muestra real; ``trades`` son
  piernas ejecutadas).
* ``data_snapshot_id`` / ``shadow_start`` / ``shadow_end`` / ``lab_end``: rango temporal
  del hold-out y frontera del LAB (separación demostrable).
* ``bars_hash``: hash determinista del hold-out exacto (timestamps + OHLCV).
* ``strategy_definition_hash`` / ``engine_version`` / ``config_hash``: identidad de la
  definición, del motor de replay y de la configuración.

Aditivo y nullable. Sin backfill: la ausencia de evidencia es información, no un dato
falso. Guards idempotentes offline-safe (patrón 030/031/032/033).

Cadena lineal: ``down_revision = "033_position_strategy_attr"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "034_shadow_dataset_fingerprint"
down_revision = "033_position_strategy_attr"
branch_labels = None
depends_on = None

_TABLE = "strategy_shadow_validations"

_COLUMNS: tuple[tuple[str, sa.types.TypeEngine[object]], ...] = (
    ("round_trips", sa.Integer()),
    ("data_snapshot_id", sa.String()),
    ("shadow_start", sa.String()),
    ("shadow_end", sa.String()),
    ("bars_hash", sa.String()),
    ("strategy_definition_hash", sa.String()),
    ("engine_version", sa.String()),
    ("config_hash", sa.String()),
    ("lab_end", sa.String()),
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


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    for name, column_type in _COLUMNS:
        if _column_exists(bind, _TABLE, name):
            continue
        kwargs: dict[str, object] = {"nullable": True}
        if name == "round_trips":
            kwargs["nullable"] = False
            kwargs["server_default"] = "0"
        op.add_column(_TABLE, sa.Column(name, column_type, **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    for name, _column_type in reversed(_COLUMNS):
        if _column_exists(bind, _TABLE, name):
            op.drop_column(_TABLE, name)
