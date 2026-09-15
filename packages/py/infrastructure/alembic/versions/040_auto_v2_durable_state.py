"""AUTO 2.0 · P4 — durabilidad del estado V2 (plan de posición + señales consumidas).

Cierra el último hueco de recuperación del AUTO 2.0: el pipeline V2 decide con un
``PositionState`` (plan por operación: stop, T1/T2, parciales) y con una identidad de
señal (``signal_id`` = instrumento+versión+timeframe+barra+acción). Ambos vivían SOLO
en RAM del worker:

* tras crash/restart la posición se readoptaba **reconstruyendo** la geometría por ATR
  (``_v2_adopt_position``): el stop real, el T1/T2 del plan y los parciales ya tomados
  se inventaban de nuevo, de modo que el motor podía re-disparar un T1 ya ejecutado o
  proteger la posición en un nivel que nunca se decidió;
* las señales consumidas se perdían, y dentro de la misma barra podía re-emitirse la
  MISMA señal ya tomada (el ``churn`` que P1 quiere matar).

Esta migración aporta los dos espejos que faltaban, **aditivos y sin backfill** (la
ausencia es información: una fila antigua sin ``position_state`` sigue siendo válida y
el worker cae a la adopción reconstruida, ya auditada):

1. ``sim_auto_positions.position_state`` (JSONB nullable): el ``PositionState.to_dict()``
   completo, rehidratable con ``position_state_from_dict`` (inverso exacto, sin campos
   nuevos). El resto de columnas (``stop_price``/``t1_state``/``trailing_state``) siguen
   siendo la vista plana consultable/observable.
2. ``sim_consumed_signals``: identidad de señal consumida por
   ``(account_id, engine_id, signal_id)`` con su ``bar_timestamp``. Solo interesa la
   barra corriente; el worker poda las barras anteriores (la tabla no crece sin límite).

Convenciones del repo (parity 1:1 con ``tables.py``): ``String`` para estados/lados,
``Numeric(18,6)`` para cantidades/precios, guards idempotentes offline-safe
(patrón 028–039).

Cadena lineal: ``down_revision = "039_research_trials_regime"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "040_auto_v2_durable_state"
down_revision = "039_research_trials_regime"
branch_labels = None
depends_on = None

_POS = "sim_auto_positions"
_POS_STATE_COLUMN = "position_state"
_SIGNALS = "sim_consumed_signals"
_SIGNALS_BAR_INDEX = "sim_consumed_signals_bar_idx"


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

    # ── 1) Plan de posición V2 durable (rehidratable, no reconstruido) ────────
    if _table_exists(bind, _POS) and not _column_exists(bind, _POS, _POS_STATE_COLUMN):
        op.add_column(
            _POS,
            sa.Column(_POS_STATE_COLUMN, JSONB, nullable=True),
        )

    # ── 2) Señales consumidas por barra (anti-repetición durable) ─────────────
    if not _table_exists(bind, _SIGNALS):
        op.create_table(
            _SIGNALS,
            sa.Column("account_id", sa.String(), nullable=False),
            sa.Column("engine_id", sa.String(), nullable=False),
            # signal_id canónico = instrumento|versión|timeframe|barra|hash (separador
            # \x1f). Es la identidad COMPLETA de la señal, no solo el instrumento.
            sa.Column("signal_id", sa.String(), nullable=False),
            sa.Column("instrument_id", sa.String(), nullable=False),
            sa.Column("bar_timestamp", sa.String(), nullable=False),
            sa.Column(
                "consumed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint(
                "account_id", "engine_id", "signal_id", name="sim_consumed_signals_pk"
            ),
        )
    if _table_exists(bind, _SIGNALS) and not _index_exists(bind, _SIGNALS_BAR_INDEX):
        # La lectura útil es "lo consumido en ESTA barra" y la poda es por barra.
        op.create_index(
            _SIGNALS_BAR_INDEX,
            _SIGNALS,
            ["account_id", "engine_id", "bar_timestamp"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _SIGNALS):
        if _index_exists(bind, _SIGNALS_BAR_INDEX):
            op.drop_index(_SIGNALS_BAR_INDEX, table_name=_SIGNALS)
        op.drop_table(_SIGNALS)
    if _table_exists(bind, _POS) and _column_exists(bind, _POS, _POS_STATE_COLUMN):
        op.drop_column(_POS, _POS_STATE_COLUMN)
