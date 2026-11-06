"""061 — ``investment_accounts.active_profile_id``: FK ``ON DELETE RESTRICT`` (AUD-03).

El catálogo ART-PROFILE nació con ``ON DELETE SET NULL``: borrar un perfil desasignaba
en silencio las cuentas que lo usaban, incluso si el ``DELETE`` llegaba por SQL directo
o entre el recuento y el borrado del caso de uso (ventana TOCTOU). El guard de la
aplicación vive ahora en el repositorio bajo bloqueo de fila
(``delete_if_unused``); esta revisión pone el backstop en la base de datos: la FK
**RESTRICT** hace imposible dejar una cuenta apuntando a un perfil inexistente.

Idempotente: si la FK ya es ``RESTRICT`` (``pg_constraint.confdeltype = 'r'``) no toca
nada. Si la tabla o la columna no existen (base anterior al catálogo) sale sin marcar
daño: la baseline (``003_prisma_schema_baseline``) ya crea la FK correcta en bases
nuevas. ``downgrade`` devuelve la semántica anterior (``SET NULL``).

Cadena lineal: ``down_revision = "060_provider_check_policy"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "061_profile_delete_restrict"
down_revision = "060_provider_check_policy"
branch_labels = None
depends_on = None

_TABLE = "investment_accounts"
_COLUMN = "active_profile_id"
_FK = "investment_accounts_active_profile_id_fkey"
_REFERENCED_TABLE = "investor_profiles"


def _table_exists(bind: sa.engine.Connection, table: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table}) is not None


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table, "c": column}) is not None


def _fk_delete_action(bind: sa.engine.Connection) -> str | None:
    """``confdeltype`` de la FK (``r`` = RESTRICT, ``n`` = SET NULL) o ``None``.

    Devuelve ``None`` cuando el constraint no existe, no es una FK de esa columna o
    apunta a otra tabla: en esos casos la revisión no improvisa un ``DROP`` ciego.
    """
    sql = sa.text(
        """
        SELECT c.confdeltype
        FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_class frel ON frel.oid = c.confrelid
        JOIN pg_attribute att ON att.attrelid = c.conrelid AND att.attnum = c.conkey[1]
        WHERE c.conname = :fk
          AND c.contype = 'f'
          AND rel.relname = :table
          AND frel.relname = :ref_table
          AND att.attname = :column
        """
    )
    value = bind.scalar(
        sql,
        {
            "fk": _FK,
            "table": _TABLE,
            "ref_table": _REFERENCED_TABLE,
            "column": _COLUMN,
        },
    )
    return None if value is None else str(value)


def _replace_fk(bind: sa.engine.Connection, ondelete: str) -> None:
    """Recrea la FK con ``ON DELETE <ondelete>`` (nombre y columna estables)."""
    if _fk_delete_action(bind) is not None:
        op.drop_constraint(_FK, _TABLE, type_="foreignkey")
    op.create_foreign_key(
        _FK,
        _TABLE,
        _REFERENCED_TABLE,
        [_COLUMN],
        ["id"],
        ondelete=ondelete,
        onupdate="CASCADE",
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE) or not _table_exists(bind, _REFERENCED_TABLE):
        # Base sin catálogo (anterior a 20260723020000): la baseline crea la FK correcta.
        return
    if not _column_exists(bind, _TABLE, _COLUMN):
        return
    if _fk_delete_action(bind) == "r":
        return
    _replace_fk(bind, "RESTRICT")


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, _TABLE) or not _table_exists(bind, _REFERENCED_TABLE):
        return
    if not _column_exists(bind, _TABLE, _COLUMN):
        return
    if _fk_delete_action(bind) == "n":
        return
    _replace_fk(bind, "SET NULL")
