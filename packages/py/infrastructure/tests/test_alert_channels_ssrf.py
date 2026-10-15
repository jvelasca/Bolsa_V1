"""v111 — anti-SSRF de ``webhookUrl`` (hallazgo 5). Tests herméticos, sin red.

``assert_public_webhook_target`` nunca se conecta: el DNS se inyecta con ``resolver``, así que
estos tests fijan la política (HTTPS obligatorio, rangos no enrutables y metadata cloud fuera,
allowlist, fail-closed ante host no resoluble).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from bolsa_infrastructure.alerts.alert_channels import (
    assert_public_webhook_target,
    resolve_host_ips,
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
