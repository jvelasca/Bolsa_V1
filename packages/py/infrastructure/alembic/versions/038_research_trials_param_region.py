"""V2.38 (incremento 3) — region de parametros por trial.

La evidencia adaptativa de V2.36/V2.37 se agregaba por **familia** (``preset_key``). El
incremento 3 introduce la primera dimension de granularidad **derivable** hoy: la
**region de parametros** dentro del grid de una familia, calculada de forma determinista
y versionada (``discovery_param_region_v0``) al emitir la candidata.

Aditivo: una columna nullable ``param_region`` en ``research_trials``, sin backfill (los
trials historicos quedan a ``NULL``: no se inventa la region de corridas pasadas, y la
agregacion sin region sigue siendo exactamente la de antes). Guards idempotentes
offline-safe (patron 030-037).

Por que NO se incluyen regimen ni clase de instrumento: no existen hoy como dato
persistido (ver docstring de ``bolsa_application.discovery_param_region``). Anadirlos
requeriria primero persistirlos como fuente de verdad.

Cadena lineal: ``down_revision = "037_discovery_evidence_freshness"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "038_research_trials_param_region"
down_revision = "037_discovery_evidence_freshness"
branch_labels = None
depends_on = None

_TABLE = "research_trials"
_COLUMN = "param_region"


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
