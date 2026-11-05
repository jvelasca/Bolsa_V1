"""066 — política de evidencia de rentabilidad por cuenta (``account_evidence_policy``).

Una fila por cuenta con los umbrales que deben fijarse ANTES de medir un backtest DÍA D:
nº de ventanas, operaciones mínimas, % de ventanas positivas, retorno neto mínimo, drawdown
máximo, exceso sobre comprar y mantener, reserva fuera de muestra y costes mínimos por lado.

Sin backfill: la ausencia de fila significa «defaults estrictos» (fail-closed), nunca un umbral
relajado. Los CHECK replican los rangos de ``bolsa_application.account_evidence_policy``.

``downgrade`` retira la tabla. Cadena lineal: ``down_revision = "065_auto_engine_intent"``.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "066_account_evidence_policy"
down_revision = "065_auto_engine_intent"
branch_labels = None
depends_on = None

_TABLE = "account_evidence_policy"

CHECKS: tuple[tuple[str, str], ...] = (
    ("min_windows", "min_windows BETWEEN 5 AND 1000"),
    ("min_trades_total", "min_trades_total BETWEEN 30 AND 100000"),
    ("min_positive_window_pct", "min_positive_window_pct BETWEEN 50 AND 100"),
    ("min_net_return_pct", "min_net_return_pct BETWEEN 0 AND 1000"),
    ("max_drawdown_pct", "max_drawdown_pct BETWEEN 1 AND 50"),
    ("min_excess_vs_buy_hold_pct", "min_excess_vs_buy_hold_pct BETWEEN 0 AND 1000"),
    ("holdout_pct", "holdout_pct BETWEEN 20 AND 60"),
    ("min_commission_bps", "min_commission_bps BETWEEN 1 AND 200"),
    ("min_slippage_bps", "min_slippage_bps BETWEEN 1 AND 200"),
    ("min_spread_bps", "min_spread_bps BETWEEN 0 AND 200"),
)


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("min_windows", sa.Integer(), nullable=False),
        sa.Column("min_trades_total", sa.Integer(), nullable=False),
        sa.Column("min_positive_window_pct", sa.Float(), nullable=False),
        sa.Column("min_net_return_pct", sa.Float(), nullable=False),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=False),
        sa.Column("min_excess_vs_buy_hold_pct", sa.Float(), nullable=False),
        sa.Column("holdout_pct", sa.Float(), nullable=False),
        sa.Column("min_commission_bps", sa.Float(), nullable=False),
        sa.Column("min_slippage_bps", sa.Float(), nullable=False),
        sa.Column("min_spread_bps", sa.Float(), nullable=False),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("account_id", name="account_evidence_policy_pkey"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["investment_accounts.id"],
            name="account_evidence_policy_account_fkey",
            ondelete="CASCADE",
        ),
        *(
            sa.CheckConstraint(expr, name=f"account_evidence_policy_{col}_ck")
            for col, expr in CHECKS
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        op.drop_table(_TABLE)
