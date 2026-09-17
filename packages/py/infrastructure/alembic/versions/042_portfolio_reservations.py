"""AUTO-1 — reservas explícitas de cartera + índice por ``(account_id, status)``.

Cierra el hueco que dejó declarado V2.40.4/AUTO-1A: la reserva de cartera era
**intra-tick y anónima** (``committed[]`` + ``_working_snapshot`` dentro de
``plan_v2_tick``), moría al volver de la función y nadie la liberaba ni la auditaba.
AUTO-1a materializó esa reserva como objeto: un ``ReservationLedger`` puro con identidad,
dimensiones comprometidas, ciclo de vida (fill/cancelación/reinicio/rollback) y ``replay``.
Esta migración le da el espejo durable, **aditivo y sin backfill**:

1. ``portfolio_reservations`` — la reserva tal y como la decide el tick (identidad +
   siete dimensiones + coste + ciclo de vida + ``lease_generation``). Espejo 1:1 de
   ``PortfolioReservationRow`` (``tables.py``). Sin fila ⇒ no hay reserva: la ausencia
   es información, y el worker cae a la reconciliación de arranque desde
   ``execution_events`` (que sigue existiendo).
2. Índices de lectura del libro por cuenta (``status``, ``sector`` y ``created_at`` DESC).
3. **El índice que faltaba** en ``execution_events``: ``(account_id, status)``. Las dos
   lecturas del libro de órdenes — ``list_applied`` (V2.40.5: la posición es Σ ``APPLIED``)
   y ``list_unapplied`` (V2.40.4: capital en vuelo) — filtran por cuenta y estado y
   quedaban acotadas solo por ``LIMIT``. Deuda declarada en el audit-pack de V2.40.4 §5.1
   y en V2.40.5 §5.2, con la migración asignada explícitamente a AUTO-1.

Sobre el shape del índice de ``execution_events``: el roadmap lo llamó "índice parcial
``(account_id, status)``" y aquí se crea **plano**, a propósito. Un índice parcial
(``WHERE status <> 'APPLIED'``) dejaría fuera justamente la lectura de ``APPLIED``, que es
la autoridad de posición desde V2.40.5; con la columna ``status`` como segunda clave, el
mismo índice sirve a las dos consultas (``status = 'APPLIED'`` y ``status IN (...)``) sin
duplicar estructura. El nombre es el mismo en los dos casos, así que el roundtrip del test
que verifica presencia/ausencia no depende de esta decisión, y queda declarada aquí.

Convenciones del repo (paridad 1:1 con ``tables.py``): ``String`` para estados/lados,
``Numeric(18,6)`` para cantidades, precios y dimensiones monetarias, ``Float`` para
coeficientes (``correlation``/``*_capacity``), ``DateTime(timezone=True)`` para instantes,
guards idempotentes offline-safe (patrón 028–041).

El baseline ``003_prisma_schema_baseline`` **no** copia los ``Index`` de ``__table_args__``
(solo FK y ``UniqueConstraint``), así que los tres índices de la tabla nueva y el de
``execution_events`` se crean **explícitamente aquí**.

Cadena lineal: ``down_revision = "041_unique_natural_keys"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "042_portfolio_reservations"
down_revision = "041_unique_natural_keys"
branch_labels = None
depends_on = None

_TABLE = "portfolio_reservations"
_ACCOUNT_STATUS_IDX = "portfolio_reservations_account_status_idx"
_ACCOUNT_SECTOR_IDX = "portfolio_reservations_account_sector_idx"
_ACCOUNT_CREATED_IDX = "portfolio_reservations_account_created_idx"

_EVENTS = "execution_events"
_EVENTS_ACCOUNT_STATUS_IDX = "execution_events_account_status_idx"

# Dimensiones monetarias de la reserva (Numeric(18,6), paridad con el resto de importes).
_MONEY_COLUMNS: tuple[str, ...] = (
    "quantity",
    "entry",
    "stop",
    "reserved_cash",
    "reserved_risk",
    "asset_exposure",
    "sector_exposure",
)

# Coeficientes declarados por la reserva (no son dinero).
_FLOAT_COLUMNS: tuple[str, ...] = (
    "correlation",
    "strategy_capacity",
    "liquidity_capacity",
)

# Identidad y dimensiones opcionales: la reserva es usable con lo que se conozca.
_STRING_COLUMNS: tuple[str, ...] = (
    "tick_id",
    "instrument_id",
    "sector",
    "strategy_version_id",
)


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "c": column_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def _create_table(bind: sa.engine.Connection) -> None:
    """Crea ``portfolio_reservations`` si falta (idempotente y offline-safe)."""
    if _table_exists(bind, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("reservation_id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), nullable=True),
        *(sa.Column(name, sa.String(), nullable=True) for name in _STRING_COLUMNS),
        sa.Column("side", sa.String(16), nullable=True),
        *(sa.Column(name, sa.Numeric(18, 6), nullable=True) for name in _MONEY_COLUMNS),
        *(sa.Column(name, sa.Float(), nullable=True) for name in _FLOAT_COLUMNS),
        # ``TradingCost.to_dict()`` (comisión/spread/slippage/gap + pérdidas derivadas).
        # NULL = no se pudo cuantificar: ausencia de coste NO es coste 0 (fail-closed).
        sa.Column("cost", JSONB, nullable=True),
        sa.Column(
            "status",
            # 32 y no 16: los estados reales del ciclo de vida son más largos que eso
            # (``RELEASED_BY_RESTART``/``RELEASED_BY_CANCEL``/``RELEASED_BY_ROLLBACK``),
            # y ``String(16)`` abortaba la liberación en PostgreSQL con
            # ``StringDataRightTruncation`` — el store tiene que poder persistir el
            # estado que el libro puro ya decidió.
            sa.String(32),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.String(), nullable=True),
        sa.Column(
            "released_qty",
            sa.Numeric(18, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "remaining_qty",
            sa.Numeric(18, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "lease_generation",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1) La reserva durable (espejo de PortfolioReservationRow) ──────────────
    _create_table(bind)

    # ── 2) Lecturas del libro: "vivas de esta cuenta", "sector de esta cuenta",
    #       "las últimas de esta cuenta" (la más reciente primero).
    if _table_exists(bind, _TABLE):
        if not _index_exists(bind, _ACCOUNT_STATUS_IDX):
            op.create_index(_ACCOUNT_STATUS_IDX, _TABLE, ["account_id", "status"])
        if not _index_exists(bind, _ACCOUNT_SECTOR_IDX):
            op.create_index(_ACCOUNT_SECTOR_IDX, _TABLE, ["account_id", "sector"])
        if not _index_exists(bind, _ACCOUNT_CREATED_IDX):
            op.create_index(
                _ACCOUNT_CREATED_IDX,
                _TABLE,
                ["account_id", sa.text("created_at DESC")],
            )

    # ── 3) El índice que faltaba en execution_events (deuda declarada en V2.40.4) ──
    if _table_exists(bind, _EVENTS) and not _index_exists(bind, _EVENTS_ACCOUNT_STATUS_IDX):
        if _column_exists(bind, _EVENTS, "account_id") and _column_exists(
            bind, _EVENTS, "status"
        ):
            op.create_index(
                _EVENTS_ACCOUNT_STATUS_IDX,
                _EVENTS,
                ["account_id", "status"],
            )


def downgrade() -> None:
    """Retira lo que creó esta migración: primero los índices, después la tabla.

    Simétrico por construcción: el baseline ``003`` no crea índices (ver docstring), así
    que los cuatro nombres de este upgrade son de la 042 y ninguno está respaldado por una
    constraint; ``DROP INDEX`` es seguro sin la danza de ``DependentObjectsStillExist`` que
    necesita la 041.
    """
    bind = op.get_bind()

    if _table_exists(bind, _EVENTS) and _index_exists(bind, _EVENTS_ACCOUNT_STATUS_IDX):
        op.drop_index(_EVENTS_ACCOUNT_STATUS_IDX, table_name=_EVENTS)

    if _table_exists(bind, _TABLE):
        for index_name in (_ACCOUNT_CREATED_IDX, _ACCOUNT_SECTOR_IDX, _ACCOUNT_STATUS_IDX):
            if _index_exists(bind, index_name):
                op.drop_index(index_name, table_name=_TABLE)
        op.drop_table(_TABLE)
