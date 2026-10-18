"""056 — ``auto_ops_jobs``: cola durable de trabajos operativos de servidor.

La generación diaria del universo ESTUDIO y la ejecución manual del sandbox DÍA-D AUTO
necesitan un estado **observable** (encolado, en curso con progreso, completado con
resultado, fallido con motivo) y una **idempotencia** por ``(kind, cuenta, día)`` que
impida dos corridas activas del mismo trabajo.

La idempotencia se implementa con un índice único **parcial**
(``status IN ('queued','running')``): un job terminado libera el hueco y permite una
reejecución manual declarada. ``account_id`` puede ser ``NULL`` (trabajo de sistema);
``coalesce(account_id, '')`` lo incluye en la clave sin depender de
``NULLS NOT DISTINCT``.

Aditiva e idempotente (comprueba existencia antes de crear); ``downgrade`` simétrico.

Cadena lineal: ``down_revision = "055_dia_d_identity_nullable"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "056_auto_ops_jobs"
down_revision = "055_dia_d_identity_nullable"
branch_labels = None
depends_on = None

_TABLE = "auto_ops_jobs"
_ACTIVE_KEY = "auto_ops_jobs_active_job_key"


def _table_exists(bind: sa.engine.Connection) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("day", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=True),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "progress",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "result",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("auto_ops_jobs_kind_day_idx", _TABLE, ["kind", "day"])
    op.create_index(
        "auto_ops_jobs_account_created_idx",
        _TABLE,
        ["account_id", "created_at"],
    )
    op.execute(
        f"CREATE UNIQUE INDEX {_ACTIVE_KEY} ON {_TABLE} "
        "(kind, coalesce(account_id, ''), day) "
        "WHERE status IN ('queued', 'running')"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    op.execute(f"DROP INDEX IF EXISTS {_ACTIVE_KEY}")
    op.drop_index("auto_ops_jobs_account_created_idx", table_name=_TABLE)
    op.drop_index("auto_ops_jobs_kind_day_idx", table_name=_TABLE)
    op.drop_table(_TABLE)
