"""JP-1 — hot scalar columns on ``position_states`` (dual-write from JSONB).

Idempotente: omite columnas ya existentes. Backfill desde ``position_state``
camelCase keys (``direction``, ``currentStop``, ``remainingQuantity``,
``quantity``, ``initialStop``, ``actualEntry``).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012_position_state_hot_columns"
down_revision = "011_position_states"
branch_labels = None
depends_on = None

_TABLE = "position_states"

_HOT_COLUMNS: tuple[tuple[str, sa.types.TypeEngine[object]], ...] = (
    ("direction", sa.String()),
    ("current_stop", sa.Numeric(18, 6)),
    ("remaining_quantity", sa.Numeric(18, 6)),
    ("quantity", sa.Numeric(18, 6)),
    ("initial_stop", sa.Numeric(18, 6)),
    ("actual_entry", sa.Numeric(18, 6)),
)


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "c": column_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return

    for col_name, col_type in _HOT_COLUMNS:
        if not _column_exists(bind, _TABLE, col_name):
            op.add_column(_TABLE, sa.Column(col_name, col_type, nullable=True))

    # Backfill only where hot column is still NULL (idempotent re-run safe).
    bind.execute(
        sa.text(
            f"""
            UPDATE {_TABLE}
            SET
              direction = COALESCE(
                direction,
                NULLIF(position_state->>'direction', '')
              ),
              current_stop = COALESCE(
                current_stop,
                NULLIF(position_state->>'currentStop', '')::numeric
              ),
              remaining_quantity = COALESCE(
                remaining_quantity,
                NULLIF(position_state->>'remainingQuantity', '')::numeric
              ),
              quantity = COALESCE(
                quantity,
                NULLIF(position_state->>'quantity', '')::numeric
              ),
              initial_stop = COALESCE(
                initial_stop,
                NULLIF(position_state->>'initialStop', '')::numeric
              ),
              actual_entry = COALESCE(
                actual_entry,
                NULLIF(position_state->>'actualEntry', '')::numeric
              )
            WHERE
              direction IS NULL
              OR current_stop IS NULL
              OR remaining_quantity IS NULL
              OR quantity IS NULL
              OR initial_stop IS NULL
              OR actual_entry IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    for col_name, _ in reversed(_HOT_COLUMNS):
        if _column_exists(bind, _TABLE, col_name):
            op.drop_column(_TABLE, col_name)
