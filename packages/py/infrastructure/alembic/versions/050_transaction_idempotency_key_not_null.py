"""AUTO v2.88.69 — idempotency_key NOT NULL solo si no hay nulos.

El ``upgrade`` cuenta ``transactions.idempotency_key IS NULL``. Si el conteo
no es cero, aborta y no rellena claves. El unique
``transactions_portfolio_id_idempotency_key_key`` no se toca.

``down_revision = "049_cash_quantity_nonneg_check"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "050_transaction_idempotency_key_not_null"
down_revision = "049_cash_quantity_nonneg_check"
branch_labels = None
depends_on = None


def assert_zero_null_idempotency_keys(null_count: int) -> None:
    """Aborta si hay nulos. No inventa claves."""
    if null_count == 0:
        return
    raise RuntimeError(
        "050: transactions.idempotency_key tiene "
        f"{null_count} nulos. No se rellenan claves y no se aplica NOT NULL."
    )


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_nullable(bind: sa.engine.Connection) -> bool | None:
    sql = (
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'transactions' "
        "AND column_name = 'idempotency_key'"
    )
    value = bind.scalar(sa.text(sql))
    if value is None:
        return None
    return str(value).upper() == "YES"


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "transactions"):
        return
    nullable = _column_nullable(bind)
    if nullable is None or nullable is False:
        return
    null_count = int(
        bind.scalar(
            sa.text("SELECT count(*) FROM transactions WHERE idempotency_key IS NULL")
        )
        or 0
    )
    assert_zero_null_idempotency_keys(null_count)
    op.alter_column("transactions", "idempotency_key", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _column_nullable(bind) is False:
        op.alter_column("transactions", "idempotency_key", nullable=True)
