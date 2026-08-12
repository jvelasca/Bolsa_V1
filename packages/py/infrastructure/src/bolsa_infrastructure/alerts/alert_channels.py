"""SC-6 — AlertChannel: webhook JSON + email SMTP sobre SignalEvent."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

import httpx

from bolsa_infrastructure.config import Settings, get_settings
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
)

logger = logging.getLogger(__name__)

ALLOWED_ALERT_CHANNELS = frozenset({"toast", "webhook", "email"})
DEFAULT_ALERT_CHANNELS = ["toast"]


@dataclass(frozen=True, slots=True)
class AlertChannelDispatchResult:
    subscription_id: str
    channel: str
    ok: bool
    error: str | None = None


def normalize_alert_channels(channels: list[str] | None) -> list[str]:
    if channels is None:
        return list(DEFAULT_ALERT_CHANNELS)
    if not channels:
        raise ValueError("channels no puede estar vacío")

    normalized: list[str] = []
    for channel in channels:
        if channel not in ALLOWED_ALERT_CHANNELS:
            raise ValueError(f"Canal no válido: {channel}")
        if channel not in normalized:
            normalized.append(channel)
    return normalized


def validate_alert_channel_config(
    channels: list[str],
    *,
    webhook_url: str | None,
    email_to: str | None,
) -> None:
    if "webhook" in channels:
        if not webhook_url:
            raise ValueError("webhookUrl es obligatorio con canal webhook")
        parsed = urlparse(webhook_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("webhookUrl debe ser http(s) válida")

    if "email" in channels:
        if not email_to or "@" not in email_to:
            raise ValueError("emailTo es obligatorio y debe ser un email válido con canal email")


def signal_event_to_payload(
    subscription: SignalAlertSubscriptionRecord,
    signal: Any,
) -> dict[str, Any]:
    return {
        "type": "signal_alert",
        "subscriptionId": subscription.id,
        "symbol": subscription.symbol,
        "instrumentId": subscription.instrument_id,
        "timeframe": subscription.timeframe,
        "strategyDefinitionId": subscription.strategy_definition_id,
        "presetKey": subscription.preset_key,
        "note": subscription.note,
        "signal": {
            "id": signal.id,
            "instrumentId": signal.instrument_id,
            "timestamp": signal.timestamp,
            "kind": signal.kind,
            "strategyDefinitionId": signal.strategy_definition_id,
            "strategyVersion": signal.strategy_version,
            "barIndex": signal.bar_index,
            "price": signal.price,
            "dataVersion": signal.data_version,
            "indicatorSnapshotHash": signal.indicator_snapshot_hash,
            "presetKey": signal.preset_key,
        },
    }


class SignalAlertChannelDispatcher:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def dispatch(
        self,
        subscription: SignalAlertSubscriptionRecord,
        signal: Any,
    ) -> list[AlertChannelDispatchResult]:
        channels = normalize_alert_channels(subscription.channels)
        results: list[AlertChannelDispatchResult] = []

        for channel in channels:
            if channel == "toast":
                continue
            if channel == "webhook":
                results.append(await self._dispatch_webhook(subscription, signal))
            elif channel == "email":
                results.append(await self._dispatch_email(subscription, signal))

        return results

    async def _dispatch_webhook(
        self,
        subscription: SignalAlertSubscriptionRecord,
        signal: Any,
    ) -> AlertChannelDispatchResult:
        url = subscription.webhook_url
        if not url:
            return AlertChannelDispatchResult(
                subscription_id=subscription.id,
                channel="webhook",
                ok=False,
                error="webhookUrl no configurada",
            )

        payload = signal_event_to_payload(subscription, signal)
        timeout = self._settings.alert_webhook_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Webhook alerta falló subscription=%s url=%s: %s",
                subscription.id,
                url,
                exc,
            )
            return AlertChannelDispatchResult(
                subscription_id=subscription.id,
                channel="webhook",
                ok=False,
                error=str(exc),
            )

        return AlertChannelDispatchResult(
            subscription_id=subscription.id,
            channel="webhook",
            ok=True,
        )

    async def _dispatch_email(
        self,
        subscription: SignalAlertSubscriptionRecord,
        signal: Any,
    ) -> AlertChannelDispatchResult:
        recipient = subscription.email_to
        if not recipient:
            return AlertChannelDispatchResult(
                subscription_id=subscription.id,
                channel="email",
                ok=False,
                error="emailTo no configurado",
            )

        if not self._settings.smtp_host or not self._settings.smtp_from:
            return AlertChannelDispatchResult(
                subscription_id=subscription.id,
                channel="email",
                ok=False,
                error="SMTP no configurado en el servidor",
            )

        subject = f"[Bolsa] {subscription.symbol} — señal {signal.kind}"
        body = (
            f"Símbolo: {subscription.symbol}\n"
            f"Instrumento: {subscription.instrument_id}\n"
            f"Señal: {signal.kind}\n"
            f"Precio: {signal.price}\n"
            f"Barra: {signal.timestamp}\n"
            f"Suscripción: {subscription.id}\n"
        )
        if subscription.note:
            body += f"Nota: {subscription.note}\n"

        try:
            await asyncio.to_thread(
                self._send_smtp_email,
                recipient,
                subject,
                body,
            )
        except Exception as exc:
            logger.warning(
                "Email alerta falló subscription=%s to=%s: %s",
                subscription.id,
                recipient,
                exc,
            )
            return AlertChannelDispatchResult(
                subscription_id=subscription.id,
                channel="email",
                ok=False,
                error=str(exc),
            )

        return AlertChannelDispatchResult(
            subscription_id=subscription.id,
            channel="email",
            ok=True,
        )

    def _send_smtp_email(self, recipient: str, subject: str, body: str) -> None:
        settings = self._settings
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.smtp_from
        message["To"] = recipient
        message.set_content(body)

        with smtplib.SMTP(settings.smtp_host or "localhost", settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_user and settings.smtp_password:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
