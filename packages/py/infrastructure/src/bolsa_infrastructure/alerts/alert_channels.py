"""SC-6/v111 — AlertChannel: webhook JSON + email SMTP sobre SignalEvent.

v111 (auditoría, anti-SSRF): la ``webhookUrl`` la define un usuario, así que antes de conectar
se exige **HTTPS** (salvo escape de dev explícito), se RESUELVE el DNS y se RECHAZAN rangos
privados/loopback/link-local/multicast/reservados y de metadata cloud, se aplica una allowlist
opcional, se **deshabilitan las redirecciones**, se acota el tamaño de la respuesta y se aplica
un timeout estricto. Un destino no permitido se declara ``ok=False`` con el motivo, nunca se
conecta.

v112 (auditoría, anti-DNS-rebinding): la conexión se **FIJA a la IP ya validada**. Validar el DNS
en una resolución y dejar que ``httpx`` re-resuelva el hostname al conectar abría la ventana de
*DNS rebinding* (el dominio del atacante responde una IP pública en la validación y una IP interna
milisegundos después, en la conexión real). ``resolve_public_webhook_target`` devuelve la lista de
IPs validadas y ``_dispatch_webhook`` conecta **por IP** conservando el ``Host``/SNI originales, de
modo que la IP que el código *valida* es la misma IP a la que el cliente HTTP *se conecta*.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import smtplib
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any
from urllib.parse import ParseResult, urlparse, urlunparse

import httpx

from bolsa_infrastructure.config import Settings, get_settings
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
)

logger = logging.getLogger(__name__)

ALLOWED_ALERT_CHANNELS = frozenset({"toast", "webhook", "email"})
DEFAULT_ALERT_CHANNELS = ["toast"]

#: Rangos NO enrutables a internet (RFC1918, loopback, link-local —incl. ``169.254.169.254``,
#: metadata cloud—, multicast, reservados/docs, CGNAT).
_BLOCKED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = tuple(
    ipaddress.ip_network(cidr) for cidr in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "255.255.255.255/32",
        "::/128",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
)


@dataclass(frozen=True, slots=True)
class AlertChannelDispatchResult:
    subscription_id: str
    channel: str
    ok: bool
    error: str | None = None
    #: v111 — trazabilidad del OUTBOX (``attempt`` tras la entrega; ``delivery_id`` si aplica).
    attempt: int = 0
    will_retry: bool = False
    delivery_id: str | None = None


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


def resolve_host_ips(host: str) -> list[str]:
    """Resuelve TODAS las direcciones de ``host`` (``getaddrinfo``), sin deduplicar por familia."""
    infos = socket.getaddrinfo(host, None)
    return list({str(info[4][0]) for info in infos})


def _is_blocked_ip(raw: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        # No es una IP literal: no se puede afirmar que sea segura ⇒ se rechaza (fail-closed).
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip in network for network in _BLOCKED_NETWORKS)


def _parse_allowed_hosts(allowed_hosts: Iterable[str] | str | None) -> set[str]:
    if allowed_hosts is None:
        return set()
    if isinstance(allowed_hosts, str):
        raw = allowed_hosts.split(",")
    else:
        raw = list(allowed_hosts)
    return {item.strip().lower() for item in raw if item and item.strip()}


def resolve_public_webhook_target(
    url: str | None,
    *,
    allowed_hosts: Iterable[str] | str | None = None,
    allow_http: bool = False,
    resolver: Callable[[str], list[str]] | None = None,
) -> tuple[str, list[str]]:
    """Valida la ``webhookUrl`` contra SSRF y devuelve ``(url, ips_validadas)``.

    Igual que :func:`assert_public_webhook_target` en la POLÍTICA (HTTPS salvo ``allow_http``,
    allowlist, rangos no enrutables/metadata fuera, fail-closed si no resuelve), pero además
    devuelve las IPs validadas para que el llamante **fije** la conexión a una de ellas y no
    deje que ``httpx`` vuelva a resolver el hostname (cierre del *DNS rebinding*).

    Para una IP literal devuelve ``[host]`` sin resolver. Un host no permitido/no resoluble
    lanza ``ValueError`` (fail-closed).
    """
    text = (url or "").strip()
    if not text:
        raise ValueError("webhookUrl es obligatorio con canal webhook")
    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()
    if scheme == "https":
        pass
    elif allow_http and scheme == "http":
        pass
    else:
        raise ValueError("webhookUrl debe usar https")

    host = parsed.hostname
    if not host:
        raise ValueError("webhookUrl debe ser una URL válida")

    allow = _parse_allowed_hosts(allowed_hosts)
    if allow and host.lower() not in allow:
        raise ValueError("webhookUrl host no permitido (allowlist)")

    # IP literal: se valida sin resolver.
    if _looks_like_ip(host):
        if _is_blocked_ip(host):
            raise ValueError("webhookUrl apunta a un rango de red no permitido")
        return text, [host]

    resolve = resolver or resolve_host_ips
    try:
        ips = resolve(host)
    except Exception as exc:  # noqa: BLE001 — no resoluble ⇒ no se conecta (fail-closed).
        raise ValueError(f"webhookUrl host no resoluble: {exc}") from exc
    if not ips:
        raise ValueError("webhookUrl host no resoluble")
    for ip in ips:
        if _is_blocked_ip(ip):
            raise ValueError("webhookUrl resuelve a un rango de red no permitido")
    return text, list(ips)


def assert_public_webhook_target(
    url: str | None,
    *,
    allowed_hosts: Iterable[str] | str | None = None,
    allow_http: bool = False,
    resolver: Callable[[str], list[str]] | None = None,
) -> str:
    """Valida la ``webhookUrl`` contra SSRF; devuelve la URL normalizada o lanza ``ValueError``.

    Exige HTTPS (salvo ``allow_http``), resuelve el DNS y rechaza si CUALQUIER dirección cae en
    un rango no enrutable o de metadata. Aplica allowlist de hosts cuando se declara.

    Delega en :func:`resolve_public_webhook_target` (fuente ÚNICA de la política); el camino de
    ENVÍO usa la variante que devuelve también las IPs para fijar la conexión.
    """
    text, _ips = resolve_public_webhook_target(
        url, allowed_hosts=allowed_hosts, allow_http=allow_http, resolver=resolver
    )
    return text


def _safe_port(parsed: ParseResult) -> int | None:
    """Puerto de una URL ya parseada; ``None`` si no lo declara o es inválido."""
    try:
        return parsed.port
    except ValueError:
        return None


def _pin_url_to_ip(url: str, ip: str) -> str:
    """Reescribe el host de ``url`` por la ``ip`` ya validada (conserva esquema/puerto/path/query).

    Es el punto que cierra el *DNS rebinding*: el cliente HTTP se conecta a esta URL (IP literal
    ⇒ no hay segunda resolución DNS) y el ``Host``/SNI originales viajan aparte. IPv6 se encierra
    entre corchetes.
    """
    parsed = urlparse(url)
    literal = f"[{ip}]" if ":" in ip else ip
    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo = f"{userinfo}:{parsed.password}"
        userinfo = f"{userinfo}@"
    port = _safe_port(parsed)
    netloc = f"{userinfo}{literal}" + (f":{port}" if port is not None else "")
    return urlunparse(parsed._replace(netloc=netloc))


def _host_header(url: str) -> str:
    """Valor del encabezado ``Host`` original (host + puerto NO por defecto)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    literal = f"[{host}]" if ":" in host else host
    port = _safe_port(parsed)
    default = 443 if (parsed.scheme or "").lower() == "https" else 80
    if port is not None and port != default:
        return f"{literal}:{port}"
    return literal



