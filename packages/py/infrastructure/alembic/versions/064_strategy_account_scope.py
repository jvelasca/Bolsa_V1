"""064 — ámbito de CUENTA propio en las promociones de estrategia (M16, auditoría .183).

La auditoría .183 señaló que el runtime AUTO cargaba la estrategia ACTIVE con
``get_active(instrument_id=<cuenta>)``: el identificador de la **cuenta** viajaba como si
fuera el de un **instrumento**. Eso funciona por accidente (la consulta encuentra la fila
sembrada cuya ``instrument_id`` es la cuenta) y rompe el significado de la tabla: una
promoción de instrumento (``inst-v229-…``) y una activa atribuida a una cuenta
(``$ACCOUNT`` de la ventana PAPER) quedan indistinguibles, y cualquier lectura por
instrumento puede devolver la de la cuenta.

Esta revisión añade ``strategy_promotions.account_id`` y su índice:

* ``account_id`` — cuenta que CONDUCE la estrategia. ``NULL`` = ACTIVE de instrumento
  (caso del LAB y de todas las filas anteriores). La columna NO se rellena a partir de
  ``instrument_id``: rellenarla sería volver a confundirlos.
* ``strategy_promotions_account_idx`` — predicado de ``get_active_for_account``
  (``account_id = :cuenta AND promoted``).

Sin backfill a propósito: las filas históricas (``instrument_id = <cuenta>``, semilla de la
ventana) se siguen leyendo por la ruta de compatibilidad del store, que sólo las trata como
cuenta cuando no declaran ninguna. Aditivo y nullable: ningún lector previo cambia.

``downgrade`` retira índice y columna (la tabla y las filas se conservan).

Cadena lineal: ``down_revision = "063_auto_engine_lease"``. El identificador se acorta a
26 caracteres porque viaja a ``alembic_version.version_num`` (``varchar(32)``).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "064_strategy_account_scope"
down_revision = "063_auto_engine_lease"
branch_labels = None
depends_on = None

_PROMOTIONS = "strategy_promotions"
_ACCOUNT_INDEX = "strategy_promotions_account_idx"


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


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _PROMOTIONS):
        # Sin tabla de promociones no hay ámbito que separar (bases anteriores a la 030).
        return
    if not _column_exists(bind, _PROMOTIONS, "account_id"):
        op.add_column(_PROMOTIONS, sa.Column("account_id", sa.String(), nullable=True))
    if not _index_exists(bind, _ACCOUNT_INDEX):
        op.create_index(_ACCOUNT_INDEX, _PROMOTIONS, ["account_id", "promoted"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _PROMOTIONS):
        return
    if _index_exists(bind, _ACCOUNT_INDEX):
        op.drop_index(_ACCOUNT_INDEX, table_name=_PROMOTIONS)
    if _column_exists(bind, _PROMOTIONS, "account_id"):
        op.drop_column(_PROMOTIONS, "account_id")
