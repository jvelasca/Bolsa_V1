"""v111 — anti-SSRF de ``webhookUrl`` (hallazgo 5). Tests herméticos, sin red.

``assert_public_webhook_target`` nunca se conecta: el DNS se inyecta con ``resolver``, así que
estos tests fijan la política (HTTPS obligatorio, rangos no enrutables y metadata cloud fuera,
allowlist, fail-closed ante host no resoluble).
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import patch

import httpx
import pytest

from bolsa_infrastructure.alerts import alert_channels
from bolsa_infrastructure.alerts.alert_channels import (
    SignalAlertChannelDispatcher,
    _host_header,
    _pin_url_to_ip,
    assert_public_webhook_target,
    resolve_host_ips,
    resolve_public_webhook_target,
)
from bolsa_infrastructure.config import Settings
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
)


def _resolver(mapping: dict[str, list[str]]) -> Callable[[str], list[str]]:
    def _resolve(host: str) -> list[str]:
        if host not in mapping:
            raise OSError(f"no resoluble: {host}")
        return mapping[host]

    return _resolve


def test_accepts_https_public_host() -> None:
    url = "https://hooks.example.com/alert"
    resolve = _resolver({"hooks.example.com": ["93.184.216.34"]})
    assert assert_public_webhook_target(url, resolver=resolve) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.com/alert",
        "ftp://hooks.example.com/alert",
        "hooks.example.com/alert",
        "",
        "   ",
    ],
)
def test_rejects_missing_or_non_https_scheme(url: str) -> None:
    with pytest.raises(ValueError):
        assert_public_webhook_target(url, resolver=_resolver({"hooks.example.com": ["8.8.8.8"]}))


def test_http_only_with_explicit_opt_in() -> None:
    url = "http://hooks.example.com/alert"
    resolve = _resolver({"hooks.example.com": ["8.8.8.8"]})
    assert assert_public_webhook_target(url, allow_http=True, resolver=resolve) == url


def test_none_is_rejected() -> None:
    with pytest.raises(ValueError, match="obligatorio"):
        assert_public_webhook_target(None)


def test_url_without_host_is_rejected() -> None:
    with pytest.raises(ValueError, match="URL válida"):
        assert_public_webhook_target("https:///no-host")


@pytest.mark.parametrize(
    "literal",
    [
        "127.0.0.1",
        "0.0.0.0",
        "10.0.0.5",
        "172.16.9.9",
        "192.168.1.20",
        "169.254.169.254",  # metadata cloud
        "100.64.0.1",  # CGNAT
        "[::1]",
        "[fd00::1]",
        "[::ffff:10.0.0.1]",  # IPv4 mapeada en IPv6
    ],
)
def test_rejects_literal_non_routable_hosts_without_resolving(literal: str) -> None:
    def _never_called(_host: str) -> list[str]:
        raise AssertionError("no debe resolver: ya es una IP literal")

    with pytest.raises(ValueError, match="rango de red no permitido"):
        assert_public_webhook_target(f"https://{literal}/x", resolver=_never_called)


@pytest.mark.parametrize(
    "ips",
    [
        ["10.1.2.3"],
        ["93.184.216.34", "192.168.0.1"],  # basta UNA bloqueada
        ["169.254.169.254"],
        ["fe80::1"],
    ],
)
def test_rejects_host_resolving_to_a_blocked_range(ips: list[str]) -> None:
    resolve = _resolver({"evil.example.com": ips})
    with pytest.raises(ValueError, match="rango de red no permitido"):
        assert_public_webhook_target("https://evil.example.com/x", resolver=resolve)


def test_fail_closed_when_host_is_not_resolvable() -> None:
    with pytest.raises(ValueError, match="no resoluble"):
        assert_public_webhook_target("https://nope.example.com/x", resolver=_resolver({}))


def test_fail_closed_when_resolution_returns_nothing() -> None:
    with pytest.raises(ValueError, match="no resoluble"):
        assert_public_webhook_target("https://empty.example.com/x", resolver=lambda _h: [])


def test_allowlist_rejects_absent_host_and_accepts_present_one() -> None:
    resolve = _resolver({"hooks.example.com": ["8.8.8.8"]})
    with pytest.raises(ValueError, match="allowlist"):
        assert_public_webhook_target(
            "https://hooks.example.com/x", allowed_hosts=["otro.example.com"], resolver=resolve
        )
    url = "https://hooks.example.com/x"
    assert (
        assert_public_webhook_target(url, allowed_hosts=["hooks.example.com"], resolver=resolve)
        == url
    )
    # La allowlist admite CSV (como llega del entorno).
    assert (
        assert_public_webhook_target(
            url, allowed_hosts="a.example.com, hooks.example.com", resolver=resolve
        )
        == url
    )


def test_default_resolver_is_the_real_lookup_and_localhost_is_rejected() -> None:
    """Sin ``resolver`` inyectado se usa el DNS real (no hay camino que lo salte)."""
    assert resolve_host_ips("localhost")
    with pytest.raises(ValueError, match="rango de red no permitido"):
        assert_public_webhook_target("https://localhost/x")


def test_resolve_returns_the_validated_ips_for_pinning() -> None:
    resolve = _resolver({"hooks.example.com": ["93.184.216.34", "1.1.1.1"]})
    text, ips = resolve_public_webhook_target("https://hooks.example.com/x", resolver=resolve)
    assert text == "https://hooks.example.com/x"
    assert ips == ["93.184.216.34", "1.1.1.1"]


def test_resolve_literal_ip_needs_no_dns() -> None:
    def _never_called(_host: str) -> list[str]:
        raise AssertionError("una IP literal no debe resolverse")

    text, ips = resolve_public_webhook_target("https://8.8.4.4/x", resolver=_never_called)
    assert text == "https://8.8.4.4/x"
    assert ips == ["8.8.4.4"]


@pytest.mark.parametrize(
    ("url", "ip", "expected"),
    [
        ("https://hooks.example.com/x", "93.184.216.34", "https://93.184.216.34/x"),
        ("https://hooks.example.com:8443/x?a=1", "93.184.216.34", "https://93.184.216.34:8443/x?a=1"),
        ("https://hooks.example.com/x", "2001:db8::1", "https://[2001:db8::1]/x"),
    ],
)
def test_pin_url_to_ip_rewrites_only_the_host(url: str, ip: str, expected: str) -> None:
    assert _pin_url_to_ip(url, ip) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://hooks.example.com/x", "hooks.example.com"),
        ("https://hooks.example.com:8443/x", "hooks.example.com:8443"),
        ("https://[2001:db8::1]/x", "[2001:db8::1]"),
    ],
)
def test_host_header_preserves_the_original_host(url: str, expected: str) -> None:
    assert _host_header(url) == expected


# --- Cierre del DNS rebinding: la conexión va a la IP VALIDADA, sin segunda resolución ------


class _FakeSignal:
    id = "sig-1"
    instrument_id = "inst-1"
    timestamp = "2024-01-10"
    kind = "entry_long"
    strategy_definition_id = "strat-1"
    strategy_version = 1
    bar_index = 59
    price = 12.34
    data_version = None
    indicator_snapshot_hash = None
    preset_key = "sma_crossover"


def _webhook_subscription(url: str) -> SignalAlertSubscriptionRecord:
    return SignalAlertSubscriptionRecord(
        id="sub-1",
        instrument_id="inst-1",
        symbol="SAN.MC",
        strategy_definition_id=None,
        preset_key="sma_crossover",
        timeframe="1d",
        signal_kinds=["entry_long"],
        channels=["webhook"],
        webhook_url=url,
        email_to=None,
        is_active=True,
        last_triggered_at=None,
        last_bar_timestamp=None,
        last_signal_kind=None,
        last_signal_price=None,
        note=None,
        created_at="2024-01-01T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_dispatch_webhook_pins_connection_to_the_validated_ip() -> None:
    """La conexión real va a la IP validadas (no hay segunda resolución de DNS).

    Falsable: con la implementación previa (``assert_public_webhook_target`` devolvía la URL con
    el hostname y ``httpx`` re-resolvía al conectar), la petición capturada tendría
    ``request.url.host == "hooks.example.com"`` y este test caería. Aquí la segunda resolución
    DNS devolvería ``169.254.169.254`` (metadata cloud); comprobamos que NUNCA se usa.
    """
    validated_ip = "93.184.216.34"
    attacker_ip = "169.254.169.254"
    calls: list[str] = []

    def _resolver(host: str) -> list[str]:
        calls.append(host)
        # La 1ª resolución (validación) es pública; cualquier resolución POSTERIOR (la que haría
        # httpx al conectar) devolvería metadata cloud: si el código la consultara, la conexión
        # saldría hacia la IP interna.
        return [validated_ip] if len(calls) == 1 else [attacker_ip]

    captured: list[httpx.Request] = []

    async def _handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"{}")

    settings = Settings(alert_webhook_timeout_seconds=5.0)
    dispatcher = SignalAlertChannelDispatcher(settings, transport=httpx.MockTransport(_handler))

    with patch.object(alert_channels, "resolve_host_ips", side_effect=_resolver):
        results = await dispatcher.dispatch(
            _webhook_subscription("https://hooks.example.com/signal"), _FakeSignal()
        )

    assert len(results) == 1
    assert results[0].ok is True
    assert calls == ["hooks.example.com"]  # UNA sola resolución: no hay ventana de rebinding
    assert len(captured) == 1
    request = captured[0]
    assert request.url.host == validated_ip  # la conexión va a la IP VALIDADA
    assert request.url.host != attacker_ip
    assert request.headers["host"] == "hooks.example.com"  # Host original conservado
    assert request.extensions.get("sni_hostname") == "hooks.example.com"  # SNI original


@pytest.mark.asyncio
async def test_dispatch_webhook_revalidates_and_blocks_before_connecting() -> None:
    """Un destino que resuelve a metadata cloud ni siquiera abre el cliente HTTP."""
    settings = Settings(alert_webhook_timeout_seconds=5.0)
    dispatcher = SignalAlertChannelDispatcher(
        settings,
        transport=httpx.MockTransport(
            lambda _request: pytest.fail("no debe conectarse a un destino bloqueado")
        ),
    )
    with patch.object(alert_channels, "resolve_host_ips", return_value=["169.254.169.254"]):
        results = await dispatcher.dispatch(
            _webhook_subscription("https://metadata.example.com/x"), _FakeSignal()
        )
    assert len(results) == 1
    assert results[0].ok is False
    assert "rango de red" in (results[0].error or "")
