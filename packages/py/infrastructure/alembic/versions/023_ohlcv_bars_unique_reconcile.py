"""V2.14 — reconcilia upsert OHLCV: índice único (instrument_id, timeframe, timestamp).

Motivo (schema-drift detectado en auditoría interna V2.14, co-verificada):
``ohlcv_repository.upsert_bars`` usa ``INSERT ... ON CONFLICT DO UPDATE`` con
``index_elements=["instrument_id", "timeframe", "timestamp"]`` (commit cd451fea,
bulk P2.3). PostgreSQL exige un índice/constraint único exacto sobre ese triple
para materializar el ``ON CONFLICT``. El ``ohlcv_bars`` vino de un esquema Prisma
previo; el modelo ORM ``OhlcvBarRow`` y la migración baseline ``003`` **no portan**
ese índice (solo PK ``id``), por lo que una BD creada desde alembic puro queda sin
él y cada sync aborta (500) con ``InvalidColumnReference: no unique or exclusion
constraint matching the ON CONFLICT`` -> listas sin bars y ``histórico no
disponible`` en la UI.

Fix (decisión de producto): añadir el índice único faltante para cumplir el
contrato que el código ya validó (cd451fea probó el re-upsert contra una BD que sí
lo tenía). Seguro de aplicar: el código actual nunca pudo insertar barras sin el
índice (abortaba siempre), por lo que no pueden existir duplicados en ese triple.

Idempotente + standalone (estilo 020/021/013/017/022): guards por
tabla/índice sin imports ORM (offline-safe).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "023_ohlcv_bars_unique_reconcile"
down_revision = "022_live_orders_exec"
branch_labels = None
depends_on = None

_TABLE = "ohlcv_bars"
_UQLD = "ohlcv_bars_instrument_timeframe_ts_uidx"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = (
        "SELECT 1 FROM pg_indexes"
        " WHERE schemaname = 'public' AND tablename = :t AND indexname = :i"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE, "i": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    # Índice único (instrument_id, timeframe, timestamp) requerido por el
    # ON CONFLICT DO UPDATE de ohlcv_repository.upsert_bars.
    if not _index_exists(bind, _UQLD):
        op.create_index(
            _UQLD,
            _TABLE,
            ["instrument_id", "timeframe", "timestamp"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE) and _index_exists(bind, _UQLD):
        op.drop_index(_UQLD, table_name=_TABLE)
