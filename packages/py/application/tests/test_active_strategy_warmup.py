"""B-1 en el decisor ACTIVE: la ventana corta se declara, no se disfraza de HOLD.

El defecto medido: el worker AUTO precarga ``AUTO_ENGINE_SIM_SIGNAL_BARS = 120`` barras.
Con un preset que pide SMA200 —o el cruce 50/200, que pide 201— la serie queda en
``None``, la regla no dispara y el decisor devolvía un **HOLD indistinguible** del de
una estrategia evaluada sin señal. Un HOLD por falta de datos no es un HOLD por
ausencia de señal, y hasta ahora se leían igual.

Lo que se fija aquí, y nada más:

1. Con 120 barras el decisor sigue en **HOLD** (fail-closed: nunca inventa una orden),
   pero el motivo ``warmup_insufficient`` viaja en ``memo``.
2. Con la ventana que cubre el warmup, el ``memo`` de warmup **no** aparece: el chequeo
   no puede convertir señales reales en HOLD silenciosos.
3. Un preset ligero no paga el chequeo: con 120 barras ``vwap_reclaim`` no se declara
   no evaluable.

Las barras son deterministas y viven en memoria: ninguna prueba toca base de datos,
ficheros ni el estado de la ventana.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_analytics.signals.preset_evaluability import WARMUP_INSUFFICIENT
from bolsa_application.active_strategy_signal_evaluator import make_active_strategy_decider
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

SYMBOL = "AAA"
DEFAULT_WINDOW = 120


@dataclass(frozen=True)
class _Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def _bars(count: int) -> list[_Bar]:
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


def _decider(preset: str, count: int) -> Any:
    executable = strategy_definition_from_preset(preset, [SYMBOL])
    active = ActiveStrategy(
        version_id="ver-warmup",
        candidate_id="cand-warmup",
        instrument_id=SYMBOL,
        name=preset,
        definition={
            "lot_qty": 100.0,
            "watch": [SYMBOL],
            "executable": executable,
        },
    )
    bars = _bars(count)
    return make_active_strategy_decider(
        active=active,
        watch=(SYMBOL,),
        bars_by_symbol=lambda symbol: bars,
    )


@pytest.mark.parametrize("preset", ["golden_cross", "death_cross"])
def test_the_default_window_declares_the_missing_warmup(preset: str) -> None:
    """120 barras con un cruce 50/200: HOLD sí, pero con el motivo publicado."""
    decision = _decider(preset, DEFAULT_WINDOW)(SYMBOL)

    assert decision.action == "HOLD", "fail-closed: nunca se inventa una orden"
    assert decision.quantity == 0
    assert decision.memo.startswith(WARMUP_INSUFFICIENT)
    assert "sma period=200" in decision.memo


def test_the_reason_names_the_bars_the_cross_needs() -> None:
    """Con 200 barras la serie sí se define y el número exacto es evidencia: 201."""
    decision = _decider("golden_cross", 200)(SYMBOL)

    assert decision.action == "HOLD"
    assert "requiere >= 201 barras" in decision.memo


def test_a_window_that_covers_the_warmup_does_not_declare_anything() -> None:
    """Anti-falso-positivo: 201 barras y el memo de warmup desaparece."""
    decision = _decider("golden_cross", 201)(SYMBOL)

    assert WARMUP_INSUFFICIENT not in decision.memo


def test_a_light_preset_is_not_declared_unevaluable_at_the_default_window() -> None:
    """``vwap_reclaim`` necesita una barra: con 120 no se omite por warmup."""
    decision = _decider("vwap_reclaim", DEFAULT_WINDOW)(SYMBOL)

    assert WARMUP_INSUFFICIENT not in decision.memo


def test_a_single_declaration_per_decision() -> None:
    """El motivo es una declaración, no un log repetido: el ``memo`` no se concatena."""
    decision = _decider("golden_cross", DEFAULT_WINDOW)(SYMBOL)

    assert decision.memo.count(WARMUP_INSUFFICIENT) == 1
