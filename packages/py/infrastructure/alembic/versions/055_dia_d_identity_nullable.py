"""055 — ``dia_d_cycle_verifications``: ``instrument_id``/``symbol`` pasan a NULLABLE (hueco).

La identidad del instrumento de un ciclo AUTO puede ser un **hueco declarado**: el resolutor
``resolve_dia_d_cycle_facts`` canoniza el instrumento al id del catálogo cuando lo conoce, pero
sin fila de catálogo conserva el valor crudo y declara el **símbolo ausente** (``None``); y un
ciclo en una etapa temprana puede no sellar todavía la identidad. ``DiaDCycleFacts`` modela ambos
como ``None`` y el caso de uso ``ResolveDiaDCycleVerification`` persiste ese hueco tal cual
(doctrina ``UNKNOWN != 0``: ``None``, nunca ``""``).

Las columnas ``instrument_id``/``symbol`` nacieron ``NOT NULL`` en la 053, así que el hueco se
colapsaba a ``""`` al persistir. Aquí se relajan para que el hueco declarado sobreviva hasta la
fila durable y el consumidor pueda distinguir «no se sabe» de «se sabe y está vacío».

Aditiva e idempotente (comprueba ``is_nullable`` antes de alterar); ``downgrade`` simétrico.

Cadena lineal: ``down_revision = "054_dia_d_verified_and_alerts"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "055_dia_d_identity_nullable"
down_revision = "054_dia_d_verified_and_alerts"
branch_labels = None
depends_on = None

_TABLE = "dia_d_cycle_verifications"
#: Columnas de identidad derivada que pueden viajar como hueco (``NULL``).
_NULLABLE_IDENTITY_COLUMNS = ("instrument_id", "symbol")


def _column_is_nullable(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool | None:
    """``True``/``False`` según ``is_nullable``; ``None`` si la columna no existe."""
    sql = (
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    value = bind.scalar(sa.text(sql), {"t": table_name, "c": column_name})
    return None if value is None else str(value).upper() == "YES"


def _set_identity_nullable(bind: sa.engine.Connection, *, nullable: bool) -> None:
    for column in _NULLABLE_IDENTITY_COLUMNS:
        current = _column_is_nullable(bind, _TABLE, column)
        if current is None or current == nullable:
            continue
        op.alter_column(_TABLE, column, existing_type=sa.String(), nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind()
    _set_identity_nullable(bind, nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    _set_identity_nullable(bind, nullable=False)
