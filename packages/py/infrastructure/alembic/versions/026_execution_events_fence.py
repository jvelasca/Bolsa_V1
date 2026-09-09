"""V2.21 / A8 (M1 · fencing estructural P1-01b) — token de lease `lease_generation`.

Cierra el hueco de fencing audita: un worker cuyo ``APPLYING`` ha sido robado
(reclaim por otro tras caducar su lease) podía, al terminar tarde, hacer
``mark_applied``/``mark_failed``/``mark_retry`` **sin demostrar que seguía siendo
el dueño**. Ese terminal incondicionado rompe la propiedad "single owner durante
toda la vida del APPLYING".

La 025 introdujo ``lease_owner`` + ``updated_at`` (reloj de caducidad) pero ese
reloj SOLO autoriza un reclaim; no basta para que un dueño viejo pruebe que su
lease no fue revocada. Añadimos un **token monótono** ``lease_generation``:
cada adquisición (``start_apply``) y cada ROBO (``reclaim_stale_apply``) lo
INCREMENTA. Un terminal con fencing exige ``lease_owner`` + ``lease_generation``
coincidentes con la fila: si otra instancia robó (bump) la generación, el
``UPDATE ... WHERE lease_generation = :viejo`` hace 0 filas → el dueño antiguo
NO puede finalizar una lease ajena.

* Aditivo, ``NOT NULL DEFAULT 0`` (filas pre-existentes quedan en la generación 0:
  su lease, si la tuvieran APPLYING sin fence, no es verificable → el regain por
  reclaim las encamina a terminal preferido en ``reap_stale_applying``).
* Guards por tabla/columna estilo 022-025 (offline-safe, sin imports ORM).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "026_execution_events_fence"
down_revision = "025_execution_events_lease"
branch_labels = None
depends_on = None

_EXEC = "execution_events"
_COL = "lease_generation"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table, "c": column}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _EXEC):
        return
    if not _column_exists(bind, _EXEC, _COL):
        op.add_column(
            _EXEC,
            sa.Column(
                _COL,
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _EXEC):
        return
    if _column_exists(bind, _EXEC, _COL):
        # Forward-only con execution history (fencing); admite drop en scratch/dev.
        op.drop_column(_EXEC, _COL)
