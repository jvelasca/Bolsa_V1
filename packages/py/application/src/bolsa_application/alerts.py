"""Use-cases de alertas de precio."""

from dataclasses import dataclass
from typing import Literal

from bolsa_infrastructure.database.repositories.alert_repository import (
    AlertCondition,
    AlertPriceSource,
    PriceAlertRecord,
    SqlAlchemyAlertRepository,
)
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)

from bolsa_application.market import GetInstrumentLiveQuote


@dataclass(frozen=True, slots=True)
class EvaluateAlertsResult:
    """Evalúa Alerts Result."""
    triggered: list[PriceAlertRecord]


class ListPriceAlerts:
    """Lista Price Alerts."""
    def __init__(self, repo: SqlAlchemyAlertRepository) -> None:
        self._repo = repo

    async def execute(self, *, active_only: bool = False) -> list[PriceAlertRecord]:
        return await self._repo.list_all(active_only=active_only)


class CreatePriceAlert:
    """Crea Price Alert."""
    def __init__(self, repo: SqlAlchemyAlertRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        instrument_id: str,
        condition: AlertCondition,
        target_price: float,
        price_source: AlertPriceSource = "daily_close",
        note: str | None = None,
    ) -> PriceAlertRecord:
        if target_price <= 0:
            raise ValueError("El precio objetivo debe ser mayor que cero")
        if price_source not in ("daily_close", "xtb_last"):
            raise ValueError("priceSource debe ser 'daily_close' o 'xtb_last'")
        return await self._repo.create(
            instrument_id=instrument_id,
            condition=condition,
            target_price=target_price,
            price_source=price_source,
            note=note,
        )


class DeletePriceAlert:
    """Elimina Price Alert."""
    def __init__(self, repo: SqlAlchemyAlertRepository) -> None:
        self._repo = repo

    async def execute(self, alert_id: str) -> None:
        deleted = await self._repo.delete(alert_id)
        if not deleted:
            raise ValueError("Alerta no encontrada")


class ReactivatePriceAlert:
    """Use-case / tipo: Reactivate Price Alert."""
    def __init__(self, repo: SqlAlchemyAlertRepository) -> None:
        self._repo = repo

    async def execute(self, alert_id: str) -> PriceAlertRecord:
        alert = await self._repo.reactivate(alert_id)
        if alert is None:
            existing = await self._repo.get_by_id(alert_id)
            if existing is None:
                raise ValueError("Alerta no encontrada")
            if existing.is_active:
                raise ValueError("La alerta ya está activa")
            raise ValueError("No se pudo reactivar la alerta")
        return alert


class EvaluatePriceAlerts:
    """Evalúa Price Alerts."""
    def __init__(
        self,
        alert_repo: SqlAlchemyAlertRepository,
        instrument_repo: SqlAlchemyInstrumentRepository,
        live_quote: GetInstrumentLiveQuote,
    ) -> None:
        self._alerts = alert_repo
        self._instruments = instrument_repo
        self._live_quote = live_quote

    async def execute(
        self,
        *,
        price_source_filter: AlertPriceSource | None = None,
    ) -> EvaluateAlertsResult:
        active = await self._alerts.list_all(active_only=True)
        if price_source_filter is not None:
            active = [alert for alert in active if alert.price_source == price_source_filter]
        if not active:
            return EvaluateAlertsResult(triggered=[])

        triggered: list[PriceAlertRecord] = []
        price_cache: dict[tuple[str, AlertPriceSource], float | None] = {}

        for alert in active:
            cache_key = (alert.instrument_id, alert.price_source)
            if cache_key not in price_cache:
                price_cache[cache_key] = await self._resolve_price(
                    alert.instrument_id,
                    alert.price_source,
                )
            price = price_cache[cache_key]
            if price is None:
                continue
            if _is_triggered(alert.condition, price, alert.target_price):
                updated = await self._alerts.mark_triggered(alert.id, price=price)
                if updated is not None:
                    triggered.append(updated)

        return EvaluateAlertsResult(triggered=triggered)

    async def _resolve_price(
        self,
        instrument_id: str,
        price_source: AlertPriceSource,
    ) -> float | None:
        if price_source == "daily_close":
            return await self._instruments.get_latest_close(instrument_id)

        quote = await self._live_quote.execute(instrument_id)
        if quote is None or not quote.xtb_available or quote.xtb is None:
            return None
        return quote.xtb.last


def _is_triggered(condition: Literal["above", "below"], price: float, target: float) -> bool:
    if condition == "above":
        return price >= target
    return price <= target
