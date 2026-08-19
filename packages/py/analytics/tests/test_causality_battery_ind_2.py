"""F-IND-2 — Batería de causalidad (feature_at_t con/sin barra futura).

Comprueba, para TODOS los indicadores soportados por ``compute_spec``, la propiedad
central de no-look-ahead:

    feature_at_t(full) == feature_at_t(prefix)   para todo t < m

es decir, el valor de un indicador en la barra ``t`` debe ser IDÉNTICO se cuelgue o
no una barra futura a continuación. Cualquier indicador que alcance datos futuros
(``bars[t + k]``) romperá esta igualdad en las barras próximas al borde.

Estructura:
- ``_CAUSAL_SPEC_TABLE``: specs (definition_id + parámetros + claves de línea) de
  indicadores que DEBEN ser estables (feature_at_t idéntico con/sin barra futura).
- ``_NON_CAUSAL_CANARIES``: salidas documentadas como NO causales — chikou (usa
  ``bars[i + displacement]``) y fractals (usa ``bars[i ± 2]``) — que, por diseño,
  NO deben ser estables. Se verifica que efectivamente rompen la propiedad, para
  que cualquier cambio futuro que accidentalmente las hiciera “causales” se
  detecte.

Esta batería es el complemento cuantitativo de la guardia estática de F-IND-1
(``_NON_CAUSAL_OUTPUT_LINES`` en rules_engine + ``nonCausalOutputKeys`` en
indicator-universe). La visualización/chart no pasa por aquí.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.indicators.compute import IndicatorSpecInput, OhlcvBar, compute_spec

# Suficientes barras para cubrir los warmups más largos (p. ej. ADX period=14,
# ST period=10, ich senkouB=52, technical_rating warmup=50).
_N_BARS = 220
_N_FUTURE = 10
_CUT = _N_BARS - _N_FUTURE  # 210 barras "pasadas" + 10 barras "futuras"


def _synthetic_bars(n: int) -> list[OhlcvBar]:
    """Serie determinista con tendencia, oscilación y volumen variable."""
    bars: list[OhlcvBar] = []
    for i in range(n):
        trend = 100.0 + i * 0.3
        wave = 8.0 * (i % 13) / 6.0
        close = trend + wave
        bars.append(
            OhlcvBar(
                timestamp=f"2024-{i // 28 + 1:02d}-{(i % 28) + 1:02d}",
                open=close - 1.0,
                high=close + 3.0,
                low=close - 3.0,
                close=round(close, 4),
                volume=float(1000 + (i * 37) % 9000),
            ),
        )
    return bars


def _column_by_line(
    result: Any,
    key: str,
    bars: list[OhlcvBar],
) -> list[float | None]:
    """Devuelve los valores de la línea ``key`` alineados por índice de barra."""
    line = next((ln for ln in result.lines if ln.key == key), None)
    if line is None:
        return []
    by_ts = {point.timestamp: point.value for point in line.points}
    return [by_ts.get(bar.timestamp) for bar in bars]


# definition_id -> (parámetros, claves de línea a comparar)

_SpecParams = dict[str, Any]
_LineKeys = list[str]

_CAUSAL_SPEC_TABLE: dict[str, tuple[_SpecParams, _LineKeys]] = {
    "sma": ({"period": 20}, ["main"]),
    "ema": ({"period": 20}, ["main"]),
    "wma": ({"period": 20}, ["main"]),
    "rsi": ({"period": 14}, ["main"]),
    "atr": ({"period": 14}, ["main"]),
    "cci": ({"period": 20}, ["main"]),
    "stoch": ({"kPeriod": 14}, ["main"]),
    "macd": ({"fastPeriod": 12, "slowPeriod": 26}, ["main"]),
    "bb": ({"period": 20, "stdDev": 2}, ["upper", "mid", "lower"]),
    "willr": ({"period": 14}, ["main"]),
    "mom": ({"period": 10}, ["main"]),
    "sd": ({"period": 20}, ["main"]),
    "dc": ({"period": 20}, ["upper", "mid", "lower"]),
    "adx": ({"period": 14}, ["main", "plus_di", "minus_di"]),
    "srsi": ({"rsiPeriod": 14, "stochPeriod": 14, "kPeriod": 3, "dPeriod": 3}, ["main", "signal"]),
    "st": ({"atrPeriod": 10, "multiplier": 3}, ["main"]),
    "vwap": ({}, ["main"]),
    "obv": ({}, ["main"]),
    "roc": ({"period": 12}, ["main"]),
    "mfi": ({"period": 14}, ["main"]),
    "aroon": ({"period": 25}, ["up", "down"]),
    "sar": ({"step": 0.02, "maxAf": 0.2}, ["main"]),
    "bears": ({"period": 13}, ["main"]),
    "bulls": ({"period": 13}, ["main"]),
    "ali": ({}, ["jaw", "teeth", "lips"]),
    "volume": ({}, ["main"]),
    "ich": (
        {"tenkanPeriod": 9, "kijunPeriod": 26, "senkouBPeriod": 52, "displacement": 26},
        ["tenkan", "kijun", "spanA", "spanB"],
    ),
    "technical_rating_v1": ({"warmupBars": 50}, ["main"]),
    "bar_data_quality_v1": ({}, ["main"]),
    "ai_global_score_v1": ({"setupWeight": 70, "dataWeight": 30}, ["main"]),
    "strategy_hybrid_score_v1": ({"warmupBars": 50}, ["main"]),
}

# definition_id -> (parámetros, claves de línea no causales que DEBEN romper la propiedad).
_NON_CAUSAL_CANARIES: dict[str, tuple[str, _SpecParams, _LineKeys]] = {
    "chikou": ("ich", {"displacement": 26}, ["chikou"]),
    "fractals": ("fr", {}, ["up", "down"]),
}


def _spec(definition_id: str, parameters: _SpecParams) -> IndicatorSpecInput:
    return IndicatorSpecInput(definition_id=definition_id, parameters=dict(parameters))


@pytest.mark.parametrize(
    "definition_id,parameters,line_keys",
    [
        (definition_id, parameters, line_keys)
        for definition_id, (parameters, line_keys) in sorted(_CAUSAL_SPEC_TABLE.items())
    ],
    ids=[definition_id for definition_id in sorted(_CAUSAL_SPEC_TABLE)],
)
def test_causal_indicator_stable_with_future_bar(
    definition_id: str,
    parameters: _SpecParams,
    line_keys: _LineKeys,
) -> None:
    """feature_at_t(full) == feature_at_t(prefix) para todo t < CUT."""
    bars = _synthetic_bars(_N_BARS)
    cut = _CUT

    full = compute_spec(bars, _spec(definition_id, parameters))
    pref = compute_spec(bars[:cut], _spec(definition_id, parameters))

    for key in line_keys:
        full_col = _column_by_line(full, key, bars)
        pref_col = _column_by_line(pref, key, bars[:cut])
        for t in range(cut):
            fv = full_col[t]
            pv = pref_col[t]
            if fv is None and pv is None:
                continue
            assert fv == pv, (
                f"{definition_id}[{key}] diff en barra {t}: con barra futura en {fv!r}, "
                f"sin barra futura en {pv!r}"
            )


@pytest.mark.parametrize(
    "case_id,definition_id,parameters,line_keys",
    [
        (case_id, definition_id, parameters, line_keys)
        for case_id, (definition_id, parameters, line_keys) in sorted(_NON_CAUSAL_CANARIES.items())
    ],
    ids=[case_id for case_id in sorted(_NON_CAUSAL_CANARIES)],
)
def test_noncausal_output_breaks_stability_canary(
    case_id: str,
    definition_id: str,
    parameters: _SpecParams,
    line_keys: _LineKeys,
) -> None:
    """Verifica que las salidas no causales SÍ rompen la propiedad estabilidad.

    No es un fallo del indicador: es prueba de que estas líneas dependen de datos
    futuros y, por tanto, deben seguir excluidas del feature set de backtest/research.
    """
    bars = _synthetic_bars(_N_BARS)
    cut = _CUT

    full = compute_spec(bars, _spec(definition_id, parameters))
    pref = compute_spec(bars[:cut], _spec(definition_id, parameters))

    broken = False
    for key in line_keys:
        full_col = _column_by_line(full, key, bars)
        pref_col = _column_by_line(pref, key, bars[:cut])
        for t in range(cut):
            if full_col[t] != pref_col[t]:
                broken = True
                break
        if broken:
            break
    assert broken, (
        f"{definition_id}[{case_id}] inesperadamente estable: ninguna barra futura cambió "
        f"el valor en t < {cut}; se esperaba que la salida no causal rompiera la estabilidad"
    )


def test_all_compute_spec_definitions_covered_by_battery() -> None:
    """Guarda: ningún definition_id soportado por ``compute_spec`` queda sin cobertura."""
    expected_causal = {
        "sma", "ema", "wma", "rsi", "atr", "cci", "stoch", "macd", "bb",
        "willr", "mom", "sd", "dc", "adx", "srsi", "st", "vwap", "obv",
        "roc", "mfi", "aroon", "sar", "bears", "bulls", "ali", "volume",
        "ich", "technical_rating_v1", "bar_data_quality_v1", "ai_global_score_v1",
        "strategy_hybrid_score_v1",
    }
    assert set(_CAUSAL_SPEC_TABLE) == expected_causal
    assert set(_NON_CAUSAL_CANARIES) == {"chikou", "fractals"}
