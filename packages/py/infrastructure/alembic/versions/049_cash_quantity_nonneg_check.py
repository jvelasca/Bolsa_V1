"""AUTO v2.88.68 — CHECK de cash y cantidad no negativos.

Si alguna fila viva tiene ``portfolios.cash < 0`` o ``positions.quantity < 0``,
``upgrade`` aborta y no borra nada. El sello no inventa un recuento en cero:
el conteo lo hace la propia migración contra la base a la que se aplica.

``down_revision = "048_journal_entry_dedupe_key"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "049_cash_quantity_nonneg_check"
down_revision = "048_journal_entry_dedupe_key"
branch_labels = None
depends_on = None

_CASH_CHECK = "ck_portfolios_cash_nonneg"
_QTY_CHECK = "ck_positions_quantity_nonneg"


def assert_no_negative_balances(
    cash_count: int,
    quantity_count: int,
    cash_sample: list[tuple[str, str]],
    quantity_sample: list[tuple[str, str, str]],
) -> None:
    """Aborta si hay negativos. No borra filas."""
    if cash_count == 0 and quantity_count == 0:
        return
    raise RuntimeError(
        "049: hay cash o cantidad negativos. La migración aborta y no borra nada. "
        f"portfolios.cash<0: {cash_count} muestra={cash_sample}; "
        f"positions.quantity<0: {quantity_count} muestra={quantity_sample}"
    )


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _constraint_exists(bind: sa.engine.Connection, name: str) -> bool:
    sql = "SELECT 1 FROM pg_constraint WHERE conname = :n"
    return bind.scalar(sa.text(sql), {"n": name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    cash_count = 0
    quantity_count = 0
    cash_sample: list[tuple[str, str]] = []
    quantity_sample: list[tuple[str, str, str]] = []
    if _table_exists(bind, "portfolios"):
        cash_count = int(
            bind.scalar(sa.text("SELECT count(*) FROM portfolios WHERE cash < 0")) or 0
        )
        if cash_count:
            rows = bind.execute(
                sa.text("SELECT id, cash::text FROM portfolios WHERE cash < 0 LIMIT 20")
            ).all()
            cash_sample = [(str(r[0]), str(r[1])) for r in rows]
    if _table_exists(bind, "positions"):
        quantity_count = int(
            bind.scalar(sa.text("SELECT count(*) FROM positions WHERE quantity < 0")) or 0
        )
        if quantity_count:
            rows = bind.execute(
                sa.text(
                    "SELECT id, portfolio_id, quantity::text "
                    "FROM positions WHERE quantity < 0 LIMIT 20"
                )
            ).all()
            quantity_sample = [(str(r[0]), str(r[1]), str(r[2])) for r in rows]
    assert_no_negative_balances(cash_count, quantity_count, cash_sample, quantity_sample)
    if _table_exists(bind, "portfolios") and not _constraint_exists(bind, _CASH_CHECK):
        op.create_check_constraint(_CASH_CHECK, "portfolios", "cash >= 0")
    if _table_exists(bind, "positions") and not _constraint_exists(bind, _QTY_CHECK):
        op.create_check_constraint(_QTY_CHECK, "positions", "quantity >= 0")


def downgrade() -> None:
    bind = op.get_bind()
    if _constraint_exists(bind, _QTY_CHECK):
        op.drop_constraint(_QTY_CHECK, "positions", type_="check")
    if _constraint_exists(bind, _CASH_CHECK):
        op.drop_constraint(_CASH_CHECK, "portfolios", type_="check")
