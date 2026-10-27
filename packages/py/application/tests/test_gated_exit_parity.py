"""ADR-048 — una sola semántica de salida: ACTIVE y política preguntan lo mismo al mismo dato.

El defecto medido por el banco de contrato: la ruta de política (``position_exit_evaluator``)
evaluaba la salida con ``evaluate_exit_last_bar_gated``, que **reconstruía** barras
``open = high = low = close`` y ``volume = 0``. En un preset de volumen o rango la serie del
VWAP desaparece (``cum_vol = 0``) y la salida se pierde, mientras el decisor ACTIVE —que ya
construía el contexto con OHLCV real— sí la veía. La misma posición podía recibir dos
respuestas según quién preguntara.

Lo que se fija aquí:

1. Sobre el MISMO OHLCV, la ruta ACTIVE y la ruta de política coinciden: si una cierra, la
   otra también, y si una no cierra, la otra tampoco.
2. La divergencia close-only se conserva como **wrapper declarado** (comportamiento
   histórico), no como ruta de producto.
3. El estado ``gated`` sale del LIBRO: la ruta ACTIVE declara ``holdsLong`` y no compra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.preset_rules import enrich_definition_with_preset_rules
from bolsa_analytics.signals.rules_engine import evaluate_exit_last_bar_gated
from bolsa_application.active_strategy_signal_evaluator import make_active_strategy_decider
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

SYMBOL = "AAA"


def _vwap_exit_definition() -> dict[str, Any]:
    """Salida por ``precio < vwap`` — la regla que el ``volume = 0`` degrada."""
    spec = {"definitionId": "vwap", "parameters": {}}
    return {
        "id": "strat-vwap",
        "version": 1,
        "presetKey": "vwap_reclaim",
        "indicatorSpecs": [spec],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "price_vs_indicator",
                    "indicatorSpec": spec,
                    "operator": "gt",
                    "signalKind": "entry_long",
                }
            ],
        },
        "exits": {
            "operator": "all",
            "rules": [
                {
                    "type": "price_vs_indicator",
                    "indicatorSpec": spec,
                    "operator": "lt",
                    "signalKind": "exit",
                }
            ],
        },
    }


def _bars(*, gap_down: bool) -> list[OhlcvBar]:
    """30 barras con volumen real; la última cae muy por debajo del VWAP si ``gap_down``."""
    closes = [100.0] * 29 + ([50.0] if gap_down else [101.0])
    return [
        OhlcvBar(
            timestamp=f"2024-02-{day:02d}",
            open=close,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=10_000.0,
        )
        for day, close in enumerate(closes, start=1)
    ]


def _active(definition: dict[str, Any]) -> ActiveStrategy:
    return ActiveStrategy(
        version_id="ver-adr48",
        candidate_id="cand-adr48",
        instrument_id=SYMBOL,
        name="vwap_reclaim",
        definition={"lot_qty": 10.0, "watch": [SYMBOL], "executable": definition},
    )


def _policy_exit(bars: list[OhlcvBar]) -> bool:
    """Ruta de POLÍTICA: lo que hace ``position_exit_evaluator`` sobre las barras cargadas."""
    resolved = enrich_definition_with_preset_rules(_vwap_exit_definition())
    event = evaluate_exit_last_bar_gated(
        resolved,
        [bar.timestamp for bar in bars],
        [bar.close for bar in bars],
        bars=bars,
    )
    return event is not None


def _active_exit(bars: list[OhlcvBar]) -> bool:
    """Ruta ACTIVE: lo que decide el decisor con el libro largo."""
    decider = make_active_strategy_decider(
        active=_active(_vwap_exit_definition()),
        watch=(SYMBOL,),
        bars_by_symbol=lambda _s: list(bars),
        long_by_symbol=lambda _s: True,
    )
    decision = decider(SYMBOL)
    assert decision.action != "BUY", "con el libro largo no se compra lo que ya se tiene"
    return decision.action == "SELL"


@pytest.mark.parametrize("gap_down", [True, False])
def test_active_and_policy_paths_agree_on_real_ohlcv(gap_down: bool) -> None:
    """Paridad: el mismo OHLCV produce la misma respuesta de salida en las dos rutas."""
    bars = _bars(gap_down=gap_down)

    assert _active_exit(bars) is _policy_exit(bars)


def test_the_closing_case_is_really_exercised() -> None:
    """Control positivo: con el hueco a la baja AMBAS rutas cierran (no es un no-op)."""
    bars = _bars(gap_down=True)

    assert _policy_exit(bars) is True
    assert _active_exit(bars) is True


def test_the_close_only_wrapper_loses_the_exit_that_the_real_path_sees() -> None:
    """El delta declarado: la ventana close-only no cierra donde la real sí.

    No es un efecto deseado: es la razón por la que la ruta de producto deja de reconstruir
    ``volume = 0``. El wrapper se conserva para llamantes históricos.
    """
    bars = _bars(gap_down=True)
    resolved = enrich_definition_with_preset_rules(_vwap_exit_definition())

    historical = evaluate_exit_last_bar_gated(
        resolved,
        [bar.timestamp for bar in bars],
        [bar.close for bar in bars],
    )

    assert historical is None
    assert _policy_exit(bars) is True


def test_the_policy_route_declares_the_book_state_too() -> None:
    """ADR-048 — la ruta ACTIVE declara ``gatedState`` con ``source = book``.

    La política no reescribe el estado: el libro es la única fuente (``_open``) y ambas
    rutas preguntan por él, no por un segundo campo persistido.
    """
    decider = make_active_strategy_decider(
        active=_active(_vwap_exit_definition()),
        watch=(SYMBOL,),
        bars_by_symbol=lambda _s: _bars(gap_down=True),
        long_by_symbol=lambda _s: True,
    )

    gated = decider(SYMBOL).gated_state

    assert gated is not None
    assert gated.to_dict() == {
        "holdsLong": True,
        "source": "book",
        "exitEvaluated": "last_bar",
    }


@dataclass(frozen=True)
class _BookThatFails:
    """Libro ilegible: cualquier lectura lanza."""

    def __call__(self, symbol: str) -> bool:
        raise RuntimeError(f"libro ilegible para {symbol}")


def test_an_unreadable_book_never_sells_either() -> None:
    """Sin libro la política no inventa una venta: HOLD declarado, aunque la regla dispare."""
    decider = make_active_strategy_decider(
        active=_active(_vwap_exit_definition()),
        watch=(SYMBOL,),
        bars_by_symbol=lambda _s: _bars(gap_down=True),
        long_by_symbol=_BookThatFails(),
    )

    decision = decider(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.hold_reason == "gated_unavailable"
    assert decision.gated_state is not None
    assert decision.gated_state.holds_long is None
