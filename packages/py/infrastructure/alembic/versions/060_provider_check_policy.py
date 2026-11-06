"""060 — ``sync_settings``: política de comprobación periódica de servidores.

La comprobación de proveedores (Yahoo / XTB) se lanzaba cada 60 s con el intervalo
**fijo en código** (``PROVIDER_HEALTH_MAX_AGE_SECONDS``) y sin interruptor: el operador
no podía apagarla ni cambiar su cadencia, y el nombre «auto-actualización en segundo
plano» de ``auto_sync_enabled`` invitaba a creer que ese toggle ya probaba servidores
(cuando solo encola y descarga velas OHLCV).

Esta revisión fija la política en la misma fila única de ``sync_settings`` que ya
gobierna la sincronización de velas — una sola configuración de automatización, con dos
bloques rotulados en la UI:

* ``provider_check_enabled`` — interruptor de la comprobación periódica. OFF ⇒ no se
  sondea automáticamente; el estado mostrado es la última medición persistida. Las
  comprobaciones manuales («Comprobar ahora») siguen permitidas.
* ``provider_check_interval_seconds`` — cadencia en segundos (15..3600). El bucle del
  proceso API late cada 10 s y comprueba cuando el dato persistido ha vencido.

Restricción ``CHECK`` de rango: la base de datos es la última defensa si algún camino
escribe sin pasar por el caso de uso (misma doctrina que la ``059``).

Aditiva e idempotente (comprueba existencia de tabla/columna/constraint antes de tocar);
``downgrade`` simétrico.

Idempotencia del ``CHECK`` declarada: la baseline (``003_prisma_schema_baseline``) crea
``sync_settings`` **desde los metadatos**, que ya incluyen la columna del intervalo. Por
eso la columna puede existir al llegar aquí y aun así faltar el ``CHECK``. Crearlo dentro
de ``if not _column_exists(...)`` lo ataba a un caso que no se da en bases nuevas y lo
dejaba ausente (drift real observado). Ahora la creación del ``CHECK`` se decide por su
propia existencia, no por la de la columna.

Cadena lineal: ``down_revision = "059_market_provider_settings"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "060_provider_check_policy"
down_revision = "059_market_provider_settings"
branch_labels = None
depends_on = None

_TABLE = "sync_settings"
_ENABLED = "provider_check_enabled"
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


def _column_exists(bind: sa.engine.Connection, column: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": _TABLE, "c": column}) is not None


def _constraint_exists(bind: sa.engine.Connection) -> bool:
    sql = (
        "SELECT 1 FROM pg_constraint WHERE conname = :n"  # noqa: S608 — nombre literal
    )
    return bind.scalar(sa.text(sql), {"n": _INTERVAL_CHECK}) is not None


def assert_base_table_present(table_exists: bool) -> None:
    """Aborta si falta ``sync_settings``: es prerrequisito obligatorio, no un caso opcional.

    La tabla nace en la baseline (``003_prisma_schema_baseline``). Un ``return``
    silencioso marcaría la revisión como aplicada **sin** las columnas de política y el
    lector (``SqlAlchemySyncSchedulerRepository``) fallaría después al seleccionarlas.
    Falla cerrado y no fabrica nada.
    """
    if table_exists:
        return
    raise RuntimeError(
        "060: falta la tabla base 'sync_settings'; la crea la baseline "
        "(003_prisma_schema_baseline) y es prerrequisito obligatorio de la cadena. "
        "Esquema incompleto: la revisión NO se marca como aplicada."
    )


def upgrade() -> None:
    bind = op.get_bind()
    assert_base_table_present(_table_exists(bind))
    if not _column_exists(bind, _ENABLED):
        op.add_column(
            _TABLE,
            sa.Column(_ENABLED, sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if not _column_exists(bind, _INTERVAL):
        op.add_column(
            _TABLE,
            sa.Column(
                _INTERVAL,
                sa.Integer(),
                nullable=False,
                server_default="60",
            ),
        )
    # Fuera del bloque de la columna: en bases nuevas la columna ya viene de la baseline
    # y el CHECK seguía ausente. Se decide por la existencia del propio constraint.
    if not _constraint_exists(bind):
        op.create_check_constraint(
            _INTERVAL_CHECK,
            _TABLE,
            f"{_INTERVAL} >= {_INTERVAL_MIN} AND {_INTERVAL} <= {_INTERVAL_MAX}",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        # Asimetría declarada: sin tabla no hay columnas que retirar.
        return
    if _column_exists(bind, _INTERVAL):
        if _constraint_exists(bind):
            op.drop_constraint(_INTERVAL_CHECK, _TABLE, type_="check")
        op.drop_column(_TABLE, _INTERVAL)
    if _column_exists(bind, _ENABLED):
        op.drop_column(_TABLE, _ENABLED)
