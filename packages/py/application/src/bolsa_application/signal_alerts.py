"""Use-cases de alertas por señal (v111: ownership + claim atómico + OUTBOX de entrega).

Cambios de la auditoría v111:

* **Ownership** — todas las operaciones aceptan ``account_id`` y acotan por dueño.
* **Claim atómico** — el disparo de una barra se reclama con ``last_bar_timestamp IS DISTINCT
  FROM`` + lease; sólo el ganador encola/despacha (fin del doble despacho worker/manual).
* **OUTBOX** — la entrega vive en ``alert_deliveries`` (PENDING/DELIVERED/RETRYABLE_FAILED/
  DEAD_LETTER): un fallo de SMTP/webhook se reintenta con backoff, no se pierde en silencio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Literal, cast

from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_analytics.signals.strategy import (
    SignalEventV1,
    StrategyBarInput,
    evaluate_strategy_last_bar,
)
from bolsa_domain.platform_kernel import MIN_SCAN_BARS
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.alerts.alert_channels import (
    AlertChannelDispatchResult,
    SignalAlertChannelDispatcher,
    normalize_alert_channels,
    signal_event_to_payload,
    validate_alert_channel_config,
)
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    AlertDeliveryRecord,
    SignalAlertSubscriptionRecord,
    SqlAlchemySignalAlertRepository,
    filter_signal_events_by_kinds,
    should_emit_for_bar,
)


@dataclass(frozen=True, slots=True)
class TriggeredSignalAlert:
    """Use-case / tipo: Triggered Signal Alert."""

    subscription: SignalAlertSubscriptionRecord
    signal: SignalEventV1
    dispatches: list[AlertChannelDispatchResult]
    deliveries: list[AlertDeliveryRecord]


@dataclass(frozen=True, slots=True)
class EvaluateSignalAlertsResult:
    """Evalúa Signal Alerts Result."""

    triggered: list[TriggeredSignalAlert]
    dispatches: list[AlertChannelDispatchResult]


class ListSignalAlertSubscriptions:
    """Lista Signal Alert Subscriptions (acotada al dueño)."""

    def __init__(self, repo: SqlAlchemySignalAlertRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        account_id: str | None = None,
        active_only: bool = False,
    ) -> list[SignalAlertSubscriptionRecord]:
        return await self._repo.list_all(account_id=account_id, active_only=active_only)


class CreateSignalAlertSubscription:
    """Crea Signal Alert Subscription."""

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
        account_id: str | None = None,
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
            account_id=account_id,
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
    """Elimina Signal Alert Subscription (sólo del dueño)."""

    def __init__(self, repo: SqlAlchemySignalAlertRepository) -> None:
        self._repo = repo

    async def execute(self, subscription_id: str, *, account_id: str | None = None) -> None:
        deleted = await self._repo.delete(subscription_id, account_id=account_id)
        if not deleted:
            raise ValueError("Suscripción no encontrada")


class ResetSignalAlertDedupe:
    """Use-case / tipo: Reset Signal Alert Dedupe."""

    def __init__(self, repo: SqlAlchemySignalAlertRepository) -> None:
        self._repo = repo

    async def execute(
        self, subscription_id: str, *, account_id: str | None = None
    ) -> SignalAlertSubscriptionRecord:
        updated = await self._repo.reset_bar_dedupe(subscription_id, account_id=account_id)
        if updated is None:
            raise ValueError("Suscripción no encontrada")
        return updated


class EvaluateSignalAlertSubscriptions:
    """Evalúa Signal Alert Subscriptions: claim atómico + encolado en el OUTBOX."""

    def __init__(
        self,
        subscription_repo: SqlAlchemySignalAlertRepository,
        strategy_repo: StrategyDefinitionRepository,
        ohlcv_repo: OhlcvRepository,
        channel_dispatcher: SignalAlertChannelDispatcher | None = None,
        outbox: ProcessAlertDeliveries | None = None,
    ) -> None:
        self._subscriptions = subscription_repo
        self._strategies = strategy_repo
        self._ohlcv = ohlcv_repo
        self._dispatcher = channel_dispatcher or SignalAlertChannelDispatcher()
        self._outbox = outbox

    async def execute(self, *, account_id: str | None = None) -> EvaluateSignalAlertsResult:
        active = await self._subscriptions.list_all(account_id=account_id, active_only=True)
        if not active:
            return EvaluateSignalAlertsResult(triggered=[], dispatches=[])

        triggered: list[TriggeredSignalAlert] = []
        all_dispatches: list[AlertChannelDispatchResult] = []
        for subscription in active:
            event = await self._evaluate_subscription(subscription)
            if event is None:
                continue
            claim = await self._subscriptions.claim_bar(
                subscription.id,
                account_id=account_id,
                bar_timestamp=event.timestamp,
                signal_kind=event.kind,
                signal_price=event.price,
            )
            if claim is None:
                # Otra pista (worker o evaluación manual) ya reclamó esta barra.
                continue
            claimed = claim.subscription
            deliveries = await self._enqueue_deliveries(claimed, event)
            await self._subscriptions.finish_bar_claim(claimed.id, claim.token)
            await self._subscriptions.commit()

            dispatches: list[AlertChannelDispatchResult] = []
            if deliveries and self._outbox is not None:
                dispatches = await self._outbox.process(deliveries)
            all_dispatches.extend(dispatches)
            triggered.append(
                TriggeredSignalAlert(
                    subscription=claimed,
                    signal=event,
                    dispatches=dispatches,
                    deliveries=deliveries,
                )
            )

        return EvaluateSignalAlertsResult(triggered=triggered, dispatches=all_dispatches)

    async def _enqueue_deliveries(
        self, subscription: SignalAlertSubscriptionRecord, event: SignalEventV1
    ) -> list[AlertDeliveryRecord]:
        payload = signal_event_to_payload(subscription, event)
        deliveries: list[AlertDeliveryRecord] = []
        for channel in normalize_alert_channels(subscription.channels):
            if channel == "toast":
                continue
            deliveries.append(
                await self._subscriptions.enqueue_delivery(
                    subscription_id=subscription.id,
                    account_id=subscription.account_id,
                    bar_timestamp=event.timestamp,
                    signal_kind=event.kind,
                    channel=channel,
                    payload=payload,
                )
            )
        return deliveries

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

        return cast(SignalEventV1, filtered[0])

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


def _signal_view(payload: dict[str, Any] | None) -> Any:
    """Reconstruye la vista mínima de la señal desde el ``payload`` durable del OUTBOX."""
    nested = (payload or {}).get("signal") or {}
    return SimpleNamespace(
        id=nested.get("id"),
        instrument_id=nested.get("instrumentId"),
        timestamp=nested.get("timestamp"),
        kind=nested.get("kind"),
        strategy_definition_id=nested.get("strategyDefinitionId"),
        strategy_version=nested.get("strategyVersion"),
        bar_index=nested.get("barIndex"),
        price=nested.get("price"),
        data_version=nested.get("dataVersion"),
        indicator_snapshot_hash=nested.get("indicatorSnapshotHash"),
        preset_key=nested.get("presetKey"),
    )


class ProcessAlertDeliveries:
    """Worker del OUTBOX: reclama entregas vencidas, las envía y transiciona su estado.

    Reintentos con **backoff** exponencial y presupuesto acotado (``max_attempts``): al agotarlo
    la fila pasa a ``DEAD_LETTER``. Nunca se pierde una entrega en silencio.
    """

    def __init__(
        self,
        subscription_repo: SqlAlchemySignalAlertRepository,
        channel_dispatcher: SignalAlertChannelDispatcher | None = None,
        *,
        max_attempts: int | None = None,
        base_backoff_seconds: float | None = None,
        lease_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self._repo = subscription_repo
        self._dispatcher = channel_dispatcher or SignalAlertChannelDispatcher(settings)
        self._max_attempts: int = max_attempts or settings.alert_delivery_max_attempts
        self._base_backoff: float = float(
            base_backoff_seconds or settings.alert_delivery_base_backoff_seconds
        )
        self._lease: float = lease_seconds or settings.alert_delivery_lease_seconds

    async def execute(self, *, limit: int = 50) -> list[AlertChannelDispatchResult]:
        claimed = await self._repo.claim_due_deliveries(
            limit=limit, lease_seconds=self._lease, max_attempts=self._max_attempts
        )
        if not claimed:
            return []
        # Se suelta el lock del claim ANTES de la I/O de red (el lease cubre una caída).
        await self._repo.commit()
        return await self.process(claimed)

    async def process(
        self, deliveries: list[AlertDeliveryRecord]
    ) -> list[AlertChannelDispatchResult]:
        results: list[AlertChannelDispatchResult] = []
        for delivery in deliveries:
            results.append(await self._process_one(delivery))
        return results

    async def _process_one(self, delivery: AlertDeliveryRecord) -> AlertChannelDispatchResult:
        subscription = await self._repo.get_by_id(
            delivery.subscription_id, account_id=delivery.account_id
        )
        if subscription is None:
            await self._repo.mark_delivery_failed(
                delivery.id,
                error="suscripción no encontrada",
                next_retry_at=None,
                dead_letter=True,
            )
            await self._repo.commit()
            return AlertChannelDispatchResult(
                subscription_id=delivery.subscription_id,
                channel=delivery.channel,
                ok=False,
                error="suscripción no encontrada",
                attempt=delivery.attempt + 1,
                will_retry=False,
                delivery_id=delivery.id,
            )

        signal = _signal_view(delivery.payload)
        dispatched = await self._dispatcher.dispatch_channels(
            subscription, signal, channel=delivery.channel
        )
        result = dispatched[0] if dispatched else AlertChannelDispatchResult(
            subscription_id=delivery.subscription_id,
            channel=delivery.channel,
            ok=True,
        )

        if result.ok:
            await self._repo.mark_delivery_delivered(delivery.id)
            await self._repo.commit()
            return AlertChannelDispatchResult(
                subscription_id=delivery.subscription_id,
                channel=delivery.channel,
                ok=True,
                attempt=delivery.attempt + 1,
                delivery_id=delivery.id,
            )

        attempt_after = delivery.attempt + 1
        dead_letter = attempt_after >= self._max_attempts
        next_retry_at = None if dead_letter else datetime.now(UTC) + timedelta(
            seconds=self._backoff_seconds(attempt_after)
        )
        await self._repo.mark_delivery_failed(
            delivery.id,
            error=result.error,
            next_retry_at=next_retry_at,
            dead_letter=dead_letter,
        )
        await self._repo.commit()
        return AlertChannelDispatchResult(
            subscription_id=delivery.subscription_id,
            channel=delivery.channel,
            ok=False,
            error=result.error,
            attempt=attempt_after,
            will_retry=not dead_letter,
            delivery_id=delivery.id,
        )

    def _backoff_seconds(self, attempt: int) -> float:
        # Backoff exponencial acotado (30s, 60s, 120s…) — determinista y auditable.
        # ``2.0`` (y no ``2``) para que el producto sea ``float`` y no ``Any`` (mypy).
        return self._base_backoff * (2.0 ** max(0, attempt - 1))
