"""B-6 en el scan: «no evaluable» deja de publicarse como «sin señal».

El defecto medido: con ``bar_limit = 120`` y el preset ``golden_cross`` (SMA 50/200),
el scan devolvía **cero hits y cero motivos**. La ventana no alcanzaba el warmup del
preset, las series del contexto quedaban en ``None``, la regla no disparaba y el
resultado se leía como «el mercado no dio señal». El instrumento se contaba igual que
uno evaluado sin señal.

Lo que se fija aquí, y nada más:

1. Con la ventana corta, el instrumento sale en ``skipped`` con motivo
   ``warmup_insufficient`` — no en ``hits`` vacíos sin explicación.
2. Con la ventana que cubre el warmup, el instrumento **no** se omite: el chequeo no
   puede convertir señales reales en omisiones.
3. El umbral respeta la naturaleza del cruce: 200 barras alcanzan para SMA200 pero no
   para el cruce, que necesita la barra anterior.

Los dobles son en memoria: ninguna prueba toca base de datos, ficheros ni la ventana.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from bolsa_analytics.signals.preset_evaluability import WARMUP_INSUFFICIENT
from bolsa_application.scans import RunScan, ScanRunResult

SYMBOL = "AAA"
INSTRUMENT_ID = "inst-aaa"


@dataclass(frozen=True)
class _Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class _Instrument:
    id: str
    symbol: str
    name: str
    exchange: str
    country: str


class _Instruments:
    async def get_by_id(self, instrument_id: str) -> _Instrument | None:
        if instrument_id != INSTRUMENT_ID:
            return None
        return _Instrument(
            id=INSTRUMENT_ID,
            symbol=SYMBOL,
            name="Instrumento de prueba",
            exchange="BME",
            country="ES",
        )

    async def get_last_sync_detail(self, instrument_id: str) -> None:
        return None

    async def get_fundamentals(self, instrument_id: str) -> None:
        return None


class _Ohlcv:
    """Devuelve exactamente ``bar_count`` barras, ignorando el ``limit`` de más."""

    def __init__(self, bar_count: int) -> None:
        self._bar_count = bar_count

    async def get_bars(
        self, instrument_id: str, *, timeframe: Any = None, limit: int | None = None
    ) -> list[_Bar]:
        count = self._bar_count if limit is None else min(self._bar_count, int(limit))
        return [
            _Bar(
                timestamp=f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
                open=100.0 + 0.1 * index - 0.2,
                high=100.0 + 0.1 * index + 0.5,
                low=100.0 + 0.1 * index - 0.5,
                close=100.0 + 0.1 * index,
                volume=1000.0,
            )
            for index in range(count)
        ]


async def _scan(*, preset: str, bar_count: int) -> ScanRunResult:
    run_scan = RunScan(
        instrument_repository=_Instruments(),  # type: ignore[arg-type]
        ohlcv_repository=_Ohlcv(bar_count),  # type: ignore[arg-type]
        strategy_repository=None,  # type: ignore[arg-type]
        list_repository=None,  # type: ignore[arg-type]
    )
    return await run_scan.execute(
        universe_instrument_ids=[INSTRUMENT_ID],
        preset_key=preset,
        bar_limit=bar_count,
    )


def _warmup_reasons(result: ScanRunResult) -> list[str]:
    return [
        skipped.reason
        for skipped in result.skipped
        if skipped.reason.startswith(WARMUP_INSUFFICIENT)
    ]


@pytest.mark.asyncio
async def test_scan_rejects_preset_below_warmup() -> None:
    """120 barras con ``golden_cross``: motivo explícito, ni un hit ni un silencio."""
    result = await _scan(preset="golden_cross", bar_count=120)

    assert result.hits == []
    assert result.hit_count == 0
    assert len(_warmup_reasons(result)) == 1
    assert _warmup_reasons(result)[0].startswith(f"{WARMUP_INSUFFICIENT}: sma period=200")


@pytest.mark.asyncio
async def test_the_skipped_instrument_is_not_counted_as_a_silent_zero() -> None:
    """El defecto era el silencio: el instrumento debe aparecer en ``skipped``.

    Antes de B-6 este mismo caso devolvía ``skipped == []`` y ``hits == []``: el
    instrumento desaparecía del recuento, que es lo que se leía como «sin señal».
    """
    result = await _scan(preset="golden_cross", bar_count=120)

    assert [skipped.instrument_id for skipped in result.skipped] == [INSTRUMENT_ID]


@pytest.mark.asyncio
async def test_scan_evaluates_the_preset_when_the_window_covers_the_warmup() -> None:
    """201 barras: el preset es evaluable y no se omite por warmup."""
    result = await _scan(preset="golden_cross", bar_count=201)

    assert _warmup_reasons(result) == []


@pytest.mark.asyncio
async def test_two_hundred_bars_cover_the_series_but_not_the_cross() -> None:
    """B-1 en el scan: SMA200 sí, el cruce no. El umbral no es ``period``."""
    result = await _scan(preset="golden_cross", bar_count=200)

    reasons = _warmup_reasons(result)
    assert len(reasons) == 1
    assert "requiere >= 201 barras" in reasons[0]


@pytest.mark.asyncio
async def test_a_light_preset_is_evaluable_at_the_scan_minimum() -> None:
    """Anti-falso-positivo: ``vwap_reclaim`` se evalúa con la ventana mínima del scan."""
    result = await _scan(preset="vwap_reclaim", bar_count=50)

    assert _warmup_reasons(result) == []


def test_the_scan_default_window_covers_every_preset() -> None:
    """B-1 — guardián: la ventana por defecto del scan (500) cubre el warmup de TODO preset.

    El scan no se toca en el sello de la ventana derivada, pero si mañana un preset
    entrara con un warmup mayor que el defecto, el scan volvería a omitirlo en silencio.
    Este guardián rota el test en vez de degradar la cobertura sin avisar.
    """
    from inspect import signature

    from bolsa_analytics.research.manifest import strategy_definition_from_preset
    from bolsa_analytics.signals.preset_catalog import load_preset_catalog
    from bolsa_analytics.signals.preset_evaluability import measured_warmup_bars

    default_bar_limit = signature(RunScan.execute).parameters["bar_limit"].default
    assert default_bar_limit == 500

    offenders = {}
    for preset in sorted(load_preset_catalog()["presets"]):
        required = measured_warmup_bars(strategy_definition_from_preset(preset, [SYMBOL]))
        if required is None or required > default_bar_limit:
            offenders[preset] = required
    assert offenders == {}