def _looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _settings_guard() -> tuple[bool, str | None]:
    try:
        settings = get_settings()
    except Exception:  # noqa: BLE001 — sin settings se aplica el modo estricto (https + sin allow).
        return False, None
    return settings.alert_webhook_allow_http, settings.alert_webhook_allowed_hosts


def validate_alert_channel_config(
    channels: list[str],
    *,
    webhook_url: str | None,
    email_to: str | None,
    allowed_hosts: Iterable[str] | str | None = None,
    allow_http: bool | None = None,
    resolver: Callable[[str], list[str]] | None = None,
) -> None:
    if "webhook" in channels:
        if allowed_hosts is None and allow_http is None:
            default_allow_http, default_allowed = _settings_guard()
            allowed_hosts = default_allowed
            allow_http = default_allow_http
        assert_public_webhook_target(
            webhook_url,
            allowed_hosts=allowed_hosts,
            allow_http=bool(allow_http),
            resolver=resolver,
        )

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
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        #: Transport opcional (inyectable en test para ejercitar el camino completo sin red).
        self._transport = transport

    async def dispatch(
        self,
        subscription: SignalAlertSubscriptionRecord,
        signal: Any,
    ) -> list[AlertChannelDispatchResult]:
        return await self.dispatch_channels(subscription, signal, channel=None)

    async def dispatch_channels(
        self,
        subscription: SignalAlertSubscriptionRecord,
        signal: Any,
        *,
        channel: str | None = None,
    ) -> list[AlertChannelDispatchResult]:
        """Despacha TODOS los canales o SOLO ``channel`` (para el worker del OUTBOX)."""
        channels = normalize_alert_channels(subscription.channels)
        if channel is not None:
            channels = [channel] if channel in channels else []
        results: list[AlertChannelDispatchResult] = []

        for name in channels:
            if name == "toast":
                continue
            if name == "webhook":
                results.append(await self._dispatch_webhook(subscription, signal))
            elif name == "email":
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
        max_bytes = self._settings.alert_webhook_max_response_bytes
        try:
            # Revalida el destino y FIJA las IPs validadas (el DNS pudo cambiar desde el alta y,
            # sobre todo, NO se deja que `httpx` re-resuelva al conectar: cierre del DNS rebinding).
            safe_url, ips = resolve_public_webhook_target(
                url,
                allowed_hosts=self._settings.alert_webhook_allowed_hosts,
                allow_http=self._settings.alert_webhook_allow_http,
            )
        except ValueError as exc:
            logger.warning(
                "Webhook alerta rechazado (SSRF) subscription=%s: %s", subscription.id, exc
            )
            return AlertChannelDispatchResult(
                subscription_id=subscription.id,
                channel="webhook",
                ok=False,
                error=str(exc),
            )

        host_header = _host_header(safe_url)
        sni_hostname = urlparse(safe_url).hostname
        last_connection_error: str | None = None
        # ``follow_redirects=False``: una redirección a un destino interno sería un bypass.
        # La URL de conexión lleva la IP **ya validada** como host (``_pin_url_to_ip``) y el
        # ``Host``/SNI originales viajan aparte: la conexión TCP va a la IP validada (sin segunda
        # resolución DNS) y TLS se valida contra el certificado del hostname.
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            for ip in ips:
                try:
                    response = await client.request(
                        "POST",
                        _pin_url_to_ip(safe_url, ip),
                        headers={"Host": host_header},
                        extensions={"sni_hostname": sni_hostname} if sni_hostname else None,
                        json=payload,
                    )
                    response.raise_for_status()
                    if max_bytes and len(response.content) > max_bytes:
                        raise ValueError(
                            "respuesta del webhook supera el tamaño máximo permitido"
                        )
                except httpx.TransportError as exc:
                    # Fallo de CONEXIÓN a ESTA IP: se intenta la siguiente IP ya validada
                    # (nunca se re-resuelve el hostname).
                    last_connection_error = str(exc)
                    logger.warning(
                        "Webhook alerta no conectó a %s subscription=%s: %s",
                        ip,
                        subscription.id,
                        exc,
                    )
                    continue
                except Exception as exc:
                    logger.warning(
                        "Webhook alerta falló subscription=%s url=%s: %s",
                        subscription.id,
                        safe_url,
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

        logger.warning(
            "Webhook alerta falló subscription=%s url=%s: %s",
            subscription.id,
            safe_url,
            last_connection_error,
        )
        return AlertChannelDispatchResult(
            subscription_id=subscription.id,
            channel="webhook",
            ok=False,
            error=last_connection_error,
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
