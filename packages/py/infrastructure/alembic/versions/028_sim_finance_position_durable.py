"""V2.23 / A9 (Bloque 5 · P1-05 + P1-06) — durabilidad SIM (contexto financiero + posición).

Cierra dos huecos del audit A9 en el AUTO SIM-ONLY:

1. **Contexto financiero por fill** (``sim_fill_finance_context``): el
   ``ExecutionEvent`` durable NO lleva ``instrument_id``/``side``/``price`` (solo
   ``execution_id``/``qty``/``account_id``/``venue``). La finance real recuperaba ese
   contexto de la memoria del ``SimulatedOrderResult`` (no durable, no
   crash-recuperable). Aquí se persiste por ``execution_id`` lo justo para que un
   resolver pueda reconstruir la finance de ESE fill sin memoria del proceso.

2. **Posición SIM durable** (``sim_auto_positions``): el worker AUTO guardaba las
   posiciones abiertas solo en RAM (``self._open``). Tras crash/restart re-compraba
   (P1-06 / invariante G7: BUY 100 → crash → restart → position=100 → NO segundo BUY).
   Espejo durable por ``(engine_id, symbol)`` con la cantidad abierta.

Convenciones del repo (parity 1:1 con las filas de ``tables.py``): ``String`` para
estados/lados (sin ENUM DDL), ``Numeric(18,6)`` para cantidades/precios,
``server_default`` para timestamps/contadores, guards idempotentes ``_table_exists``/
``_index_exists`` (offline-safe, pueden correr dos veces en scratch/dev).

Cadena lineal: ``down_revision = "027_auto_engine_state"`` (sin branch_labels).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "028_sim_finance_position_durable"
down_revision = "027_auto_engine_state"
branch_labels = None
depends_on = None

_FIN_CTX = "sim_fill_finance_context"
_POS = "sim_auto_positions"


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

    # ── 1) Contexto financiero durable por execution_id ─────────────────────
    if _table_exists(bind, _FIN_CTX):
        if not _index_exists(bind, "sim_fill_finance_context_account_idx"):
            op.create_index(
                "sim_fill_finance_context_account_idx",
                _FIN_CTX,
                ["account_id"],
            )
    else:
        op.create_table(
            _FIN_CTX,
            sa.Column("execution_id", sa.String(), primary_key=True),
            sa.Column("instrument_id", sa.String(), nullable=False),
            # ``buy``/``sell`` (enum-igual: String, sin ENUM DDL).
            sa.Column("side", sa.String(length=8), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
            sa.Column("price", sa.Numeric(18, 6), nullable=False),
            sa.Column("account_id", sa.String(), nullable=True),
            sa.Column("venue", sa.String(), nullable=False),
            sa.Column("idempotency_key", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "sim_fill_finance_context_account_idx",
            _FIN_CTX,
            ["account_id"],
        )

    # ── 2) Posición SIM durable (readopción crash/restart, G7) ──────────────
    if _table_exists(bind, _POS):
        if not _index_exists(bind, "sim_auto_positions_engine_updated_idx"):
            op.create_index(
                "sim_auto_positions_engine_updated_idx",
                _POS,
                ["engine_id", "updated_at"],
            )
    else:
        op.create_table(
            _POS,
            sa.Column("engine_id", sa.String(), nullable=False),
            # ``symbol`` (no FK a instruments: el motor AUTO opera por símbolo de
            # watch y espeja auto_engine_runs, sin acoplar al catálogo).
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
            sa.Column("avg_price", sa.Numeric(18, 6), nullable=True),
            sa.Column(
                "opened_at",
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
            sa.PrimaryKeyConstraint("engine_id", "symbol", name="sim_auto_positions_pk"),
        )
        op.create_index(
            "sim_auto_positions_engine_updated_idx",
            _POS,
            ["engine_id", "updated_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _POS):
        if _index_exists(bind, "sim_auto_positions_engine_updated_idx"):
            op.drop_index("sim_auto_positions_engine_updated_idx", table_name=_POS)
        op.drop_table(_POS)
    if _table_exists(bind, _FIN_CTX):
        if _index_exists(bind, "sim_fill_finance_context_account_idx"):
            op.drop_index("sim_fill_finance_context_account_idx", table_name=_FIN_CTX)
        op.drop_table(_FIN_CTX)
