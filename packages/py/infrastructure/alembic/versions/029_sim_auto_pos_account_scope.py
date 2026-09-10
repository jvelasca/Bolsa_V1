"""V2.24 / A9.1 (P1-02 + P2-01) — aislamiento por cuenta + estado de protección SIM.

Cierra el P1-02 del audit V2.23: ``sim_auto_positions`` tenía PK
``(engine_id, symbol)`` **sin** ``account_id``, de modo que dos cuentas con el mismo
``engine_id`` (p. ej. ``auto-sim``) y el mismo símbolo colisionaban en la MISMA fila
(una cuenta leía la posición de otra). Aquí:

1. se añade ``account_id NOT NULL`` a ``sim_auto_positions`` y se rehace la PK a
   ``(account_id, engine_id, symbol)`` (con backfill de filas previas a un valor
   centinela inequívoco, revisable por operador), y
2. se añaden las columnas de ESTADO DE PROTECCIÓN por posición (P2-01):
   ``entry_price``, ``high_watermark``, ``stop_price``, ``t1_state``,
   ``trailing_state`` — para que un crash/restart readopte SL/T1/trailing sin
   recalcular de cero (el trailing no debe olvidar el máximo tras un reinicio).

Además se endurece la defensa de identidad del contexto financiero
(``sim_fill_finance_context.account_id``) con índice compuesto
``(account_id, execution_id)`` (P1-03, defensa redundante por scope).

Convenciones: ``String`` para estados/lados (sin ENUM DDL), ``Numeric(18,6)`` para
precios/cantidades, guards idempotentes ``_table_exists``/``_column_exists``/
``_index_exists``/``_pk_columns`` (offline-safe).

Cadena lineal: ``down_revision = "028_sim_finance_position_durable"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "029_sim_auto_pos_account_scope"
down_revision = "028_sim_finance_position_durable"
branch_labels = None
depends_on = None

_POS = "sim_auto_positions"
_FIN_CTX = "sim_fill_finance_context"

# Centinela de backfill: filas anteriores a la migración no conocían la cuenta. NO se
# inventa una cuenta real (jamás acreditar la posición a una cuenta arbitraria); el
# operador debe revisar/adoptar. El worker AUTO solo escribe ya con account_id real.
_LEGACY_ACCOUNT_ID = "legacy-unscoped"

_PROTECTION_COLUMNS: tuple[tuple[str, sa.types.TypeEngine[object]], ...] = (
    ("entry_price", sa.Numeric(18, 6)),
    ("high_watermark", sa.Numeric(18, 6)),
    ("stop_price", sa.Numeric(18, 6)),
    ("t1_state", sa.String()),
    ("trailing_state", sa.String()),
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


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def _constraint_exists(bind: sa.engine.Connection, constraint_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE table_schema = 'public' AND constraint_name = :n"
    )
    return bind.scalar(sa.text(sql), {"n": constraint_name}) is not None


def _pk_columns(bind: sa.engine.Connection, table_name: str) -> list[str]:
    sql = (
        "SELECT a.attname "
        "FROM pg_index i "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = (:t)::regclass AND i.indisprimary "
        "ORDER BY a.attnum"
    )
    rows = bind.scalars(sa.text(sql), {"t": table_name}).all()
    return [str(r) for r in rows]


def upgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, _POS):
        # ── P1-02: account_id en la identidad de la posición ────────────────
        if not _column_exists(bind, _POS, "account_id"):
            op.add_column(
                _POS,
                sa.Column("account_id", sa.String(), nullable=True),
            )
            # Backfill de filas previas (revisable; nunca se acredita a una cuenta real).
            op.execute(
                sa.text(
                    f"UPDATE {_POS} SET account_id = :legacy WHERE account_id IS NULL"
                ).bindparams(legacy=_LEGACY_ACCOUNT_ID)
            )
            op.alter_column(_POS, "account_id", nullable=False)

        # ── P2-01: estado de protección durable por posición ────────────────
        for column_name, column_type in _PROTECTION_COLUMNS:
            if not _column_exists(bind, _POS, column_name):
                op.add_column(
                    _POS,
                    sa.Column(column_name, column_type, nullable=True),
                )

        # ── PK compuesta nueva (account_id, engine_id, symbol) ──────────────
        pk_cols = _pk_columns(bind, _POS)
        if pk_cols != ["account_id", "engine_id", "symbol"]:
            if _constraint_exists(bind, "sim_auto_positions_pk"):
                op.drop_constraint("sim_auto_positions_pk", _POS, type_="primary")
            op.create_primary_key(
                "sim_auto_positions_pk",
                _POS,
                ["account_id", "engine_id", "symbol"],
            )

        if not _index_exists(bind, "sim_auto_positions_account_engine_updated_idx"):
            op.create_index(
                "sim_auto_positions_account_engine_updated_idx",
                _POS,
                ["account_id", "engine_id", "updated_at"],
            )

    # ── P1-03 (defensa redundante): scope de cuenta en el contexto financiero ─
    if _table_exists(bind, _FIN_CTX) and not _index_exists(
        bind, "sim_fill_finance_context_account_exec_idx"
    ):
        op.create_index(
            "sim_fill_finance_context_account_exec_idx",
            _FIN_CTX,
            ["account_id", "execution_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, _FIN_CTX) and _index_exists(
        bind, "sim_fill_finance_context_account_exec_idx"
    ):
        op.drop_index("sim_fill_finance_context_account_exec_idx", table_name=_FIN_CTX)

    if _table_exists(bind, _POS):
        if _index_exists(bind, "sim_auto_positions_account_engine_updated_idx"):
            op.drop_index(
                "sim_auto_positions_account_engine_updated_idx", table_name=_POS
            )
        pk_cols = _pk_columns(bind, _POS)
        if pk_cols != ["engine_id", "symbol"]:
            # Downgrade a la PK antigua ``(engine_id, symbol)``: varias cuentas pueden
            # compartir (engine_id, symbol) tras 029, lo que violaría la PK vieja. Se
            # conserva UNA fila por par (la más reciente) y se descartan las demás
            # homónimas de otras cuentas (pérdida documentada e inevitable del downgrade).
            op.execute(
                sa.text(
                    f"""
                    DELETE FROM {_POS} p
                    USING {_POS} q
                    WHERE p.engine_id = q.engine_id
                      AND p.symbol = q.symbol
                      AND (
                        p.updated_at < q.updated_at
                        OR (p.updated_at = q.updated_at AND p.account_id > q.account_id)
                      )
                    """
                )
            )
            if _constraint_exists(bind, "sim_auto_positions_pk"):
                op.drop_constraint("sim_auto_positions_pk", _POS, type_="primary")
            op.create_primary_key(
                "sim_auto_positions_pk",
                _POS,
                ["engine_id", "symbol"],
            )
        for column_name, _column_type in reversed(_PROTECTION_COLUMNS):
            if _column_exists(bind, _POS, column_name):
                op.drop_column(_POS, column_name)
        if _column_exists(bind, _POS, "account_id"):
            op.drop_column(_POS, "account_id")
