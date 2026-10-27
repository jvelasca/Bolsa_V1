"""B-1 / B-6: la ventana declara «no evaluable» en vez de publicar «sin señal».

El defecto que se cierra: el scan exigía ``MIN_SCAN_BARS = 50`` plano. Con un
``bar_limit`` menor que el warmup real del preset, las series quedaban en ``None``,
la regla no disparaba y el scan publicaba cero señales **sin declarar por qué**. Un
instrumento no evaluable se contaba igual que un instrumento evaluado sin señal.

Lo que se fija aquí, y nada más:

1. **Ningún preset sano se declara no evaluable** con la ventana por defecto (500
   barras): el chequeo no puede convertir señales reales en omisiones.
2. **El umbral es exacto**: con ``N - 1`` barras el preset no es evaluable y con
   ``N`` sí, para los 21 presets del catálogo. Un cruce necesita una barra más que
   la serie que cruza (compara ``-1`` con ``-2``).
3. **El motivo nombra la serie y las barras**: ``warmup_insufficient`` deja de ser
   un booleano opaco.
4. **Una serie ausente del contexto no se disfraza de warmup**: es otro defecto.

Las series son deterministas y viven en memoria: ninguna prueba toca base de datos,
ficheros ni el estado de la ventana.
"""

from __future__ import annotations

import pytest

from bolsa_analytics.indicators import compute
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_analytics.signals.preset_catalog import load_preset_catalog
from bolsa_analytics.signals.preset_evaluability import (
    WARMUP_INSUFFICIENT,
    evaluability_reason,
    measured_warmup_bars,
    required_spec_depth,
    unevaluable_specs,
)
from bolsa_analytics.signals.rules_engine import build_indicator_context

SYMBOL = "AAA"
DEFAULT_WINDOW = 500

#: Umbral medido con la serie real, no deducido de los periodos. Los cuatro presets
#: que el audit declaró inalcanzables con ``bar_limit = 120`` están aquí: con 120
#: barras se publicaban como «sin señal».
_EXPECTED_THRESHOLD: dict[str, int] = {
    "golden_cross": 201,
    "death_cross": 201,
    "sma_crossover": 51,
    "ichimoku_tk_cross": 78,
    "ma_stack_bullish": 200,
    "price_above_sma200": 200,
    "pullback_in_uptrend": 50,
}


def _preset_keys() -> list[str]:
    return sorted(load_preset_catalog()["presets"])


def _bars(count: int, *, spread: float = 0.5) -> list[OhlcvBar]:
    """Serie OHLCV determinista de ``count`` barras, con pendiente suave."""
    return [
        OhlcvBar(
            timestamp=f"2026-01-{1 + index % 28:02d}",
            open=100.0 + 0.1 * index - spread * 0.4,
            high=100.0 + 0.1 * index + spread,
            low=100.0 + 0.1 * index - spread,
            close=100.0 + 0.1 * index,
            volume=1000.0,
        )
        for index in range(count)
    ]


def _context(preset: str, count: int) -> dict[str, list[float | None]]:
    definition = strategy_definition_from_preset(preset, [SYMBOL])
    return build_indicator_context(_bars(count), list(definition.get("indicatorSpecs") or []))


def _reason(preset: str, count: int) -> str | None:
    definition = strategy_definition_from_preset(preset, [SYMBOL])
    return evaluability_reason(
        definition,
        _context(preset, count),
        bar_count=count,
    )


def _threshold(preset: str) -> int:
    """Barras mínimas que el preset necesita, leídas de la serie real a 500 barras.

    No se deduce de los periodos: se pregunta a cada serie en qué índice se define
    por primera vez y se le suma la profundidad que exige su regla.
    """
    definition = strategy_definition_from_preset(preset, [SYMBOL])
    context = _context(preset, DEFAULT_WINDOW)
    required = 0
    for key, depth in required_spec_depth(definition).items():
        series = context[key]
        first = next(index for index, value in enumerate(series) if value is not None)
        required = max(required, first + depth)
    return required


