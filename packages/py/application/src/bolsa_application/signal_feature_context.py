"""Procedencia ÚNICA de la feature de señal para scan, alertas y decisor ACTIVE.

El motor declarativo (``evaluate_rules_signals``) evalúa los indicadores que recibe en
``indicator_context``. Cuando ese contexto no llega, fabrica barras sintéticas
``open = high = low = close`` y ``volume = 0``: los indicadores de rango y de volumen
(VWAP, SuperTrend, CCI, Stoch sobre rango) cambian de valor, y en VWAP el indicador
desaparece (``cum_vol = 0``). Eso hacía que el decisor ACTIVE y las alertas no evaluaran
la MISMA señal que el scan sobre las mismas barras.

Este módulo concentra la conversión para que los tres caminos consuman exactamente la
misma representación: barras OHLCV reales cuando existen, y un fallback **declarado** —
``close`` como OHLC y ``volume = 0`` — cuando la barra no trae los campos.

Regla: si una barra no declara ``open``/``high``/``low``/``volume``, se usa ``close`` y
``volume = 0``. Es *fail-closed* en el sentido de que no inventa rango; y es **idéntico** al
comportamiento previo del motor para datos close-only, de modo que las pruebas que solo
tienen cierres no cambian.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.rules_engine import build_indicator_context

__all__ = [
    "bar_field",
    "build_signal_indicator_context",
    "feature_source",
    "to_ohlcv_bars",
]

#: La barra traía OHLCV: la feature se calculó con el dato real.
FEATURE_SOURCE_REAL = "real"

#: La barra venía close-only: el motor usó ``open = high = low = close`` y ``volume = 0``.
FEATURE_SOURCE_SYNTHETIC = "synthetic"


def bar_field(bar: Any, name: str) -> Any:
    """Lee ``name`` de una barra (objeto o mapping). ``None`` si no existe."""
    if isinstance(bar, Mapping):
        return bar.get(name)
    return getattr(bar, name, None)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_ohlcv_bars(bars: Sequence[Any]) -> list[OhlcvBar]:
    """Normaliza barras heterogéneas a ``OhlcvBar``.

    Acepta entidades de dominio, filas de base de datos, mappings y dobles de prueba. Una
    barra close-only se convierte en ``open = high = low = close`` con ``volume = 0``: es el
    mismo valor que el motor sintetiza, así que no se introduce una tercera representación.
    """
    normalized: list[OhlcvBar] = []
    for bar in bars:
        close = _as_float(bar_field(bar, "close"))
        if close is None:
            continue
        open_ = _as_float(bar_field(bar, "open"))
        high = _as_float(bar_field(bar, "high"))
        low = _as_float(bar_field(bar, "low"))
        volume = _as_float(bar_field(bar, "volume"))
        timestamp = bar_field(bar, "timestamp")
        normalized.append(
            OhlcvBar(
                timestamp=str(timestamp if timestamp is not None else ""),
                open=close if open_ is None else open_,
                high=close if high is None else high,
                low=close if low is None else low,
                close=close,
                volume=0.0 if volume is None else volume,
            )
        )
    return normalized


def build_signal_indicator_context(
    bars: Sequence[Any],
    definition: Mapping[str, Any],
) -> dict[str, list[float | None]]:
    """``indicator_context`` para ``evaluate_strategy_last_bar`` a partir de OHLCV.

    Es el mismo cálculo que usa el scan (``build_indicator_context(ohlcv_bars, specs)``).
    Sin ``indicatorSpecs`` devuelve ``{}``, que es lo que el motor interpreta como «no hay
    feature precalculada» y deja el camino de presets intrínsecos intacto.
    """
    specs = [dict(spec) for spec in (definition.get("indicatorSpecs") or [])]
    if not specs or not bars:
        return {}
    return build_indicator_context(to_ohlcv_bars(bars), specs)


def feature_source(bars: Sequence[Any]) -> str | None:
    """Procedencia de la feature: ``"real"``, ``"synthetic"`` o ``None`` sin barras (O-6).

    Una ventana es ``real`` solo si **todas** sus barras declaran ``open``/``high``/``low``
    y ``volume``: una sola barra close-only obliga a sintetizar rango y volumen para esa
    barra, y los indicadores de rango o volumen de la ventana entera dejan de ser el dato.
    De ahí que sea ``all`` y no ``any`` — la ventana se evalúa como un todo.

    ``None`` (no ``"synthetic"``) cuando no hay barras: no se evaluó nada, y afirmar una
    procedencia sería inventar el hecho. La ausencia es información, no un relleno.
    """
    if not bars:
        return None
    for bar in bars:
        if (
            _as_float(bar_field(bar, "open")) is None
            or _as_float(bar_field(bar, "high")) is None
            or _as_float(bar_field(bar, "low")) is None
            or _as_float(bar_field(bar, "volume")) is None
        ):
            return FEATURE_SOURCE_SYNTHETIC
    return FEATURE_SOURCE_REAL
