"""V2.32 / A12 — fase SHADOW: replay determinista del finalista (puro, sin DB).

Certifica que la evidencia shadow se **ejecuta** (no se lee un flag): el replay
reutiliza el motor declarativo de reglas, es determinista y fail-closed ante falta de
barras/definición/operaciones.
"""

from __future__ import annotations

import math
from typing import Any

from bolsa_application.discovery_catalog import DISCOVERY_FAMILIES
from bolsa_application.strategy_shadow_phase import (
    ShadowReplayConfig,
    extract_executable,
    run_shadow_replay,
)
from bolsa_domain.entities.strategy_lifecycle import (
    ShadowPolicy,
    StrategyFinalist,
)


def _executable_definition() -> dict[str, Any]:
    """Materializa una definición ejecutable real (plantilla del catálogo)."""
    family = next(f for f in DISCOVERY_FAMILIES if f.name == "ema_crossover")
    definition = family.template({"fastPeriod": 5, "slowPeriod": 20})
    assert definition is not None
    return definition


def _finalist(definition: dict[str, Any], version_id: str = "ver-shadow-1") -> StrategyFinalist:
    return StrategyFinalist(
        candidate_id="cand-1",
        version_id=version_id,
        name="shadow-test",
        definition_hash="h",
        definition=definition,
    )


def _bars(count: int = 200) -> list[Any]:
    from bolsa_analytics.backtest import BacktestBarInput

    out = []
    for index in range(count):
        price = 100.0 + 12.0 * math.sin(index / 6.0) + index * 0.05
        out.append(
            BacktestBarInput(
                timestamp=f"2026-01-{index % 28 + 1:02d}",
                close=price,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                volume=1000.0,
            )
        )
    return out


def test_extract_executable_none_when_missing() -> None:
    assert extract_executable(_finalist({})) is None
    assert extract_executable(_finalist({"executable": None})) is None
    assert extract_executable(_finalist({"executable": {"id": "x"}})) == {"id": "x"}


def test_shadow_replay_without_definition_is_fail_closed() -> None:
    result = run_shadow_replay(finalist=_finalist({}), bars=_bars())
    assert result.passed is False
    assert "shadow_sin_definicion_ejecutable" in result.reasons
    assert result.trades == 0


def test_shadow_replay_without_bars_is_fail_closed() -> None:
    finalist = _finalist({"executable": _executable_definition()})
    result = run_shadow_replay(finalist=finalist, bars=[])
    assert result.passed is False
    assert "shadow_barras_insuficientes" in result.reasons


def test_shadow_replay_produces_contable_evidence() -> None:
    finalist = _finalist({"executable": _executable_definition()})
    policy = ShadowPolicy(min_trades=1, min_return_pct=-1000.0)
    result = run_shadow_replay(
        finalist=finalist,
        bars=_bars(),
        policy=policy,
        config=ShadowReplayConfig(min_bars=60),
        as_of="2026-09-11",
    )
    assert result.trades > 0, "la plantilla debe ejecutar operaciones reales"
    assert result.as_of == "2026-09-11"
    assert result.bars_used == 200
    assert result.return_pct is not None
    assert result.passed is True
    assert result.reasons == ()


def test_shadow_replay_is_deterministic() -> None:
    finalist = _finalist({"executable": _executable_definition()})
    policy = ShadowPolicy(min_trades=1, min_return_pct=-1000.0)
    first = run_shadow_replay(finalist=finalist, bars=_bars(), policy=policy)
    second = run_shadow_replay(finalist=finalist, bars=_bars(), policy=policy)
    assert first == second


def test_shadow_replay_insufficient_sample_fails() -> None:
    finalist = _finalist({"executable": _executable_definition()})
    policy = ShadowPolicy(min_trades=10_000, min_return_pct=-1000.0)
    result = run_shadow_replay(finalist=finalist, bars=_bars(), policy=policy)
    assert result.passed is False
    assert "shadow_muestra_insuficiente" in result.reasons
