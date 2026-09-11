"""V2.36 (incremento 1) — snapshots de evidencia para el carril ``adaptive``.

V2.35.1 dejó el ``DiscoveryBudgetAllocator`` con un carril ``adaptive`` de peso ``0.0``
(hueco semántico). Esta migración introduce la tabla que persiste el **prior de reparto
de presupuesto** derivado de la evidencia persistida del LAB:

* ``discovery_evidence_snapshots``: una fila por snapshot, con ``snapshot_hash`` (clave
  natural idempotente), ``math_version`` (fórmula reproducible), ventana temporal del
  corte (``window_from``/``window_to``) y ``payload`` JSONB (pesos por familia H0, pesos
  por carril, tamaños de muestra). Inmutable: no se reescribe un hash ya existente.

Aditivo: tabla nueva, sin tocar tablas previas y sin backfill (no había snapshots antes;
no se inventa). Guards idempotentes offline-safe (patrón 030/031/032/034/035).

Cadena lineal: ``down_revision = "035_paper_forward_evidence"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "036_discovery_evidence_snapshots"
down_revision = "035_paper_forward_evidence"
branch_labels = None
depends_on = None

_TABLE = "discovery_evidence_snapshots"
_HASH_IDX = "discovery_evidence_snapshots_hash_idx"
_CREATED_IDX = "discovery_evidence_snapshots_created_idx"


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
    if _table_exists(bind, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("snapshot_hash", sa.String(), nullable=False),
        sa.Column("math_version", sa.String(), nullable=False),
        sa.Column("window_from", sa.String(), nullable=True),
        sa.Column("window_to", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(_HASH_IDX, _TABLE, ["snapshot_hash"], unique=True)
    op.create_index(_CREATED_IDX, _TABLE, ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if _index_exists(bind, _HASH_IDX):
        op.drop_index(_HASH_IDX, table_name=_TABLE)
    if _index_exists(bind, _CREATED_IDX):
        op.drop_index(_CREATED_IDX, table_name=_TABLE)
    op.drop_table(_TABLE)
