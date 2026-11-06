"""S4 — el contrato HTTP de señales publica ``signalBar`` y ``executionBar``.

Auditoría .183: la señal se decide con la barra cerrada ``t`` y se ejecuta en la
``t + 1``; el contrato no lo imponía y un consumidor podía operar en la misma barra.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from bolsa_api.api.v1.routes.signals_evaluate import evaluate_signals
from bolsa_api.schemas.indicators_compute import OhlcvBarInputDto
from bolsa_api.schemas.signals_evaluate import EvaluateSignalsRequestDto

_SMA_CROSSOVER = {
    "id": "preset:sma_crossover",
    "version": 1,
    "name": "Cruce SMA 20/50",
    "kind": "indicator_signals",
    "presetKey": "sma_crossover",
    "universe": {"instrumentIds": ["inst-1"]},
    "timeframe": "1d",
    "indicatorSpecs": [
        {"definitionId": "sma", "parameters": {"period": 20}},
        {"definitionId": "sma", "parameters": {"period": 50}},
    ],
}


def _bars() -> list[OhlcvBarInputDto]:
    """Serie en V (baja y luego sube): las SMA 20/50 se cruzan y emiten señal."""
    closes = [130.0 - index for index in range(30)] + [100.0 + index for index in range(1, 31)]
    return [
        OhlcvBarInputDto(
            timestamp=f"2024-01-{day:02d}",
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000.0,
        )
        for day, close in enumerate(closes, start=1)
    ]


@pytest.mark.asyncio
async def test_evaluate_signals_publishes_explicit_timing() -> None:
    response = await evaluate_signals(
        EvaluateSignalsRequestDto(
            definition=_SMA_CROSSOVER,
            instrument_id="inst-1",
            bars=_bars(),
            mode="raw",
        )
    )

    assert response.data, "la serie debe producir señales"
    for event in response.data:
        assert event.signal_bar == event.bar_index
        assert event.execution_bar == event.bar_index + 1
        assert event.execution_bar is not None
        assert event.execution_bar > event.signal_bar


@pytest.mark.asyncio
async def test_route_rejects_a_signal_with_lookahead(monkeypatch) -> None:
    """La guarda del router no publica una señal ejecutable en su propia barra."""
    from bolsa_analytics.signals import strategy as strategy_module

    bars = _bars()
    last_index = len(bars) - 1
    lookahead_event = strategy_module.SignalEventV1(
        id="sig:lookahead",
        instrument_id="inst-1",
        timestamp=bars[-1].timestamp,
        kind="entry_long",
        strategy_definition_id="preset:sma_crossover",
        strategy_version=1,
        bar_index=last_index,
        price=bars[-1].close,
        signal_bar=last_index,
        execution_bar=last_index,
    )

    def fake_evaluate(*_args, **_kwargs):
        return [lookahead_event]

    monkeypatch.setattr(
        "bolsa_api.api.v1.routes.signals_evaluate.evaluate_strategy",
        fake_evaluate,
    )

    with pytest.raises(HTTPException) as exc:
        await evaluate_signals(
            EvaluateSignalsRequestDto(
                definition=_SMA_CROSSOVER,
                instrument_id="inst-1",
                bars=bars,
                mode="raw",
            )
        )

    assert exc.value.status_code == 500
    assert "signal timing contract violated" in str(exc.value.detail)
