"""V2.31 / A11 — dispatch declarativo del LAB (Discovery) (tests herméticos).

Certifica que ``RunSmaGridOptimize.execute(definition=...)`` optimiza una familia del
catálogo de Discovery con el grid genérico de reglas, devolviendo un resultado
compatible con el resto del lifecycle (trials rankeados, familia preservada y engine
``rules_grid_h0``), sin exigir que el nombre de familia sea uno de los tres H0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pytest

from bolsa_application.optimize import RunSmaGridOptimize

# ── Dobles de repositorio ───────────────────────────────────────────────────────


@dataclass
class _Instrument:
    id: str


@dataclass
class _Bar:
    timestamp: str
    close: float
    open: float
    high: float
    low: float
    volume: float


class _Instruments:
    async def get_by_id(self, instrument_id: str) -> Any:
        return _Instrument(id=instrument_id) if instrument_id == "AAA" else None


class _Ohlcv:
    def __init__(self, count: int = 300) -> None:
        self._bars = []
        for i in range(count):
            price = 100 + 20 * math.sin(i / 12.0) + i * 0.05
            self._bars.append(
                _Bar(
                    timestamp=f"2026-{i:04d}",
                    close=price,
                    open=price,
                    high=price * 1.01,
                    low=price * 0.99,
                    volume=1000.0,
                )
            )

    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: Any = None,
        limit: int = 0,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> Any:
        bars = list(self._bars)
        if date_to is not None:
            bars = [b for b in bars if b.timestamp <= date_to]
        if date_from is not None:
            bars = [b for b in bars if b.timestamp >= date_from]
        return bars[:limit] if limit else bars


def _bb_reversion_definition() -> dict[str, Any]:
    lower = {"definitionId": "bb", "parameters": {"period": 20, "stdDev": 2.0, "line": "lower"}}
    mid = {"definitionId": "bb", "parameters": {"period": 20, "stdDev": 2.0, "line": "mid"}}
    return {
        "presetKey": "bb_reversion",
        "indicatorSpecs": [lower, mid],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "price_vs_indicator",
                    "indicatorSpec": lower,
                    "operator": "lt",
                    "signalKind": "entry_long",
                }
            ],
        },
        "exits": {
            "operator": "all",
            "rules": [
                {
                    "type": "price_vs_indicator",
                    "indicatorSpec": mid,
                    "operator": "gt",
                    "signalKind": "exit",
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_lab_dispatches_declarative_family() -> None:
    """Una familia del catálogo (no-H0) se optimiza por reglas declarativas."""
    use_case = RunSmaGridOptimize(_Instruments(), _Ohlcv())
    result = await use_case.execute(
        instrument_id="AAA",
        strategy_family="bb_reversion",
        definition=_bb_reversion_definition(),
        bar_limit=300,
        max_trials=10,
    )
    assert result.strategy_family == "bb_reversion"
    assert result.engine == "rules_grid_h0"
    assert result.trials
    scores = [trial.score for trial in result.trials]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_lab_unknown_instrument_still_fail_closed() -> None:
    use_case = RunSmaGridOptimize(_Instruments(), _Ohlcv())
    with pytest.raises(ValueError):
        await use_case.execute(
            instrument_id="ZZZ",
            strategy_family="bb_reversion",
            definition=_bb_reversion_definition(),
        )


@pytest.mark.asyncio
async def test_lab_classic_family_unaffected_by_definition_param() -> None:
    """Sin ``definition`` el LAB sigue el camino H0 clásico (SMA)."""
    use_case = RunSmaGridOptimize(_Instruments(), _Ohlcv())
    result = await use_case.execute(
        instrument_id="AAA",
        strategy_family="sma_crossover",
        bar_limit=300,
        max_trials=10,
    )
    assert result.strategy_family == "sma_crossover"
    assert "sma" in result.engine
    assert result.engine != "rules_grid_h0"
