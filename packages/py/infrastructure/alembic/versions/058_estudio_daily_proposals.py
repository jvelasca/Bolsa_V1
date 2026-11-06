"""058 — ``estudio_daily_proposals``: handoff durable propuesta ESTUDIO → ciclo AUTO.

El parte diario ESTUDIO ya sella por valor una identidad de señal (``signal.id``) y de
plan (``TradePlan.decisionId``), pero esa identidad vivía **solo** en el ``result`` del
job. El productor AUTO abría su ciclo con la identidad que derivaba de su propia barra
(``signal_identity_for_bar``) y no consumía el plan del parte; por eso el enlace
``señal → plan → reserva → orden → fill → posición → salida → cierre`` **no** era
demostrable, y lo único que coincidía era el símbolo (una inferencia, no una prueba).

Esta tabla es el puente durable: una fila por ``(cuenta, día, instrumento)`` con la
identidad propuesta, su geometría y su desenlace. El productor la lee, adopta la
identidad y la marca ``consumed`` con el ``cycle_id`` que abrió. Sin backfill: el
histórico anterior a esta revisión no se reescribe ni se le inventa identidad.

Índices:
* único **parcial** ``(account_id, day, instrument_id)`` donde ``status='proposed'``:
  una sola propuesta PENDIENTE por valor y día; el desenlace libera el hueco.
* único **parcial** sobre ``decision_id`` (solo cuando no es nulo): la identidad del
  plan no puede apuntar a dos propuestas.
* ``(account_id, bar_date)`` para la lectura del productor por frescura declarada.

Aditiva e idempotente (comprueba existencia antes de crear); ``downgrade`` simétrico.

Cadena lineal: ``down_revision = "057_top3_opportunity_identity"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "058_estudio_daily_proposals"
down_revision = "057_top3_opportunity_identity"
branch_labels = None
depends_on = None

_TABLE = "estudio_daily_proposals"
_PENDING_KEY = "estudio_daily_proposals_pending_key"
_DECISION_KEY = "estudio_daily_proposals_decision_key"
_ACCOUNT_BAR_IDX = "estudio_daily_proposals_account_bar_idx"


def _table_exists(bind: sa.engine.Connection) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("day", sa.String(), nullable=False),
        sa.Column("instrument_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=True),
        sa.Column("decision_id", sa.String(), nullable=True),
        sa.Column("signal_id", sa.String(), nullable=True),
        sa.Column("strategy_definition_id", sa.String(), nullable=True),
        sa.Column("strategy_version", sa.Integer(), nullable=True),
        sa.Column("preset_key", sa.String(), nullable=True),
        sa.Column("bar_date", sa.String(), nullable=True),
        sa.Column(
            "plan",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("consumed_cycle_id", sa.String(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        f"CREATE UNIQUE INDEX {_PENDING_KEY} ON {_TABLE} "
        "(account_id, day, instrument_id) "
        "WHERE status = 'proposed'"
    )
    op.execute(
        f"CREATE UNIQUE INDEX {_DECISION_KEY} ON {_TABLE} "
        "(decision_id) "
        "WHERE decision_id IS NOT NULL"
    )
    op.create_index(_ACCOUNT_BAR_IDX, _TABLE, ["account_id", "bar_date"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    op.execute(f"DROP INDEX IF EXISTS {_DECISION_KEY}")
    op.execute(f"DROP INDEX IF EXISTS {_PENDING_KEY}")
    op.drop_index(_ACCOUNT_BAR_IDX, table_name=_TABLE)
    op.drop_table(_TABLE)
