"""V1.87 — lifecycle aggregate lock + per-position sequence_no.

``lifecycle_aggregates`` is the FOR UPDATE target. Events are ordered by
``sequence_no`` (time ``at`` is metadata). UNIQUE(position_id, sequence_no).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "016_lifecycle_sequence"
down_revision = "015_lifecycle_events"
branch_labels = None
depends_on = None

_EVENTS = "lifecycle_events"
_AGG = "lifecycle_aggregates"
_SEQ_COL = "sequence_no"
_SEQ_UIDX = "lifecycle_events_position_seq_uidx"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(
    bind: sa.engine.Connection, table_name: str, column_name: str
) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "c": column_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _AGG):
        op.create_table(
            _AGG,
            sa.Column("position_id", sa.String(), primary_key=True),
            sa.Column("account_id", sa.String(), nullable=False),
            sa.Column(
                "last_sequence_no",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if _table_exists(bind, _EVENTS) and not _column_exists(bind, _EVENTS, _SEQ_COL):
        op.add_column(
            _EVENTS,
            sa.Column(_SEQ_COL, sa.Integer(), nullable=True),
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {_EVENTS} AS e
                SET {_SEQ_COL} = s.rn
                FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY position_id
                               ORDER BY at ASC, created_at ASC, id ASC
                           ) AS rn
                    FROM {_EVENTS}
                ) AS s
                WHERE e.id = s.id
                """
            )
        )
        op.execute(
            sa.text(f"UPDATE {_EVENTS} SET {_SEQ_COL} = 1 WHERE {_SEQ_COL} IS NULL")
        )
        op.alter_column(_EVENTS, _SEQ_COL, nullable=False)

    if _table_exists(bind, _EVENTS) and not _index_exists(bind, _SEQ_UIDX):
        op.create_index(
            _SEQ_UIDX,
            _EVENTS,
            ["position_id", _SEQ_COL],
            unique=True,
        )

    if _table_exists(bind, _EVENTS) and _table_exists(bind, _AGG):
        op.execute(
            sa.text(
                f"""
                INSERT INTO {_AGG} (position_id, account_id, last_sequence_no, created_at)
                SELECT position_id,
                       MIN(account_id) AS account_id,
                       MAX({_SEQ_COL}) AS last_sequence_no,
                       MIN(created_at) AS created_at
                FROM {_EVENTS}
                GROUP BY position_id
                ON CONFLICT (position_id) DO NOTHING
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, _EVENTS) and _index_exists(bind, _SEQ_UIDX):
        op.drop_index(_SEQ_UIDX, table_name=_EVENTS)
    if _table_exists(bind, _EVENTS) and _column_exists(bind, _EVENTS, _SEQ_COL):
        op.drop_column(_EVENTS, _SEQ_COL)
    if _table_exists(bind, _AGG):
        op.drop_table(_AGG)
