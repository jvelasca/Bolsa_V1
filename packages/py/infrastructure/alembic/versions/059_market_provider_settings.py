"""059 — ``market_provider_settings``: configuración durable de proveedores.

Los proveedores de datos (``yahoo``, ``xtb``) se configuraban **solo** por entorno
(``XTB_BRIDGE_URL``) o estaban fijados en código (Yahoo siempre activo y declarado sano).
Eso hacía imposible habilitar/deshabilitar un proveedor, cambiar su prioridad o su throttle
desde la aplicación, y obligaba a reiniciar el proceso para cualquier cambio.

Esta tabla es la configuración efectiva, una fila por proveedor:

* ``enabled`` — si el proveedor puede usarse. Deshabilitado ⇒ no se encola ni se sincroniza
  y el motivo se declara; nunca se cae a él en silencio.
* ``priority`` — orden de intento por capacidad (menor primero). Hoy hay un proveedor por
  capacidad, pero el contrato queda fijado para cuando haya más.
* ``min_interval_seconds`` — throttle mínimo entre peticiones.
* ``base_url`` — URL del bridge (solo XTB; Yahoo no la admite).
* ``options`` — JSONB aditivo para ajustes que no merecen columna propia.
* ``last_check_*`` — resultado de la última verificación explícita («Probar conexión»).
  Sin fila de verificación, el estado es «sin verificar»: no se afirma disponibilidad.

Restricciones ``CHECK`` en rango: la base de datos es la última defensa si algún camino
escribe sin pasar por el caso de uso (misma doctrina que las claves naturales).

Aditiva e idempotente (comprueba existencia antes de crear); ``downgrade`` simétrico.

Cadena lineal: ``down_revision = "058_estudio_daily_proposals"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "059_market_provider_settings"
down_revision = "058_estudio_daily_proposals"
branch_labels = None
depends_on = None

_TABLE = "market_provider_settings"
_PRIORITY_CHECK = "market_provider_settings_priority_check"
_INTERVAL_CHECK = "market_provider_settings_interval_check"


def _table_exists(bind: sa.engine.Connection) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE}) is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("min_interval_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("base_url", sa.String(), nullable=True),
        sa.Column(
            "options",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_ok", sa.Boolean(), nullable=True),
        sa.Column("last_check_message", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("priority >= 0 AND priority <= 100", name=_PRIORITY_CHECK),
        sa.CheckConstraint(
            "min_interval_seconds >= 0 AND min_interval_seconds <= 120",
            name=_INTERVAL_CHECK,
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    op.drop_table(_TABLE)