def test_every_preset_is_evaluable_with_the_default_window() -> None:
    """Anti-falso-positivo: con 500 barras ningún preset puede declararse omitido."""
    offenders = {preset: _reason(preset, DEFAULT_WINDOW) for preset in _preset_keys()}
    assert {key: value for key, value in offenders.items() if value is not None} == {}


@pytest.mark.parametrize("preset", _preset_keys())
def test_the_threshold_is_exact_for_every_preset(preset: str) -> None:
    """Con ``N - 1`` barras no es evaluable; con ``N`` sí. Para los 21 presets."""
    threshold = _threshold(preset)

    assert _reason(preset, threshold - 1) is not None, (
        f"{preset}: con {threshold - 1} barras no debería ser evaluable"
    )
    assert _reason(preset, threshold) is None
    assert _reason(preset, DEFAULT_WINDOW) is None

    if preset in _EXPECTED_THRESHOLD:
        assert threshold == _EXPECTED_THRESHOLD[preset], (
            f"{preset}: umbral medido {threshold}, declarado {_EXPECTED_THRESHOLD[preset]}"
        )
    else:
        # Ninguno de los presets restantes necesita más que la ventana mínima del scan.
        assert threshold <= 50, f"{preset}: umbral {threshold} rompe MIN_SCAN_BARS=50"


def test_a_cross_needs_the_previous_bar_not_just_the_series() -> None:
    """B-1 en una línea: SMA200 está definida con 200 barras, pero el cruce necesita 201.

    Es la razón por la que el umbral **no** puede ser ``period``: el cruce compara la
    barra ``-1`` con la ``-2``, y con 200 barras la ``-2`` todavía es ``None``.
    """
    sma200 = compute.compute_sma([100.0 + 0.1 * index for index in range(200)], 200)
    assert sma200[-1] is not None, "SMA200 sí está definida en la última barra"
    assert sma200[-2] is None, "y no en la anterior: por eso el cruce pide 201"

    assert _reason("golden_cross", 200) is not None
    assert _reason("golden_cross", 201) is None


def test_a_comparison_needs_only_the_last_bar() -> None:
    """Contraste: ``price_above_sma200`` compara contra ``-1`` y se decide con 200."""
    assert _reason("price_above_sma200", 199) is not None
    assert _reason("price_above_sma200", 200) is None


def test_ichimoku_pays_the_displacement_and_is_not_fifty_three() -> None:
    """``senkouBPeriod=52`` + ``displacement=26`` ⇒ 78, no ``52 + 1``.

    Es el contraejemplo que justifica medir sobre la serie en vez de sumar periodos.
    """
    assert _reason("ichimoku_tk_cross", 77) is not None
    assert _reason("ichimoku_tk_cross", 78) is None


def test_the_reason_names_the_series_and_the_bars_it_needs() -> None:
    """El motivo es accionable: dice qué serie falta y cuándo se conoce el número.

    A 120 barras SMA200 **no se define en ninguna barra**, así que el motivo declara
    «requiere más de 120» en vez de inventar un ``201`` por aritmética de periodos.
    A 200 barras la serie sí se define en ``-1`` y el número exacto es evidencia.
    """
    undefined = _reason("golden_cross", 120)
    assert undefined is not None
    assert undefined.startswith(f"{WARMUP_INSUFFICIENT}:")
    assert "sma period=200" in undefined
    assert "requiere más de 120 barras" in undefined
    assert "ventana: 120 barras" in undefined

    exact = _reason("golden_cross", 200)
    assert exact is not None
    assert "sma period=200" in exact
    assert "requiere >= 201 barras" in exact


