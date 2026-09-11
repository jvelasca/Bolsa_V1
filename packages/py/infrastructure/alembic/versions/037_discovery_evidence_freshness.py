"""V2.37 / P2-03 — freshness y fingerprint del snapshot de evidencia.

La auditoría de v2.36 señaló dos carencias del snapshot que alimenta el carril
``adaptive``:

1. **Freshness**: el worker leía ``get_latest()`` sin validar la antigüedad del corte
   ``window_to``, de modo que un snapshot obsoleto podía seguir gobernando el reparto
   indefinidamente. La validación es fail-closed en el worker (snapshot stale ⇒ peso
   adaptativo 0); esta migración aporta el dato que la hace auditable.
2. **Fingerprint**: distinguir *event-time evidence* (cuándo ocurrió cada trial) de
   *research dataset snapshot* (qué conjunto exacto de filas se agregó). Detecta
   reescrituras retrospectivas del dataset.

Aditivo: una columna nullable ``evidence_fingerprint`` en la tabla existente, sin
backfill (los snapshots v0 ya persistidos quedan a ``NULL``: no tenían huella y no se
inventa). Guards idempotentes offline-safe (patrón 030-036).

Cadena lineal: ``down_revision = "036_discovery_evidence_snapshots"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "037_discovery_evidence_freshness"
down_revision = "036_discovery_evidence_snapshots"
branch_labels = None
depends_on = None

_TABLE = "discovery_evidence_snapshots"
_COLUMN = "evidence_fingerprint"


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "c": column_name}) is not None


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if _column_exists(bind, _TABLE, _COLUMN):
        return
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE):
        return
    if not _column_exists(bind, _TABLE, _COLUMN):
        return
    op.drop_column(_TABLE, _COLUMN)
