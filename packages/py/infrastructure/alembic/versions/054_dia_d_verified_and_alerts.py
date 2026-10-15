"""v111 — Evidencia DÍA-D resuelta por servidor + ownership y outbox de alertas.

Tres bloques aditivos, idempotentes y con ``downgrade`` simétrico:

1. ``dia_d_cycle_verifications`` — se añaden ``facts_hash`` (hash del snapshot de hechos
   durables que respalda la verificación) y ``verified_by`` (actor humano). La clave natural
   pasa de ``(cycle_id, dia_d, end_date, mode)`` a ``(account_id, cycle_id, dia_d, end_date,
   mode)``: una verificación de OTRA cuenta con el mismo ciclo NO puede sobrescribirse.
2. ``signal_alert_subscriptions`` — ``account_id`` (ownership) + columnas de *claim* atómico
   (``processing_bar_timestamp``/``processing_token``/``processing_started_at``).
3. ``alert_deliveries`` — patrón OUTBOX: una fila por ``(subscription_id, bar_timestamp,
   channel)`` con estado/reintento, para que un fallo de SMTP/webhook no se confunda con una
   entrega realizada.

**Seguridad de la restricción nueva.** La clave antigua es un PREFIJO de la nueva, así que
ninguna fila existente puede violarla (la nueva admite un superconjunto de combinaciones). La
migración sólo detecta y **remite** (falla con mensaje) la ambigüedad de OWNERSHIP real: un
mismo ``cycle_id`` con ventanas distintas y ``account_id`` distintos, que exigiría decisión
humana antes de imponer el aislamiento.

Cadena lineal: ``down_revision = "053_dia_d_cycle_verifications"``.

**Límite de Alembic.** ``revision`` viaja a ``alembic_version.version_num`` (``varchar(32)``), así
que el identificador **no puede superar 32 caracteres** (lección de ``v2.88.72`` → ``v2.88.73``);
por eso se acorta a ``054_dia_d_verified_and_alerts`` y el test hermético lo fija.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "054_dia_d_verified_and_alerts"
down_revision = "053_dia_d_cycle_verifications"
branch_labels = None
depends_on = None

_DIA_D = "dia_d_cycle_verifications"
_DIA_D_KEY = "dia_d_cycle_verifications_cycle_key"
_DIA_D_OLD_KEY = "dia_d_cycle_verifications_cycle_key"

_ALERTS = "signal_alert_subscriptions"
_DELIVERIES = "alert_deliveries"


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    sql = (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "c": column_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def _constraint_exists(bind: sa.engine.Connection, table_name: str, name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE table_schema = 'public' AND table_name = :t AND constraint_name = :n"
    )
    return bind.scalar(sa.text(sql), {"t": table_name, "n": name}) is not None


def _unique_columns(bind: sa.engine.Connection, table_name: str, name: str) -> list[str]:
    sql = (
        "SELECT kcu.column_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON tc.constraint_name = kcu.constraint_name "
        " AND tc.table_schema = kcu.table_schema "
        "WHERE tc.table_schema = 'public' AND tc.table_name = :t "
        "  AND tc.constraint_name = :n "
        "ORDER BY kcu.ordinal_position"
    )
    return [row[0] for row in bind.execute(sa.text(sql), {"t": table_name, "n": name}).fetchall()]


def _upgrade_dia_d(bind: sa.engine.Connection) -> None:
    if not _table_exists(bind, _DIA_D):
        return
    if not _column_exists(bind, _DIA_D, "facts_hash"):
        op.add_column(_DIA_D, sa.Column("facts_hash", sa.String(), nullable=True))
    if not _column_exists(bind, _DIA_D, "verified_by"):
        op.add_column(_DIA_D, sa.Column("verified_by", sa.String(), nullable=True))

    # Ambigüedad de OWNERSHIP real (mismo ciclo, ventanas distintas, cuentas distintas): se
    # remite a decisión humana en vez de imponer el aislamiento sobre datos contradictorios.
    ambiguous = bind.scalar(
        sa.text(
            "SELECT count(*) FROM ("
            "  SELECT cycle_id FROM dia_d_cycle_verifications "
            "  GROUP BY cycle_id "
            "  HAVING count(DISTINCT coalesce(account_id, '')) > 1"
            ") AS t"
        )
    )
    if ambiguous:
        raise RuntimeError(
            "054: hay ciclos DÍA-D verificados por varias cuentas "
            f"({int(ambiguous)}); remite a decisión humana antes de imponer el aislamiento"
        )

    wanted = ["account_id", "cycle_id", "dia_d", "end_date", "mode"]
    if _constraint_exists(bind, _DIA_D, _DIA_D_KEY):
        if _unique_columns(bind, _DIA_D, _DIA_D_KEY) == wanted:
            return
        op.drop_constraint(_DIA_D_KEY, _DIA_D, type_="unique")
    op.create_unique_constraint(_DIA_D_KEY, _DIA_D, wanted)


def _downgrade_dia_d(bind: sa.engine.Connection) -> None:
    if not _table_exists(bind, _DIA_D):
        return
    old = ["cycle_id", "dia_d", "end_date", "mode"]
    if _constraint_exists(bind, _DIA_D, _DIA_D_KEY):
        if _unique_columns(bind, _DIA_D, _DIA_D_KEY) != old:
            op.drop_constraint(_DIA_D_KEY, _DIA_D, type_="unique")
            op.create_unique_constraint(_DIA_D_KEY, _DIA_D, old)
    if _column_exists(bind, _DIA_D, "verified_by"):
        op.drop_column(_DIA_D, "verified_by")
    if _column_exists(bind, _DIA_D, "facts_hash"):
        op.drop_column(_DIA_D, "facts_hash")


def _upgrade_alerts(bind: sa.engine.Connection) -> None:
    if _table_exists(bind, _ALERTS):
        if not _column_exists(bind, _ALERTS, "account_id"):
            op.add_column(_ALERTS, sa.Column("account_id", sa.String(), nullable=True))
        if not _index_exists(bind, "signal_alert_subscriptions_account_id_idx"):
            op.create_index(
                "signal_alert_subscriptions_account_id_idx", _ALERTS, ["account_id"]
            )
        if not _column_exists(bind, _ALERTS, "processing_bar_timestamp"):
            op.add_column(
                _ALERTS, sa.Column("processing_bar_timestamp", sa.String(), nullable=True)
            )
        if not _column_exists(bind, _ALERTS, "processing_token"):
            op.add_column(_ALERTS, sa.Column("processing_token", sa.String(), nullable=True))
        if not _column_exists(bind, _ALERTS, "processing_started_at"):
            op.add_column(
                _ALERTS,
                sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
            )

    if not _table_exists(bind, _DELIVERIES):
        op.create_table(
            _DELIVERIES,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "subscription_id",
                sa.String(),
                sa.ForeignKey("signal_alert_subscriptions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("account_id", sa.String(), nullable=True),
            sa.Column("bar_timestamp", sa.String(), nullable=False),
            sa.Column("signal_kind", sa.String(), nullable=True),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=True),
            sa.Column("last_error", sa.String(), nullable=True),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "subscription_id",
                "bar_timestamp",
                "channel",
                name="alert_deliveries_subscription_bar_channel_key",
            ),
        )
        op.create_index("alert_deliveries_account_id_idx", _DELIVERIES, ["account_id"])
        op.create_index(
            "alert_deliveries_status_retry_idx", _DELIVERIES, ["status", "next_retry_at"]
        )


def _downgrade_alerts(bind: sa.engine.Connection) -> None:
    if _table_exists(bind, _DELIVERIES):
        if _index_exists(bind, "alert_deliveries_status_retry_idx"):
            op.drop_index("alert_deliveries_status_retry_idx", table_name=_DELIVERIES)
        if _index_exists(bind, "alert_deliveries_account_id_idx"):
            op.drop_index("alert_deliveries_account_id_idx", table_name=_DELIVERIES)
        op.drop_table(_DELIVERIES)

    if _table_exists(bind, _ALERTS):
        if _column_exists(bind, _ALERTS, "processing_started_at"):
            op.drop_column(_ALERTS, "processing_started_at")
        if _column_exists(bind, _ALERTS, "processing_token"):
            op.drop_column(_ALERTS, "processing_token")
        if _column_exists(bind, _ALERTS, "processing_bar_timestamp"):
            op.drop_column(_ALERTS, "processing_bar_timestamp")
        if _index_exists(bind, "signal_alert_subscriptions_account_id_idx"):
            op.drop_index("signal_alert_subscriptions_account_id_idx", table_name=_ALERTS)
        if _column_exists(bind, _ALERTS, "account_id"):
            op.drop_column(_ALERTS, "account_id")


def upgrade() -> None:
    bind = op.get_bind()
    _upgrade_dia_d(bind)
    _upgrade_alerts(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _downgrade_alerts(bind)
    _downgrade_dia_d(bind)
