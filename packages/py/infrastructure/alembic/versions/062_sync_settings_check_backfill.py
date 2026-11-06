"""062 — ``sync_settings``: backfill del ``CHECK`` de intervalo que la 060 podía no crear.

La ``060`` creaba ``sync_settings_provider_check_interval_check`` dentro del bloque
``if not _column_exists(provider_check_interval_seconds)``. En una base **nueva** la
baseline (``003_prisma_schema_baseline``) ya crea esa columna **desde los metadatos**, así
que la rama no se ejecutaba y el ``CHECK`` quedaba ausente: drift real entre
``Base.metadata`` y la BD, visible en el gate ``SCHEMA_DRIFT_PG_REQUIRED``.

La ``060`` ya está corregida para decidir la creación por la existencia del propio
constraint. Pero una base **heredada** que ya tiene ``alembic_version`` en ``060`` (o
``061``) no vuelve a ejecutar esa revisión: sin esta ``062`` el defecto queda sellado
para siempre. Esta revisión es la única vía de reparación de esas bases.

Idempotente y fail-closed:

* sin tabla o sin columna base ⇒ sale sin marcar daño (base anterior a la política);
* sin el constraint ⇒ lo crea con la definición de la ``060`` (15..3600);
* con el constraint y la definición esperada ⇒ no toca nada (re-ejecutar es un no-op);
* con el constraint y **otra** definición ⇒ aborta: el operador debe decidir, esta
  revisión no sobrescribe un guardrail existente.

``downgrade`` retira solo el constraint (nunca la columna ni la tabla).

Cadena lineal: ``down_revision = "061_profile_delete_restrict"``.
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "062_sync_settings_check_backfill"
down_revision = "061_profile_delete_restrict"
branch_labels = None
depends_on = None

_TABLE = "sync_settings"
_INTERVAL = "provider_check_interval_seconds"
_INTERVAL_CHECK = "sync_settings_provider_check_interval_check"

_INTERVAL_MIN = 15
_INTERVAL_MAX = 3600


def _table_exists(bind: sa.engine.Connection) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE}) is not None


def _column_exists(bind: sa.engine.Connection) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE, "c": _INTERVAL}) is not None


def _check_definition(bind: sa.engine.Connection) -> str | None:
    """Definición canónica del ``CHECK`` en la BD (``None`` si no existe)."""
    sql = sa.text(
        """
        SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        WHERE c.conname = :name
          AND c.contype = 'c'
          AND rel.relname = :table
          AND n.nspname = 'public'
        """
    )
    value = bind.scalar(sql, {"name": _INTERVAL_CHECK, "table": _TABLE})
    return None if value is None else str(value)


def _check_oid(bind: sa.engine.Connection) -> int | None:
    sql = sa.text(
        """
        SELECT c.oid
        FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        WHERE c.conname = :name
          AND c.contype = 'c'
          AND rel.relname = :table
          AND n.nspname = 'public'
        """
    )
    value = bind.scalar(sql, {"name": _INTERVAL_CHECK, "table": _TABLE})
    return None if value is None else int(value)


def _normalize(definition: str) -> str:
    """Forma comparable: sin espacios, paréntesis ni comillas; minúsculas.

    PostgreSQL devuelve ``CHECK (((provider_check_interval_seconds >= 15) AND
    (provider_check_interval_seconds <= 3600)))``; quitando el ruido queda una cadena
    estable con la que distinguir «mismo guardrail» de «guardrail distinto».
    """
    return re.sub(r"[^a-z0-9_<>=]", "", definition.lower())


def expected_definition() -> str:
    """Definición canónica que debe declarar la BD (misma expresión que la ``060``)."""
    return (
        f"check(({_INTERVAL}>={_INTERVAL_MIN})and({_INTERVAL}<={_INTERVAL_MAX}))"
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind) or not _column_exists(bind):
        # Base anterior a la política de comprobación: la baseline crea todo en nuevas.
        return
    definition = _check_definition(bind)
    if definition is None:
        op.create_check_constraint(
            _INTERVAL_CHECK,
            _TABLE,
            f"{_INTERVAL} >= {_INTERVAL_MIN} AND {_INTERVAL} <= {_INTERVAL_MAX}",
        )
        return
    if _normalize(definition) == _normalize(expected_definition()):
        return
    raise RuntimeError(
        "062: el CHECK 'sync_settings_provider_check_interval_check' existe con una "
        f"definición distinta a la esperada ({definition!r}). La revisión NO sobrescribe "
        "un guardrail existente: revisa el esquema y decide a mano. Esquema incompleto: "
        "la revisión NO se marca como aplicada."
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind) or not _column_exists(bind):
        return
    if _check_oid(bind) is None:
        return
    op.drop_constraint(_INTERVAL_CHECK, _TABLE, type_="check")
