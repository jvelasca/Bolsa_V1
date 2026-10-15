from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bolsa_infrastructure.alerts import alert_channels
from bolsa_infrastructure.alerts.alert_channels import (
    SignalAlertChannelDispatcher,
    assert_public_webhook_target,
    normalize_alert_channels,
    signal_event_to_payload,
    validate_alert_channel_config,
)
from bolsa_infrastructure.config import Settings
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
)

_PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def _public_dns() -> None:
    """Resuelve cualquier host a una IP pública salvo en los tests de SSRF que lo parchean."""
    with patch.object(alert_channels, "resolve_host_ips", return_value=[_PUBLIC_IP]):
        yield


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


def _subscription(**overrides) -> SignalAlertSubscriptionRecord:
    base = SignalAlertSubscriptionRecord(
        id="sub-1",
        instrument_id="inst-1",
        symbol="SAN.MC",
        strategy_definition_id=None,
        preset_key="sma_crossover",
        timeframe="1d",
        signal_kinds=["entry_long"],
        channels=["webhook"],
        webhook_url="https://hooks.example.com/signal",
        email_to=None,
        is_active=True,
        last_triggered_at=None,
        last_bar_timestamp=None,
        last_signal_kind=None,
        last_signal_price=None,
        note=None,
        created_at="2024-01-01T00:00:00+00:00",
    )
    return replace(base, **overrides)


def test_normalize_alert_channels_defaults() -> None:
    assert normalize_alert_channels(None) == ["toast"]


def test_validate_alert_channel_config_webhook_requires_url() -> None:
    with pytest.raises(ValueError, match="webhookUrl"):
        validate_alert_channel_config(["webhook"], webhook_url=None, email_to=None)


def test_validate_alert_channel_config_rejects_http() -> None:
    with pytest.raises(ValueError, match="https"):
        validate_alert_channel_config(
            ["webhook"], webhook_url="http://hooks.example.com/signal", email_to=None
        )


def test_validate_alert_channel_config_rejects_private_ip() -> None:
    with patch.object(alert_channels, "resolve_host_ips", return_value=["10.0.0.5"]):
        with pytest.raises(ValueError, match="rango de red"):
            validate_alert_channel_config(
                ["webhook"], webhook_url="https://internal.example.com/signal", email_to=None
            )


def test_validate_alert_channel_config_rejects_metadata_ip() -> None:
    with patch.object(alert_channels, "resolve_host_ips", return_value=["169.254.169.254"]):
        with pytest.raises(ValueError, match="rango de red"):
            validate_alert_channel_config(
                ["webhook"], webhook_url="https://metadata.example.com/signal", email_to=None
            )


def test_validate_alert_channel_config_rejects_loopback() -> None:
    with patch.object(alert_channels, "resolve_host_ips", return_value=["127.0.0.1"]):
        with pytest.raises(ValueError, match="rango de red"):
            validate_alert_channel_config(
                ["webhook"], webhook_url="https://localhost.example.com/signal", email_to=None
            )


def test_validate_alert_channel_config_enforces_allowlist() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        validate_alert_channel_config(
            ["webhook"],
            webhook_url="https://hooks.example.com/signal",
            email_to=None,
            allowed_hosts="allowed.example.com",
        )


def test_assert_public_webhook_target_rejects_literal_private_ip() -> None:
    with pytest.raises(ValueError, match="rango de red"):
        assert_public_webhook_target("https://192.168.1.10/hook")


def test_signal_event_to_payload_shape() -> None:
    payload = signal_event_to_payload(_subscription(), _FakeSignal())
    assert payload["type"] == "signal_alert"
    assert payload["symbol"] == "SAN.MC"
    assert payload["signal"]["kind"] == "entry_long"


@pytest.mark.asyncio
async def test_dispatch_webhook_success() -> None:
    settings = Settings(alert_webhook_timeout_seconds=5.0)
    dispatcher = SignalAlertChannelDispatcher(settings)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"{}"

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "bolsa_infrastructure.alerts.alert_channels.httpx.AsyncClient",
        return_value=mock_client,
    ):
        results = await dispatcher.dispatch(_subscription(), _FakeSignal())

    assert len(results) == 1
    assert results[0].ok is True
    assert results[0].channel == "webhook"
    mock_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_webhook_failure() -> None:
    settings = Settings(alert_webhook_timeout_seconds=5.0)
    dispatcher = SignalAlertChannelDispatcher(settings)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "bolsa_infrastructure.alerts.alert_channels.httpx.AsyncClient",
        return_value=mock_client,
    ):
        results = await dispatcher.dispatch(_subscription(), _FakeSignal())

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error is not None


@pytest.mark.asyncio
async def test_dispatch_webhook_blocked_before_connect() -> None:
    settings = Settings(alert_webhook_timeout_seconds=5.0)
    dispatcher = SignalAlertChannelDispatcher(settings)

    with patch.object(alert_channels, "resolve_host_ips", return_value=["169.254.169.254"]):
        results = await dispatcher.dispatch(_subscription(), _FakeSignal())

    assert len(results) == 1
    assert results[0].ok is False
    assert "rango de red" in (results[0].error or "")
