"""Vista previa de impacto al quitar un instrumento de listas / purgarlo de BD."""

from __future__ import annotations

from dataclasses import dataclass

from bolsa_infrastructure.database.models import (
    InstrumentListItemRow,
    InstrumentListRow,
    InstrumentRow,
    LedgerEntryRow,
    OhlcvBarRow,
    PendingOrderRow,
    PositionRow,
    PriceAlertRow,
    SignalAlertSubscriptionRow,
    TrackerDefinitionRow,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ListMembershipRef:
    list_id: str
    list_name: str
    source: str


@dataclass(frozen=True, slots=True)
class NamedRef:
    id: str
    name: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class InstrumentRemovalPreview:
    instrument_id: str
    symbol: str
    name: str
    list_memberships: tuple[ListMembershipRef, ...]
    remaining_list_count: int
    trackers_by_instrument: tuple[NamedRef, ...]
    trackers_by_list: tuple[NamedRef, ...]
    price_alerts_active: int
    price_alerts_total: int
    signal_alerts_active: int
    signal_alerts_total: int
    positions: int
    pending_orders: int
    transactions: int
    backtest_runs: int
    ledger_entries: int
    ohlcv_bar_count: int
    would_be_orphan: bool
    can_purge: bool
    purge_blocked_reasons: tuple[str, ...]
    purge_warnings: tuple[str, ...]


class GetInstrumentRemovalPreview:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        instrument_id: str,
        *,
        excluding_list_id: str | None = None,
    ) -> InstrumentRemovalPreview | None:
        inst = await self._session.get(InstrumentRow, instrument_id)
        if inst is None:
            return None

        memberships = await self._list_memberships(instrument_id)
        remaining = [
            m for m in memberships if excluding_list_id is None or m.list_id != excluding_list_id
        ]
        would_be_orphan = len(remaining) == 0

        trackers_by_instrument = await self._trackers_pinning_instrument(instrument_id)
        trackers_by_list: list[NamedRef] = []
        if excluding_list_id:
            trackers_by_list = await self._trackers_for_list(excluding_list_id)

        price_total, price_active = await self._count_price_alerts(instrument_id)
        signal_total, signal_active = await self._count_signal_alerts(instrument_id)
        positions = await self._count(PositionRow, instrument_id)
        pending = await self._count(PendingOrderRow, instrument_id)
        # transactions / backtests vía SQL por si el modelo no está importado aquí
        transactions = await self._count_table("transactions", instrument_id)
        backtests = await self._count_table("backtest_runs", instrument_id)
        ledger = await self._count(LedgerEntryRow, instrument_id)
        ohlcv = await self._count(OhlcvBarRow, instrument_id)

        blocked: list[str] = []
        warnings: list[str] = []

        if not would_be_orphan:
            blocked.append("El valor sigue en otras listas; no se purga de BD.")
        if positions > 0:
            blocked.append(f"Tiene {positions} posición(es) abierta(s).")
        if pending > 0:
            blocked.append(f"Tiene {pending} orden(es) pendiente(s).")

        if price_active > 0 or price_total > 0:
            warnings.append(
                f"Se eliminarán {price_total} alerta(s) de precio"
                + (f" ({price_active} activas)" if price_active else "")
                + "."
            )
        if signal_active > 0 or signal_total > 0:
            warnings.append(
                f"Se eliminarán {signal_total} suscripción(es) de alerta de señal"
                + (f" ({signal_active} activas)" if signal_active else "")
                + "."
            )
        if trackers_by_instrument:
            names = ", ".join(t.name for t in trackers_by_instrument[:5])
            warnings.append(
                f"Rastreadores que fijan este instrumento ({len(trackers_by_instrument)}): {names}."
                " Habrá que editar su universo."
            )
        if trackers_by_list:
            names = ", ".join(t.name for t in trackers_by_list[:5])
            warnings.append(
                f"Rastreadores ligados a esta lista ({len(trackers_by_list)}): {names}."
                " Seguirán activos; el valor ya no estará en el universo de la lista."
            )
        if backtests > 0:
            warnings.append(f"Se eliminarán {backtests} backtest(s) asociados (cascade).")
        if transactions > 0:
            warnings.append(f"Se eliminarán {transactions} transacción(es) históricas (cascade).")
        if ohlcv > 0:
            warnings.append(f"Se eliminarán {ohlcv} velas OHLCV.")

        can_purge = would_be_orphan and len(blocked) == 0

        return InstrumentRemovalPreview(
            instrument_id=inst.id,
            symbol=inst.symbol,
            name=inst.name,
            list_memberships=tuple(memberships),
            remaining_list_count=len(remaining),
            trackers_by_instrument=tuple(trackers_by_instrument),
            trackers_by_list=tuple(trackers_by_list),
            price_alerts_active=price_active,
            price_alerts_total=price_total,
            signal_alerts_active=signal_active,
            signal_alerts_total=signal_total,
            positions=positions,
            pending_orders=pending,
            transactions=transactions,
            backtest_runs=backtests,
            ledger_entries=ledger,
            ohlcv_bar_count=ohlcv,
            would_be_orphan=would_be_orphan,
            can_purge=can_purge,
            purge_blocked_reasons=tuple(blocked),
            purge_warnings=tuple(warnings),
        )

    async def _list_memberships(self, instrument_id: str) -> list[ListMembershipRef]:
        stmt = (
            select(InstrumentListRow.id, InstrumentListRow.name, InstrumentListRow.source)
            .join(InstrumentListItemRow, InstrumentListItemRow.list_id == InstrumentListRow.id)
            .where(InstrumentListItemRow.instrument_id == instrument_id)
            .order_by(InstrumentListRow.name.asc())
        )
        result = await self._session.execute(stmt)
        return [
            ListMembershipRef(list_id=row[0], list_name=row[1], source=row[2])
            for row in result.all()
        ]

    async def _trackers_pinning_instrument(self, instrument_id: str) -> list[NamedRef]:
        stmt = (
            select(TrackerDefinitionRow.id, TrackerDefinitionRow.name)
            .where(
                TrackerDefinitionRow.definition.contains(
                    {"universe": {"instrumentIds": [instrument_id]}}
                )
            )
            .order_by(TrackerDefinitionRow.name.asc())
            .limit(50)
        )
        result = await self._session.execute(stmt)
        return [NamedRef(id=row[0], name=row[1]) for row in result.all()]

    async def _trackers_for_list(self, list_id: str) -> list[NamedRef]:
        stmt = (
            select(TrackerDefinitionRow.id, TrackerDefinitionRow.name)
            .where(TrackerDefinitionRow.definition["universe"]["listId"].astext == list_id)
            .order_by(TrackerDefinitionRow.name.asc())
            .limit(50)
        )
        result = await self._session.execute(stmt)
        return [NamedRef(id=row[0], name=row[1]) for row in result.all()]

    async def _count_price_alerts(self, instrument_id: str) -> tuple[int, int]:
        total = await self._count(PriceAlertRow, instrument_id)
        stmt = (
            select(func.count())
            .select_from(PriceAlertRow)
            .where(
                PriceAlertRow.instrument_id == instrument_id,
                PriceAlertRow.is_active.is_(True),
            )
        )
        active = int((await self._session.execute(stmt)).scalar_one())
        return total, active

    async def _count_signal_alerts(self, instrument_id: str) -> tuple[int, int]:
        total = await self._count(SignalAlertSubscriptionRow, instrument_id)
        stmt = (
            select(func.count())
            .select_from(SignalAlertSubscriptionRow)
            .where(
                SignalAlertSubscriptionRow.instrument_id == instrument_id,
                SignalAlertSubscriptionRow.is_active.is_(True),
            )
        )
        active = int((await self._session.execute(stmt)).scalar_one())
        return total, active

    async def _count(self, model: type, instrument_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(model)
            .where(model.instrument_id == instrument_id)  # type: ignore[attr-defined]
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def _count_table(self, table: str, instrument_id: str) -> int:
        result = await self._session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE instrument_id = :id"),
            {"id": instrument_id},
        )
        return int(result.scalar_one())
