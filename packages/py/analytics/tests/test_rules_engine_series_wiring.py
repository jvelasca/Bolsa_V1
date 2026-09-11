"""V2.34 / A14 — wiring causal de indicadores en el evaluador de señales.

Certifica que los ``definitionId`` que A14 necesita (y que el catálogo de Discovery ya
usaba) resuelven a una serie real en ``_series_for_spec`` en lugar de devolver ``None``
(silencio fail-closed con la regla inerte). Se comprueba también que las guardias de
causalidad (``fr`` y ``ich:chikou``) siguen devolviendo ``None``.
"""

from __future__ import annotations

import math

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.rules_engine import _series_for_spec


def _bars(count: int = 120) -> list[OhlcvBar]:
    """Serie oscilante con volumen: suficiente para que todos los indicadores calienten."""
    bars: list[OhlcvBar] = []
    for index in range(count):
        close = 100.0 + 15.0 * math.sin(index / 9.0) + index * 0.05
        bars.append(
            OhlcvBar(
                timestamp=f"2026-{index:04d}",
                open=close * 0.999,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=1000.0 + index,
            )
        )
    return bars


def _series(definition_id: str, **parameters: object) -> list[float | None] | None:
    bars = _bars()
    closes = [bar.close for bar in bars]
    return _series_for_spec(bars, closes, definition_id, dict(parameters))


def _has_value(series: list[float | None] | None) -> bool:
    return series is not None and any(value is not None for value in series)


def test_newly_wired_ids_resolve_to_a_real_series() -> None:
    """Cada id cableado en A14 produce una serie con al menos un valor no ``None``."""
    cases: dict[str, dict[str, object]] = {
        "wma": {"period": 20},
        "mom": {"period": 10},
        "sd": {"period": 20},
        "roc": {"period": 12},
        "obv": {},
        "mfi": {"period": 14},
        "bears": {"period": 13},
        "bulls": {"period": 13},
        "aroon": {"period": 25},
        "sar": {"step": 0.02, "maxAf": 0.2},
        "srsi": {"rsiPeriod": 14, "stochPeriod": 14, "kPeriod": 3, "dPeriod": 3},
    }
    for definition_id, parameters in cases.items():
        series = _series(definition_id, **parameters)
        assert series is not None, f"{definition_id} no resuelve a serie (quedaría inerte)"
        assert len(series) == 120, f"{definition_id} devuelve longitud inesperada"
        assert _has_value(series), f"{definition_id} no produce ningún valor"


def test_line_selection_for_multi_line_ids() -> None:
    """Los ids con varias líneas respetan ``line`` (aroon up/down, srsi k/signal)."""
    aroon_up = _series("aroon", period=25, line="up")
    aroon_down = _series("aroon", period=25, line="down")
    assert aroon_up is not None and aroon_down is not None
    assert aroon_up != aroon_down

    srsi_k = _series("srsi", rsiPeriod=14, stochPeriod=14, kPeriod=3, dPeriod=3)
    srsi_d = _series("srsi", rsiPeriod=14, stochPeriod=14, kPeriod=3, dPeriod=3, line="signal")
    assert srsi_k is not None and srsi_d is not None
    assert srsi_k != srsi_d


def test_sar_accepts_legacy_maxstep_alias() -> None:
    """``maxStep`` (plantilla histórica) y ``maxAf`` (compute_spec) dan la misma serie."""
    modern = _series("sar", step=0.02, maxAf=0.2)
    legacy = _series("sar", step=0.02, maxStep=0.2)
    assert modern is not None and legacy is not None
    assert modern == legacy


def test_causality_guards_still_return_none() -> None:
    """Las salidas no causales siguen vetadas (sin look-ahead)."""
    assert _series("fr") is None
    assert _series("ich", tenkanPeriod=9, kijunPeriod=26, line="chikou") is None


def test_unknown_id_still_fails_closed() -> None:
    """Un id desconocido no inventa serie (fail-closed silencioso, como antes)."""
    assert _series("does_not_exist", period=10) is None
