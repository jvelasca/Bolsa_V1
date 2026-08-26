"""DEX-3 — ``operational_incidents`` (ADR-035 resolución recon / V1.13).

Workflow humano: open → in_review → resolved → cleared. Sin auto-heal.
Idempotente: omite tabla/índices si ya existen.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "014_operational_incidents"
down_revision = "013_submit_intents"
branch_labels = None
depends_on = None

_TABLE = "operational_incidents"
_ACTIVE_IDX = "operational_incidents_active_account_kind_idx"
_ACCOUNT_IDX = "operational_incidents_account_id_idx"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(_ACCOUNT_IDX, _TABLE, ["account_id"])
    op.create_index(
        _ACTIVE_IDX,
        _TABLE,
        ["account_id", "kind"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'in_review', 'resolved')"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if _index_exists(bind, _ACTIVE_IDX):
        op.drop_index(_ACTIVE_IDX, table_name=_TABLE)
    if _index_exists(bind, _ACCOUNT_IDX):
        op.drop_index(_ACCOUNT_IDX, table_name=_TABLE)
    op.drop_table(_TABLE)
