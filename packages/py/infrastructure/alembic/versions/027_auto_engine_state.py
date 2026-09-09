"""V2.22 / A9 (M4 · P2 del audit) — estado durable del AUTO Engine.

Sustituye la telemetría AUTO en-memoria de ``PaperAutoEngine``
(``_state|_last_tick|_proposals|_vetoes|_pending_plans|_last_reason``) por un
espejo durable en PostgreSQL, de modo que un worker reiniciado readopta
``RUNNING`` + contadores SIN un tick doble tras crash (invariante exact-una-vez
del bucle AUTO).

Dos tablas, espejo de los modelos ``AutoEngineRunRow`` / ``AutoEngineTickRow`` de
``database/models/tables.py`` (parity 1:1 con la migración):

* ``auto_engine_runs`` — UNA fila por ``engine_id`` (motor+venue): estado enum
  (String; convención enum-igual del repo, sin ENUM DDL), ``last_tick_at`` y
  contadores acumulados monótonos (proposals / vetoes / pending_plans /
  last_reason / updated_at).
* ``auto_engine_ticks`` — ledger append-only de cada ``run_tick`` matriculado:
  ``seq`` monótono por ``engine_id`` (UNIQUE(engine_id, seq)) para probar que un
  crash/relaunch no re-ejecuta el tick ya registrado.

Guard + idempotente estilo 013/020 (__future__, sin imports ORM): omite la tabla
o índices si ya existen (offline-safe, puede correr en scratch/dev sin romper).

down_revision ``026_execution_events_fence`` (cadena lineal; sin branch_labels).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "027_auto_engine_state"
down_revision = "026_execution_events_fence"
branch_labels = None
depends_on = None

_RUNS = "auto_engine_runs"
_TICKS = "auto_engine_ticks"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, _RUNS):
        # Si la fila-run ya existe (re-ejecución parcial/idempotencia) no la
        # recreamos; solo nos aseguramos de los índices declarados.
        if not _index_exists(bind, "auto_engine_runs_updated_at_idx"):
            op.create_index(
                "auto_engine_runs_updated_at_idx",
                _RUNS,
                ["updated_at"],
            )
    else:
        op.create_table(
            _RUNS,
            sa.Column("engine_id", sa.String(), primary_key=True),
            sa.Column("venue", sa.String(), nullable=False),
            sa.Column("state", sa.String(), nullable=False),
            sa.Column(
                "last_tick_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "proposals",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "vetoes",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "pending_plans",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("last_reason", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "auto_engine_runs_updated_at_idx",
            _RUNS,
            ["updated_at"],
        )

    if _table_exists(bind, _TICKS):
        # Re-ejecución idempotente: solo aseguramos índice de consulta si falta.
        if not _index_exists(bind, "auto_engine_ticks_engine_created_idx"):
            op.create_index(
                "auto_engine_ticks_engine_created_idx",
                _TICKS,
                ["engine_id", "created_at"],
            )
    else:
        op.create_table(
            _TICKS,
            sa.Column("tick_id", sa.String(), primary_key=True),
            sa.Column("engine_id", sa.String(), nullable=False),
            sa.Column("seq", sa.BigInteger(), nullable=False),
            sa.Column("state", sa.String(), nullable=False),
            sa.Column(
                "proposals",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "vetoes",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "pending_plans",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column(
                "tick_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            # UNIQUE real (constraint nombrada) sobre (engine_id, seq): habilita el
            # ``ON CONFLICT ON CONSTRAINT auto_engine_ticks_engine_seq_uidx`` que el
            # store durable usa para no-duplicar cada tick en crash/re-registro.
            sa.UniqueConstraint(
                "engine_id",
                "seq",
                name="auto_engine_ticks_engine_seq_uidx",
            ),
        )
        op.create_index(
            "auto_engine_ticks_engine_created_idx",
            _TICKS,
            ["engine_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TICKS):
        if _index_exists(bind, "auto_engine_ticks_engine_created_idx"):
            op.drop_index("auto_engine_ticks_engine_created_idx", table_name=_TICKS)
        op.drop_table(_TICKS)
    if _table_exists(bind, _RUNS):
        if _index_exists(bind, "auto_engine_runs_updated_at_idx"):
            op.drop_index("auto_engine_runs_updated_at_idx", table_name=_RUNS)
        op.drop_table(_RUNS)
