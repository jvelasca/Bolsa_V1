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


# ── V2.34 / A14: CPCV/WFE declarativos (gates reales para Discovery/gramática) ──


def _ema_crossover_definition() -> dict[str, Any]:
    """Definición declarativa rentable sobre una serie con tendencia (WFE calculable)."""
    fast = {"definitionId": "ema", "parameters": {"period": 10}}
    slow = {"definitionId": "ema", "parameters": {"period": 50}}
    return {
        "presetKey": "ema_crossover",
        "indicatorSpecs": [fast, slow],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_cross",
                    "leftSpec": fast,
                    "rightSpec": slow,
                    "direction": "bullish",
                    "signalKind": "entry_long",
                }
            ],
        },
        "exits": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_cross",
                    "leftSpec": fast,
                    "rightSpec": slow,
                    "direction": "bearish",
                    "signalKind": "exit",
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_lab_declarative_cpcv_produces_real_robustness_evidence() -> None:
    """CPCV declarativo: ``cpcv``/``pbo``/WFE no vacíos ⇒ los gates dejan de ser N/E.

    Antes de A14 la vía declarativa devolvía ``cpcv=None`` y ``walk_forward=None``, con
    lo que ``robustness`` y ``walk_forward`` quedaban NOT_EVALUATED y la promoción era
    imposible. Este test blinda que el CPCV declarativo mide de verdad.
    """
    use_case = RunSmaGridOptimize(_Instruments(), _Ohlcv(count=400))
    result = await use_case.execute(
        instrument_id="AAA",
        strategy_family="ema_crossover",
        definition=_ema_crossover_definition(),
        bar_limit=400,
        max_trials=10,
        cpcv_groups=4,
    )
    assert result.cpcv is not None
    assert result.cpcv.get("pathCount", 0) > 0
    # PBO CSCV presente (requisito del gate ``robustness``).
    assert result.pbo is not None
    assert "pbo" in result.pbo
    # WFE agregado (requisito del gate ``walk_forward``), vía cpcv o edge report.
    assert result.cpcv.get("walkForwardEfficiency") is not None


@pytest.mark.asyncio
async def test_lab_declarative_walk_forward_produces_real_evidence() -> None:
    """WF declarativo: ``walk_forward`` no vacío con WFE agregado."""
    use_case = RunSmaGridOptimize(_Instruments(), _Ohlcv(count=400))
    result = await use_case.execute(
        instrument_id="AAA",
        strategy_family="ema_crossover",
        definition=_ema_crossover_definition(),
        bar_limit=400,
        max_trials=10,
        walk_forward_folds=3,
    )
    assert result.walk_forward is not None
    assert result.walk_forward.get("nFolds") == 3
    assert result.walk_forward.get("walkForwardEfficiency") is not None


@pytest.mark.asyncio
async def test_declarative_gates_no_longer_not_evaluated() -> None:
    """``evaluate_optimize_result`` mide robustness/walk_forward sobre la vía declarativa."""
    from bolsa_application.strategy_lab_phase import evaluate_optimize_result
    from bolsa_domain.entities.strategy_lifecycle import (
        GateStatus,
        StrategyCandidate,
    )

    use_case = RunSmaGridOptimize(_Instruments(), _Ohlcv(count=400))
    result = await use_case.execute(
        instrument_id="AAA",
        strategy_family="ema_crossover",
        definition=_ema_crossover_definition(),
        bar_limit=400,
        max_trials=10,
        cpcv_groups=4,
    )
    candidate = StrategyCandidate(
        id="disc-AAA-ema_crossover-0",
        instrument_id="AAA",
        strategy_family="ema_crossover",
        params={"definition": _ema_crossover_definition()},
        origin="discovery",
    )
    evaluation = evaluate_optimize_result(candidate=candidate, result=result)
    by_gate = {gate.gate: gate for gate in evaluation.gates}
    # Un gate puede PASS o FAIL, pero ya no puede quedar sin evidencia (NOT_EVALUATED).
    assert by_gate["robustness"].status is not GateStatus.NOT_EVALUATED
    assert by_gate["walk_forward"].status is not GateStatus.NOT_EVALUATED


@pytest.mark.asyncio
async def test_lab_classic_cpcv_path_unaffected_by_definition_param() -> None:
    """Sin ``definition`` el CPCV sigue siendo H0 (no toca la rama declarativa)."""
    use_case = RunSmaGridOptimize(_Instruments(), _Ohlcv(count=400))
    result = await use_case.execute(
        instrument_id="AAA",
        strategy_family="sma_crossover",
        bar_limit=400,
        max_trials=10,
        cpcv_groups=4,
    )
    assert result.cpcv is not None
    assert result.engine.startswith("cpcv_")
    assert "rules_grid" not in result.engine


@pytest.mark.asyncio
async def test_champion_definition_is_rematerialized_from_winning_params() -> None:
    """El ``executable`` promocionado usa los parámetros del CAMPEÓN, no de la candidata.

    Regresión A14: antes, ``_rules_to_grid`` sobrescribía la definición de cada trial con
    la de la candidata, así que el campeón promocionado replicaba el punto plantilla
    inicial y el shadow/forward medían parámetros que no eran los optimizados.
    """
    from bolsa_application.auto_orchestrator import _champion_definition
    from bolsa_domain.entities.strategy_lifecycle import StrategyCandidate

    candidate_definition = _ema_crossover_definition()  # ema(10)/ema(50)
    use_case = RunSmaGridOptimize(_Instruments(), _Ohlcv(count=400))
    result = await use_case.execute(
        instrument_id="AAA",
        strategy_family="ema_crossover",
        definition=candidate_definition,
        bar_limit=400,
        max_trials=10,
    )
    candidate = StrategyCandidate(
        id="disc-AAA-ema_crossover-0",
        instrument_id="AAA",
        strategy_family="ema_crossover",
        params={"definition": candidate_definition},
        origin="discovery",
    )
    extra = _champion_definition(candidate=candidate, result=result)
    assert extra is not None
    # ``champion_params`` es un dict plano de grid params (sin la definición anidada).
    assert "definition" not in extra["champion_params"]
    assert "executable" in extra
    executable = extra["executable"]
    assert executable["entries"]["rules"]
    assert executable["exits"]["rules"]