def test_an_absent_series_is_not_blamed_on_the_warmup() -> None:
    """Una spec referenciada pero no declarada es otro defecto: no se disfraza de warmup.

    Se deja fuera del recuento a propósito. Si se atribuyera al warmup, un error de
    definición se «arreglaría» pidiendo más barras y seguiría sin evaluarse nunca.
    """
    definition = {
        "indicatorSpecs": [{"definitionId": "sma", "parameters": {"period": 50}}],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_compare",
                    "leftSpec": {"definitionId": "rsi", "parameters": {"period": 14}},
                    "operator": "lt",
                    "rightValue": 30,
                    "signalKind": "entry_long",
                }
            ],
        },
    }
    context = build_indicator_context(
        _bars(60), list(definition["indicatorSpecs"])
    )

    assert unevaluable_specs(context, definition) == []
    assert evaluability_reason(definition, context, bar_count=60) is None


def test_the_declared_depth_marks_crosses_as_two_bars() -> None:
    """El contrato de profundidad: cruz = 2, comparación = 1."""
    cross = strategy_definition_from_preset("sma_crossover", [SYMBOL])
    compare = strategy_definition_from_preset("price_above_sma200", [SYMBOL])

    assert set(required_spec_depth(cross).values()) == {2}
    assert set(required_spec_depth(compare).values()) == {1}


# --- B-1 (ventana derivada): el warmup se mide ANTES de pedir barras -------------------
#
# ``evaluability_reason`` diagnostica después; ``measured_warmup_bars`` dimensiona antes.
# Si las dos mediciones no coinciden, la ventana que el worker pide y el motivo que luego
# publica se contradicen. Estas pruebas fijan esa igualdad.


@pytest.mark.parametrize("preset", _preset_keys())
def test_measured_warmup_matches_the_series_threshold_for_every_preset(preset: str) -> None:
    """El número que dimensiona la ventana es EL MISMO que el que diagnostica el scan."""
    definition = strategy_definition_from_preset(preset, [SYMBOL])

    assert measured_warmup_bars(definition) == _threshold(preset)


@pytest.mark.parametrize("preset", _preset_keys())
def test_measured_warmup_is_evaluable_at_its_own_number(preset: str) -> None:
    """Anti-falso-positivo: pedir ``measured_warmup_bars`` barras basta para evaluar."""
    definition = strategy_definition_from_preset(preset, [SYMBOL])
    required = measured_warmup_bars(definition)

    assert required is not None
    assert _reason(preset, required) is None


def test_a_definition_without_rules_pays_no_warmup() -> None:
    """Un preset sin series no paga ventana: ``0`` y la env manda."""
    assert measured_warmup_bars({"exits": {"rules": []}}) == 0
    assert measured_warmup_bars({}) == 0


def test_measured_warmup_is_none_when_a_spec_never_defines() -> None:
    """Una serie que la sonda no define no produce un número inventado: ``None``.

    ``None`` obliga al llamante a fallar cerrado y declararlo; devolver ``probe`` a ojo
    convertiría «no se puede medir» en una ventana falsa.
    """
    definition = {
        "indicatorSpecs": [{"definitionId": "sma", "parameters": {"period": 5000}}],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_compare",
                    "leftSpec": {"definitionId": "sma", "parameters": {"period": 5000}},
                    "operator": "gt",
                    "rightValue": 0,
                    "signalKind": "entry_long",
                }
            ],
        },
    }

    assert measured_warmup_bars(definition) is None


def test_measured_warmup_is_none_for_an_undeclared_spec() -> None:
    """Una spec referenciada y no declarada es una definición incompleta, no warmup medible."""
    definition = {
        "indicatorSpecs": [{"definitionId": "sma", "parameters": {"period": 50}}],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_compare",
                    "leftSpec": {"definitionId": "rsi", "parameters": {"period": 14}},
                    "operator": "lt",
                    "rightValue": 30,
                    "signalKind": "entry_long",
                }
            ],
        },
    }

    assert measured_warmup_bars(definition) is None


def test_measured_warmup_enriches_a_definition_that_only_carries_the_preset() -> None:
    """Sin reglas propias se enriquece desde ``presetKey``: medir sin reglas daría ``0``."""
    assert measured_warmup_bars({"presetKey": "golden_cross"}) == 201
