"""V2.14 — live_orders observabilidad recovery + execution_events (desc 022).

Revision id corto (constraint alembic_version varchar32, convención repo: 021).

* ``live_orders``: + ``attempt_count``/``last_error``/``claim_expires_at``
  (observabilidad operacional del lease/recovery, B2→E1; no son estado de negocio).
* ``execution_events``: traza idempotente del fill financiero. identity
  ``execution_id`` única (PK) = clave de idempotencia: dos insert del mismo fill →
  uno solo materializa (el materializado a PositionState/Ledger queda GATED en una
  capa superior por consentimiento; esta tabla es la traza previa).

Idempotente + standalone (estilo 020/021/013/017): guards por tabla/columna/tabla
sin imports ORM (offline-safe).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "022_live_orders_exec"
down_revision = "021_live_orders_fin"
branch_labels = None
depends_on = None

_LIVE_ORDERS = "live_orders"
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
    if not _table_exists(bind, _LIVE_ORDERS):
        return
    # Observabilidad recovery worker (no alter de datos; nullable).
    for col_name, col_type in (
        ("attempt_count", sa.Integer),
        ("last_error", sa.Text()),
        ("claim_expires_at", sa.DateTime(timezone=True)),
    ):
        if not _column_exists(bind, _LIVE_ORDERS, col_name):
            op.add_column(
                _LIVE_ORDERS,
                sa.Column(col_name, col_type, nullable=True),
            )

    if _table_exists(bind, _EXEC):
        return
    op.create_table(
        _EXEC,
        sa.Column("execution_id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("venue", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=True),
        sa.Column("venue_order_id", sa.String(), nullable=True),
        sa.Column("fill_seq", sa.Integer(), nullable=True),
        sa.Column("qty", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index("execution_events_order_id_idx", _EXEC, ["order_id"])
    op.create_index(
        "execution_events_venue_order_id_idx",
        _EXEC,
        ["venue_order_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _EXEC):
        op.drop_table(_EXEC)
    if not _table_exists(bind, _LIVE_ORDERS):
        return
    for col_name in ("attempt_count", "last_error", "claim_expires_at"):
        if _column_exists(bind, _LIVE_ORDERS, col_name):
            op.drop_column(_LIVE_ORDERS, col_name)
