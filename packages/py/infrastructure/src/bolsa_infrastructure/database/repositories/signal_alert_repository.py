from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import InstrumentRow, SignalAlertSubscriptionRow
from bolsa_infrastructure.ids import new_id

DEFAULT_SIGNAL_KINDS = ["entry_long", "exit"]
DEFAULT_ALERT_CHANNELS = ["toast"]
SignalKindFilter = Literal["entry_long", "entry_short", "exit", "watch"]


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


class SqlAlchemySignalAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self, *, active_only: bool = False) -> list[SignalAlertSubscriptionRecord]:
        stmt = select(SignalAlertSubscriptionRow).order_by(SignalAlertSubscriptionRow.created_at.desc())
        if active_only:
            stmt = stmt.where(SignalAlertSubscriptionRow.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_record(row) for row in result.scalars().all()]

    async def get_by_id(self, subscription_id: str) -> SignalAlertSubscriptionRecord | None:
        stmt = select(SignalAlertSubscriptionRow).where(SignalAlertSubscriptionRow.id == subscription_id)
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
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def delete(self, subscription_id: str) -> bool:
        stmt = delete(SignalAlertSubscriptionRow).where(SignalAlertSubscriptionRow.id == subscription_id)
        result = await self._session.execute(stmt)
        return cast(CursorResult[Any], result).rowcount > 0

    async def mark_bar_triggered(
        self,
        subscription_id: str,
        *,
        bar_timestamp: str,
        signal_kind: str,
        signal_price: float,
    ) -> SignalAlertSubscriptionRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(SignalAlertSubscriptionRow)
            .where(
                SignalAlertSubscriptionRow.id == subscription_id,
                SignalAlertSubscriptionRow.is_active.is_(True),
            )
            .values(
                last_triggered_at=now,
                last_bar_timestamp=bar_timestamp,
                last_signal_kind=signal_kind,
                last_signal_price=signal_price,
            )
            .returning(SignalAlertSubscriptionRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

    async def reset_bar_dedupe(self, subscription_id: str) -> SignalAlertSubscriptionRecord | None:
        stmt = (
            update(SignalAlertSubscriptionRow)
            .where(SignalAlertSubscriptionRow.id == subscription_id)
            .values(last_bar_timestamp=None)
            .returning(SignalAlertSubscriptionRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

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
            last_signal_price=float(row.last_signal_price) if row.last_signal_price is not None else None,
            note=row.note,
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
