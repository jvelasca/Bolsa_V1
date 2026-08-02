from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_analytics.signals.strategy import (
    SignalEventV1,
    StrategyBarInput,
    evaluate_strategy_last_bar,
)
from bolsa_application.scans import MIN_SCAN_BARS
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.alerts.alert_channels import (
    AlertChannelDispatchResult,
    SignalAlertChannelDispatcher,
    normalize_alert_channels,
    validate_alert_channel_config,
)
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
    SqlAlchemySignalAlertRepository,
    filter_signal_events_by_kinds,
    should_emit_for_bar,
)


@dataclass(frozen=True, slots=True)
class TriggeredSignalAlert:
    subscription: SignalAlertSubscriptionRecord
    signal: SignalEventV1
    dispatches: list[AlertChannelDispatchResult]


@dataclass(frozen=True, slots=True)
class EvaluateSignalAlertsResult:
    triggered: list[TriggeredSignalAlert]
    dispatches: list[AlertChannelDispatchResult]


class ListSignalAlertSubscriptions:
    def __init__(self, repo: SqlAlchemySignalAlertRepository) -> None:
        self._repo = repo

    async def execute(self, *, active_only: bool = False) -> list[SignalAlertSubscriptionRecord]:
        return await self._repo.list_all(active_only=active_only)


class CreateSignalAlertSubscription:
    def __init__(
        self,
        repo: SqlAlchemySignalAlertRepository,
        strategy_repo: StrategyDefinitionRepository,
    ) -> None:
        self._repo = repo
        self._strategies = strategy_repo

    async def execute(
        self,
        *,
        instrument_id: str,
        strategy_definition_id: str | None = None,
        preset_key: Literal["sma_crossover", "rsi_mean_reversion"] | None = None,
        timeframe: str = "1d",
        signal_kinds: list[str] | None = None,
        channels: list[str] | None = None,
        webhook_url: str | None = None,
        email_to: str | None = None,
        note: str | None = None,
    ) -> SignalAlertSubscriptionRecord:
        if strategy_definition_id is None and preset_key is None:
            raise ValueError("Indica strategyDefinitionId o presetKey")
        if strategy_definition_id is not None and preset_key is not None:
            raise ValueError("Usa strategyDefinitionId o presetKey, no ambos")

        resolved_timeframe = timeframe
        if strategy_definition_id:
            saved = await self._strategies.get_definition(strategy_definition_id)
            if saved is None:
                raise ValueError("Estrategia no encontrada")
            if saved.preset_key is None and not saved.definition.get("presetKey"):
                raise ValueError("Solo estrategias ejecutables en H0")
            resolved_timeframe = saved.timeframe

        if signal_kinds is not None and not signal_kinds:
            raise ValueError("signalKinds no puede estar vacío")

        resolved_channels = normalize_alert_channels(channels)
        validate_alert_channel_config(
            resolved_channels,
            webhook_url=webhook_url,
            email_to=email_to,
        )

        return await self._repo.create(
            instrument_id=instrument_id,
            strategy_definition_id=strategy_definition_id,
            preset_key=preset_key,
            timeframe=resolved_timeframe,
            signal_kinds=signal_kinds,
            channels=resolved_channels,
            webhook_url=webhook_url.strip() if webhook_url else None,
            email_to=email_to.strip() if email_to else None,
            note=note,
        )


class DeleteSignalAlertSubscription:
    def __init__(self, repo: SqlAlchemySignalAlertRepository) -> None:
        self._repo = repo

    async def execute(self, subscription_id: str) -> None:
        deleted = await self._repo.delete(subscription_id)
        if not deleted:
            raise ValueError("Suscripción no encontrada")


class ResetSignalAlertDedupe:
    def __init__(self, repo: SqlAlchemySignalAlertRepository) -> None:
        self._repo = repo

    async def execute(self, subscription_id: str) -> SignalAlertSubscriptionRecord:
        updated = await self._repo.reset_bar_dedupe(subscription_id)
        if updated is None:
            raise ValueError("Suscripción no encontrada")
        return updated


class EvaluateSignalAlertSubscriptions:
    def __init__(
        self,
        subscription_repo: SqlAlchemySignalAlertRepository,
        strategy_repo: StrategyDefinitionRepository,
        ohlcv_repo: OhlcvRepository,
        channel_dispatcher: SignalAlertChannelDispatcher | None = None,
    ) -> None:
        self._subscriptions = subscription_repo
        self._strategies = strategy_repo
        self._ohlcv = ohlcv_repo
        self._dispatcher = channel_dispatcher or SignalAlertChannelDispatcher()

    async def execute(self) -> EvaluateSignalAlertsResult:
        active = await self._subscriptions.list_all(active_only=True)
        if not active:
            return EvaluateSignalAlertsResult(triggered=[], dispatches=[])

        triggered: list[TriggeredSignalAlert] = []
        all_dispatches: list[AlertChannelDispatchResult] = []
        for subscription in active:
            event = await self._evaluate_subscription(subscription)
            if event is None:
                continue
            updated = await self._subscriptions.mark_bar_triggered(
                subscription.id,
                bar_timestamp=event.timestamp,
                signal_kind=event.kind,
                signal_price=event.price,
            )
            if updated is None:
                continue
            dispatches = await self._dispatcher.dispatch(updated, event)
            all_dispatches.extend(dispatches)
            triggered.append(
                TriggeredSignalAlert(subscription=updated, signal=event, dispatches=dispatches)
            )

        return EvaluateSignalAlertsResult(triggered=triggered, dispatches=all_dispatches)

    async def _evaluate_subscription(self, subscription: SignalAlertSubscriptionRecord) -> SignalEventV1 | None:
        try:
            definition = await self._resolve_definition(subscription)
        except ValueError:
            return None

        tf = (
            TimeFrame(subscription.timeframe)
            if subscription.timeframe in {t.value for t in TimeFrame}
            else TimeFrame.D1
        )
        bars = await self._ohlcv.get_bars(subscription.instrument_id, timeframe=tf, limit=500)
        if len(bars) < MIN_SCAN_BARS:
            return None

        last_bar_timestamp = bars[-1].timestamp
        if not should_emit_for_bar(subscription.last_bar_timestamp, last_bar_timestamp):
            return None

        strategy_bars = [StrategyBarInput(timestamp=bar.timestamp, close=bar.close) for bar in bars]
        per_instrument_definition = {
            **definition,
            "universe": {"instrumentIds": [subscription.instrument_id]},
        }

        try:
            events = evaluate_strategy_last_bar(
                per_instrument_definition,
                strategy_bars,
                instrument_id=subscription.instrument_id,
                mode="raw",
            )
        except ValueError:
            return None

        filtered = filter_signal_events_by_kinds(events, subscription.signal_kinds)
        if not filtered:
            return None

        return filtered[0]

    async def _resolve_definition(self, subscription: SignalAlertSubscriptionRecord) -> dict[str, Any]:
        if subscription.strategy_definition_id:
            saved = await self._strategies.get_definition(subscription.strategy_definition_id)
            if saved is None:
                raise ValueError("Estrategia no encontrada")
            return {**saved.definition, "id": saved.id}

        if is_valid_preset_key(subscription.preset_key):
            return strategy_definition_from_preset(
                subscription.preset_key,
                instrument_ids=[subscription.instrument_id],
                timeframe=subscription.timeframe,
            )

        raise ValueError("Suscripción sin estrategia ejecutable")
