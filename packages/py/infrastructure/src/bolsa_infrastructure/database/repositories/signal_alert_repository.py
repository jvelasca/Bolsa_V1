"""Repositorio SQLAlchemy — suscripciones de alertas por señal + OUTBOX de entregas.

v111 (auditoría): la suscripción tiene DUEÑO (``account_id``) y el dispare de una barra se
resuelve con un **claim atómico** (``WHERE last_bar_timestamp IS DISTINCT FROM :bar`` + lease),
de modo que worker y evaluación manual no despachan dos veces. La ENTREGA vive en una tabla
OUTBOX (``alert_deliveries``) con estado/reintento, para que un fallo de SMTP/webhook no se
pierda en silencio (``last_bar_timestamp`` deja de ser prueba de "entregado").
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    AlertDeliveryRow,
    InstrumentRow,
    SignalAlertSubscriptionRow,
)
from bolsa_infrastructure.ids import new_id

DEFAULT_SIGNAL_KINDS = ["entry_long", "exit"]
DEFAULT_ALERT_CHANNELS = ["toast"]
SignalKindFilter = Literal["entry_long", "entry_short", "exit", "watch"]

#: Estados del OUTBOX (PENDING → DELIVERED | RETRYABLE_FAILED → DEAD_LETTER).
DELIVERY_PENDING = "pending"
DELIVERY_DELIVERED = "delivered"
DELIVERY_RETRYABLE_FAILED = "retryable_failed"
DELIVERY_DEAD_LETTER = "dead_letter"
DELIVERY_TERMINAL = frozenset({DELIVERY_DELIVERED, DELIVERY_DEAD_LETTER})

#: Lease por defecto del claim de barra (segundos) — cubre un worker caído a mitad de claim.
DEFAULT_CLAIM_LEASE_SECONDS = 120.0


@dataclass(frozen=True, slots=True)
class SignalAlertSubscriptionRecord:
    id: str
    instrument_id: str
    symbol: str
    strategy_definition_id: str | None
    preset_key: str | None
    timeframe: str
    signal_kinds: list[str]
    channels: list[str]
    webhook_url: str | None
    email_to: str | None
    is_active: bool
    last_triggered_at: str | None
    last_bar_timestamp: str | None
    last_signal_kind: str | None
    last_signal_price: float | None
    note: str | None
    created_at: str
    #: v111 — dueño de la suscripción (aislamiento por cuenta). ``None`` = fila legacy.
    account_id: str | None = None


@dataclass(frozen=True, slots=True)
class BarClaim:
    """Resultado del CLAIM atómico de una barra: la suscripción ganadora y su token de lease."""

    subscription: SignalAlertSubscriptionRecord
    token: str


@dataclass(frozen=True, slots=True)
class AlertDeliveryRecord:
    """Una entrega de un canal para un ``(suscripción, barra)`` (fila del OUTBOX)."""

    id: str
    subscription_id: str
    account_id: str | None
    bar_timestamp: str
    signal_kind: str | None
    channel: str
    status: str
    attempt: int
    payload: dict[str, Any] | None
    last_error: str | None
    next_retry_at: str | None
    created_at: str


class SqlAlchemySignalAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        """Confirma la transacción (lo usa el worker del OUTBOX entre claim y envío)."""
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    # ── Suscripciones ────────────────────────────────────────────────────────────

    async def list_all(
        self,
        *,
        account_id: str | None = None,
        active_only: bool = False,
    ) -> list[SignalAlertSubscriptionRecord]:
        """Suscripciones visibles. ``account_id`` acota al dueño (fail-closed en el llamante)."""
        stmt = select(SignalAlertSubscriptionRow).order_by(
            SignalAlertSubscriptionRow.created_at.desc()
        )
        if account_id is not None:
            stmt = stmt.where(SignalAlertSubscriptionRow.account_id == account_id)
        if active_only:
            stmt = stmt.where(SignalAlertSubscriptionRow.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_record(row) for row in result.scalars().all()]

    async def get_by_id(
        self, subscription_id: str, *, account_id: str | None = None
    ) -> SignalAlertSubscriptionRecord | None:
        stmt = select(SignalAlertSubscriptionRow).where(
            SignalAlertSubscriptionRow.id == subscription_id
        )
        if account_id is not None:
            stmt = stmt.where(SignalAlertSubscriptionRow.account_id == account_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

    async def create(
        self,
        *,
        instrument_id: str,
        strategy_definition_id: str | None,
        preset_key: str | None,
        timeframe: str = "1d",
        signal_kinds: list[str] | None = None,
        channels: list[str] | None = None,
        webhook_url: str | None = None,
        email_to: str | None = None,
        note: str | None = None,
        account_id: str | None = None,
    ) -> SignalAlertSubscriptionRecord:
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        instrument = result.scalar_one_or_none()
        if instrument is None:
            raise ValueError("Instrumento no encontrado")

        kinds = signal_kinds or list(DEFAULT_SIGNAL_KINDS)
        resolved_channels = channels or list(DEFAULT_ALERT_CHANNELS)
        now = datetime.now(UTC)
        row = SignalAlertSubscriptionRow(
            id=new_id(),
            instrument_id=instrument_id,
            symbol=instrument.symbol,
            strategy_definition_id=strategy_definition_id,
            preset_key=preset_key,
            timeframe=timeframe,
            signal_kinds=kinds,
            channels=resolved_channels,
            webhook_url=webhook_url,
            email_to=email_to,
            is_active=True,
            last_triggered_at=None,
            last_bar_timestamp=None,
            last_signal_kind=None,
            last_signal_price=None,
            note=note,
            account_id=account_id,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def delete(self, subscription_id: str, *, account_id: str | None = None) -> bool:
        stmt = delete(SignalAlertSubscriptionRow).where(
            SignalAlertSubscriptionRow.id == subscription_id
        )
        if account_id is not None:
            stmt = stmt.where(SignalAlertSubscriptionRow.account_id == account_id)
        result = await self._session.execute(stmt)
        return cast(CursorResult[Any], result).rowcount > 0

    async def claim_bar(
        self,
        subscription_id: str,
        *,
        account_id: str | None = None,
        bar_timestamp: str,
        signal_kind: str,
        signal_price: float,
        lease_seconds: float = DEFAULT_CLAIM_LEASE_SECONDS,
    ) -> BarClaim | None:
        """CLAIM atómico de la barra: sólo el ganador recibe fila (los demás despachan nada).

        Gana quien actualiza con ``last_bar_timestamp IS DISTINCT FROM :bar`` **y** sin otro claim
        en vuelo (``processing_token`` nulo o lease expirada). Marca la barra como procesada
        (dedupe) y sella el lease; el llamante DEBE cerrar el claim con :meth:`finish_bar_claim`
        tras encolar las entregas (o el lease expira y se reclama).
        """
        now = datetime.now(UTC)
        lease_cutoff = now - timedelta(seconds=lease_seconds)
        token = new_id()
        stmt = (
            update(SignalAlertSubscriptionRow)
            .where(
                SignalAlertSubscriptionRow.id == subscription_id,
                SignalAlertSubscriptionRow.is_active.is_(True),
                SignalAlertSubscriptionRow.last_bar_timestamp.is_distinct_from(bar_timestamp),
                or_(
                    SignalAlertSubscriptionRow.processing_token.is_(None),
                    SignalAlertSubscriptionRow.processing_started_at < lease_cutoff,
                ),
            )
            .values(
                last_triggered_at=now,
                last_bar_timestamp=bar_timestamp,
                last_signal_kind=signal_kind,
                last_signal_price=signal_price,
                processing_bar_timestamp=bar_timestamp,
                processing_token=token,
                processing_started_at=now,
            )
            .returning(SignalAlertSubscriptionRow)
        )
        if account_id is not None:
            stmt = stmt.where(SignalAlertSubscriptionRow.account_id == account_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return BarClaim(subscription=self._to_record(row), token=token)

    async def finish_bar_claim(self, subscription_id: str, token: str) -> None:
        """Libera el lease del claim (sólo si el token sigue siendo el nuestro)."""
        stmt = (
            update(SignalAlertSubscriptionRow)
            .where(
                SignalAlertSubscriptionRow.id == subscription_id,
                SignalAlertSubscriptionRow.processing_token == token,
            )
            .values(
                processing_bar_timestamp=None,
                processing_token=None,
                processing_started_at=None,
            )
        )
        await self._session.execute(stmt)

    async def reset_bar_dedupe(
        self, subscription_id: str, *, account_id: str | None = None
    ) -> SignalAlertSubscriptionRecord | None:
        stmt = (
            update(SignalAlertSubscriptionRow)
            .where(SignalAlertSubscriptionRow.id == subscription_id)
            .values(
                last_bar_timestamp=None,
                processing_bar_timestamp=None,
                processing_token=None,
                processing_started_at=None,
            )
            .returning(SignalAlertSubscriptionRow)
        )
        if account_id is not None:
            stmt = stmt.where(SignalAlertSubscriptionRow.account_id == account_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

    # ── OUTBOX de entregas ───────────────────────────────────────────────────────

    async def enqueue_delivery(
        self,
        *,
        subscription_id: str,
        account_id: str | None,
        bar_timestamp: str,
        signal_kind: str | None,
        channel: str,
        payload: dict[str, Any] | None,
    ) -> AlertDeliveryRecord:
        """Encola una entrega ``PENDING`` (una fila del OUTBOX).

        La unicidad ``(suscripción, barra, canal)`` la garantiza la tabla: un reencolado del mismo
        ``(suscripción, barra, canal)`` **falla** (``IntegrityError``) en vez de duplicar la entrega
        o de absorberla en silencio. El mismo ``(barra)`` por otro canal es otra entrega.
        """
        now = datetime.now(UTC)
        row = AlertDeliveryRow(
            id=new_id(),
            subscription_id=subscription_id,
            account_id=account_id,
            bar_timestamp=bar_timestamp,
            signal_kind=signal_kind,
            channel=channel,
            status=DELIVERY_PENDING,
            attempt=0,
            payload=payload,
            last_error=None,
            next_retry_at=None,
            claimed_at=None,
            delivered_at=None,
            created_at=now,
            updated_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_delivery(row)

    async def list_deliveries(
        self,
        *,
        subscription_id: str | None = None,
        account_id: str | None = None,
        limit: int = 200,
    ) -> list[AlertDeliveryRecord]:
        stmt = select(AlertDeliveryRow).order_by(AlertDeliveryRow.created_at.desc())
        if subscription_id is not None:
            stmt = stmt.where(AlertDeliveryRow.subscription_id == subscription_id)
        if account_id is not None:
            stmt = stmt.where(AlertDeliveryRow.account_id == account_id)
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_delivery(row) for row in result.scalars().all()]

    async def count_deliveries_by_status(self) -> dict[str, int]:
        """Recuento del OUTBOX por estado (observabilidad: ``RETRYABLE_FAILED``/``DEAD_LETTER``).

        Read-only y sin ámbito de cuenta (el estado del OUTBOX es global); lo consume ``/health``.
        """
        stmt = select(AlertDeliveryRow.status, func.count()).group_by(AlertDeliveryRow.status)
        result = await self._session.execute(stmt)
        return {str(status): int(count) for status, count in result.all()}

    async def claim_due_deliveries(
        self,
        *,
        limit: int = 50,
        lease_seconds: float = DEFAULT_CLAIM_LEASE_SECONDS,
        max_attempts: int = 5,
    ) -> list[AlertDeliveryRecord]:
        """Reclama entregas PENDING/REINTENTABLES vencidas (``FOR UPDATE SKIP LOCKED``).

        Sólo devuelve filas que este proceso ha sellado (``claimed_at``). Las de estado terminal,
        las diferidas (``next_retry_at`` futuro) y las ya agotadas (``attempt >= max``, que se
        remiten a ``DEAD_LETTER``) quedan fuera.
        """
        now = datetime.now(UTC)
        lease_cutoff = now - timedelta(seconds=lease_seconds)
        candidates = (
            select(AlertDeliveryRow.id)
            .where(
                AlertDeliveryRow.status.in_([DELIVERY_PENDING, DELIVERY_RETRYABLE_FAILED]),
                or_(
                    AlertDeliveryRow.next_retry_at.is_(None),
                    AlertDeliveryRow.next_retry_at <= now,
                ),
                or_(
                    AlertDeliveryRow.claimed_at.is_(None),
                    AlertDeliveryRow.claimed_at < lease_cutoff,
                ),
            )
            .order_by(AlertDeliveryRow.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        stmt = (
            update(AlertDeliveryRow)
            .where(AlertDeliveryRow.id.in_(candidates))
            .values(claimed_at=now, updated_at=now)
            .returning(AlertDeliveryRow)
        )
        result = await self._session.execute(stmt)
        return [self._to_delivery(row) for row in result.scalars().all()]

    async def mark_delivery_delivered(self, delivery_id: str) -> AlertDeliveryRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(AlertDeliveryRow)
            .where(AlertDeliveryRow.id == delivery_id)
            .values(
                status=DELIVERY_DELIVERED,
                attempt=AlertDeliveryRow.attempt + 1,
                delivered_at=now,
                claimed_at=None,
                next_retry_at=None,
                updated_at=now,
            )
            .returning(AlertDeliveryRow)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._to_delivery(row)

    async def mark_delivery_failed(
        self,
        delivery_id: str,
        *,
        error: str | None,
        next_retry_at: datetime | None,
        dead_letter: bool,
    ) -> AlertDeliveryRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(AlertDeliveryRow)
            .where(AlertDeliveryRow.id == delivery_id)
            .values(
                status=DELIVERY_DEAD_LETTER if dead_letter else DELIVERY_RETRYABLE_FAILED,
                attempt=AlertDeliveryRow.attempt + 1,
                last_error=(error or "")[:500] or None,
                next_retry_at=None if dead_letter else next_retry_at,
                claimed_at=None,
                updated_at=now,
            )
            .returning(AlertDeliveryRow)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._to_delivery(row)

    async def expire_exhausted_deliveries(self, *, max_attempts: int = 5) -> int:
        """Remite a ``DEAD_LETTER`` las rein tentables que ya agotaron el presupuesto."""
        now = datetime.now(UTC)
        stmt = (
            update(AlertDeliveryRow)
            .where(
                AlertDeliveryRow.status == DELIVERY_RETRYABLE_FAILED,
                AlertDeliveryRow.attempt >= max_attempts,
            )
            .values(status=DELIVERY_DEAD_LETTER, updated_at=now)
        )
        result = await self._session.execute(stmt)
        return int(cast(CursorResult[Any], result).rowcount or 0)

    def _to_record(self, row: SignalAlertSubscriptionRow) -> SignalAlertSubscriptionRecord:
        kinds = row.signal_kinds if isinstance(row.signal_kinds, list) else DEFAULT_SIGNAL_KINDS
        channels = row.channels if isinstance(row.channels, list) else DEFAULT_ALERT_CHANNELS
        return SignalAlertSubscriptionRecord(
            id=row.id,
            instrument_id=row.instrument_id,
            symbol=row.symbol,
            strategy_definition_id=row.strategy_definition_id,
            preset_key=row.preset_key,
            timeframe=row.timeframe,
            signal_kinds=[str(kind) for kind in kinds],
            channels=[str(channel) for channel in channels],
            webhook_url=row.webhook_url,
            email_to=row.email_to,
            is_active=row.is_active,
            last_triggered_at=row.last_triggered_at.isoformat() if row.last_triggered_at else None,
            last_bar_timestamp=row.last_bar_timestamp,
            last_signal_kind=row.last_signal_kind,
            last_signal_price=(
                float(row.last_signal_price) if row.last_signal_price is not None else None
            ),
            note=row.note,
            created_at=row.created_at.isoformat(),
            account_id=getattr(row, "account_id", None),
        )

    def _to_delivery(self, row: AlertDeliveryRow) -> AlertDeliveryRecord:
        return AlertDeliveryRecord(
            id=row.id,
            subscription_id=row.subscription_id,
            account_id=row.account_id,
            bar_timestamp=row.bar_timestamp,
            signal_kind=row.signal_kind,
            channel=row.channel,
            status=row.status,
            attempt=row.attempt,
            payload=row.payload if isinstance(row.payload, dict) else None,
            last_error=row.last_error,
            next_retry_at=row.next_retry_at.isoformat() if row.next_retry_at else None,
            created_at=row.created_at.isoformat(),
        )


def filter_signal_events_by_kinds(
    events: list[Any],
    kinds: list[str],
) -> list[Any]:
    allowed = set(kinds)
    return [event for event in events if getattr(event, "kind", None) in allowed]


def should_emit_for_bar(last_bar_timestamp: str | None, current_bar_timestamp: str) -> bool:
    return last_bar_timestamp != current_bar_timestamp
