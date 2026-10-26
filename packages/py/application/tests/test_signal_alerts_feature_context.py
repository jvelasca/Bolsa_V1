"""Contrato scan↔alerta: la alerta evalúa la MISMA feature OHLCV que el scan (B-4).

Sin contexto, ``evaluate_strategy_last_bar`` reconstruye barras close-only con volumen 0 y
los presets de volumen/rango (VWAP, ATR, CCI) divergen del scan. Estas pruebas fijan que el
``indicator_context`` viaja hasta el motor y que el helper conserva rango y volumen.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from bolsa_application import signal_alerts as signal_alerts_module
from bolsa_application.signal_alerts import EvaluateSignalAlertSubscriptions
from bolsa_application.signal_feature_context import (
    build_signal_indicator_context,
    to_ohlcv_bars,
)
from bolsa_domain.platform_kernel import MIN_SCAN_BARS
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
)


@dataclass(frozen=True)
class _Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class _CloseBar:
    """Barra legacy: solo cierre (sin rango ni volumen)."""

    timestamp: str
    close: float


def _bars(count: int = MIN_SCAN_BARS) -> list[_Bar]:
    return [
        _Bar(
            timestamp=f"2026-01-{index + 1:02d}",
            open=100.0,
            high=100.8,
            low=99.2,
            close=100.0 + (0.05 if index % 2 else -0.05),
            volume=1200.0 + index,
        )
        for index in range(count)
    ]


def _subscription() -> SignalAlertSubscriptionRecord:
    return SignalAlertSubscriptionRecord(
        id="sub-1",
        instrument_id="AAA",
        symbol="AAA",
        strategy_definition_id=None,
        preset_key="vwap_reclaim",
        timeframe="1d",
        signal_kinds=["entry_long", "exit"],
        channels=["toast"],
        webhook_url=None,
        email_to=None,
        is_active=True,
        last_triggered_at=None,
        last_bar_timestamp=None,
        last_signal_kind=None,
        last_signal_price=None,
        note=None,
        created_at="2026-01-01",
    )


class _SubscriptionRepo:
    async def list_all(self, *, account_id: str | None = None, active_only: bool = False) -> list[Any]:
        return [_subscription()]


class _StrategyRepo:
    async def get_definition(self, definition_id: str) -> Any:
        return None


class _OhlcvRepo:
    def __init__(self, bars: list[Any]) -> None:
        self._bars = bars

    async def get_bars(self, instrument_id: str, *, timeframe: Any, limit: int) -> list[Any]:
        return self._bars


def test_the_helper_keeps_high_low_and_volume() -> None:
    """El helper no degrada la barra a cierre: rango y volumen llegan a los indicadores."""
    bars = to_ohlcv_bars(_bars(3))
    assert [bar.high for bar in bars] == [100.8, 100.8, 100.8]
    assert [bar.low for bar in bars] == [99.2, 99.2, 99.2]
    assert [bar.volume for bar in bars] == [1200.0, 1201.0, 1202.0]


def test_the_helper_falls_back_to_close_with_zero_volume() -> None:
    """Fail-closed: una barra sin rango usa el cierre como OHLC y volumen 0."""
    (bar,) = to_ohlcv_bars([_CloseBar(timestamp="2026-01-01", close=42.5)])
    assert (bar.open, bar.high, bar.low, bar.close) == (42.5, 42.5, 42.5, 42.5)
    assert bar.volume == 0.0


def test_the_context_carries_the_preset_indicators() -> None:
    definition = {
        "presetKey": "vwap_reclaim",
        "indicatorSpecs": [{"definitionId": "vwap", "parameters": {}}],
        "universe": {"instrumentIds": ["AAA"]},
    }
    context = build_signal_indicator_context(_bars(), definition)
    assert context, "el contexto no puede quedar vacío para un preset con indicadores"
    assert any("vwap" in key.lower() for key in context)


def test_the_alert_evaluates_with_the_ohlcv_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regresión B-4: la llamada al motor recibe ``indicator_context`` no nulo."""
    captured: dict[str, Any] = {}
    real_evaluate = signal_alerts_module.evaluate_strategy_last_bar

    def _spy(*args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        captured["args"] = args
        return real_evaluate(*args, **kwargs)

    monkeypatch.setattr(signal_alerts_module, "evaluate_strategy_last_bar", _spy)

    use_case = EvaluateSignalAlertSubscriptions(
        _SubscriptionRepo(),  # type: ignore[arg-type]
        _StrategyRepo(),  # type: ignore[arg-type]
        _OhlcvRepo(_bars()),  # type: ignore[arg-type]
    )
    event = asyncio.run(use_case._evaluate_subscription(_subscription()))

    assert "indicator_context" in captured, "la alerta debe pasar el contexto al motor"
    assert captured["indicator_context"], "el contexto no puede ser vacío ni None"
    vwap_series = [
        values
        for key, values in captured["indicator_context"].items()
        if "vwap" in key.lower()
    ]
    assert vwap_series, "el contexto debe traer la serie del VWAP"
    assert any(value is not None for value in vwap_series[0]), (
        "el VWAP necesita volumen: si la serie es toda None, la feature no llegó"
    )
    # El cierre de la última barra supera el VWAP y la alerta se emite: evaluada, no un no-op.
    assert event is not None and event.kind == "entry_long"


def test_the_alert_without_context_would_miss_the_vwap() -> None:
    """Control negativo: con barras close-only el VWAP es ausente (toda la serie None).

    Fija que la prueba anterior no es un falso verde por no-op: sin volumen el indicador no
    se puede calcular, que es exactamente lo que le pasaba a la alerta antes del fix.
    """
    close_only = [_CloseBar(timestamp=f"2026-01-{index + 1:02d}", close=100.0) for index in range(5)]
    definition = {
        "presetKey": "vwap_reclaim",
        "indicatorSpecs": [{"definitionId": "vwap", "parameters": {}}],
        "universe": {"instrumentIds": ["AAA"]},
    }
    close_only_context = build_signal_indicator_context(close_only, definition)
    ohlcv_context = build_signal_indicator_context(_bars(5), definition)
    close_only_vwap = [
        values for key, values in close_only_context.items() if "vwap" in key.lower()
    ][0]
    ohlcv_vwap = [values for key, values in ohlcv_context.items() if "vwap" in key.lower()][0]
    assert all(value is None for value in close_only_vwap)
    assert any(value is not None for value in ohlcv_vwap)
