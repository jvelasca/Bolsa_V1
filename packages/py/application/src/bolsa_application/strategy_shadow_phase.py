"""V2.32 / A12 — fase SHADOW: evidencia ejecutada del finalista (no el flag).

Cierra el P2 diferido por V2.31: hasta ahora el Promotion Gate aceptaba
``AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1`` como sustituto de validación shadow, pero el
sistema **nunca ejecutaba** nada. Esta fase produce la evidencia real:

    FINALISTA ──▶ SHADOW REPLAY ──▶ ShadowValidationResult ──▶ PROMOTION GATE

El replay es **determinista y puro** (sin DB, sin red, sin IA): reutiliza el motor
declarativo de reglas (``evaluate_rules_signals`` en modo ``gated``) sobre una ventana
de barras **separada del LAB**, con la misma contabilidad de equity/drawdown y la misma
causalidad ``index-1 → open(index)`` que el LAB. Sin look-ahead.

Fail-closed: sin barras suficientes, sin definición ejecutable o sin operaciones ⇒
``passed=False`` con motivo explícito. No se inventa evidencia.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    ShadowPolicy,
    ShadowValidationResult,
    StrategyFinalist,
)

__all__ = [
    "ShadowReplayConfig",
    "extract_executable",
    "run_shadow_replay",
]


@dataclass(frozen=True, slots=True)
class ShadowReplayConfig:
    """Ventana y capital del replay shadow (defaults conservadores)."""

    initial_cash: float = 10000.0
    window_bars: int = 250
    min_bars: int = 60


def extract_executable(finalist: StrategyFinalist) -> dict[str, Any] | None:
    """Extrae la definición ejecutable declarativa de un finalista.

    Es ``definition["executable"]`` (``StrategyDefinitionV1``). Los finalistas de
    familias H0 (SMA/RSI/MACD) pueden no traerla: en ese caso no hay replay posible y
    el llamante debe resolverlo fail-closed (sin evidencia ⇒ no promoción).
    """
    definition = finalist.definition if isinstance(finalist.definition, Mapping) else {}
    executable = definition.get("executable")
    if isinstance(executable, Mapping):
        return dict(executable)
    return None


def run_shadow_replay(
    *,
    finalist: StrategyFinalist,
    bars: Sequence[Any],
    policy: ShadowPolicy | None = None,
    config: ShadowReplayConfig | None = None,
    as_of: str | None = None,
) -> ShadowValidationResult:
    """Ejecuta la validación shadow del finalista sobre ``bars`` (ventana separada).

    Devuelve SIEMPRE un ``ShadowValidationResult``: nunca lanza por falta de evidencia
    (un fallo del replay es ``passed=False``, no una excepción que rompa el ciclo).
    """
    effective_policy = policy or ShadowPolicy()
    effective_config = config or ShadowReplayConfig()
    executable = extract_executable(finalist)

    if executable is None:
        return _denied(finalist, "shadow_sin_definicion_ejecutable", as_of=as_of)
    if len(bars) < effective_config.min_bars:
        return _denied(
            finalist,
            "shadow_barras_insuficientes",
            bars_used=len(bars),
            as_of=as_of,
        )

    window = list(bars)[-max(1, int(effective_config.window_bars)) :]
    try:
        from bolsa_analytics.optimize.rules_grid import _simulate_rules_strategy

        prepared = [_as_backtest_bar(bar) for bar in window]
        metrics = _simulate_rules_strategy(
            prepared,
            executable,
            initial_cash=effective_config.initial_cash,
            attach_round_trips=True,
        )
    except Exception:  # noqa: BLE001 — sin evidencia no se inventa: fail-closed.
        return _denied(finalist, "shadow_replay_fallido", bars_used=len(window), as_of=as_of)

    return effective_policy.evaluate(
        version_id=finalist.version_id,
        trades=int(metrics.get("tradeCount") or 0),
        return_pct=_as_float(metrics.get("totalReturnPct")),
        max_drawdown_pct=_as_float(metrics.get("maxDrawdownPct")),
        win_rate=_as_float(metrics.get("winRate")),
        instrument_id=_finalist_instrument(finalist),
        bars_used=len(window),
        as_of=as_of,
    )


def _denied(
    finalist: StrategyFinalist,
    reason: str,
    *,
    bars_used: int = 0,
    as_of: str | None = None,
) -> ShadowValidationResult:
    return ShadowValidationResult(
        version_id=finalist.version_id,
        trades=0,
        passed=False,
        reasons=(reason,),
        instrument_id=_finalist_instrument(finalist),
        bars_used=bars_used,
        as_of=as_of,
    )


def _finalist_instrument(finalist: StrategyFinalist) -> str | None:
    definition = finalist.definition if isinstance(finalist.definition, Mapping) else {}
    instrument = definition.get("instrument_id")
    return str(instrument) if instrument else None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_backtest_bar(bar: Any) -> Any:
    """Adapta una barra del repositorio OHLCV a ``BacktestBarInput``.

    Acepta tanto ``BacktestBarInput`` ya construida como barras ORM/dict con
    ``timestamp``/``open``/``high``/``low``/``close``/``volume``.
    """
    from bolsa_analytics.backtest import BacktestBarInput

    if isinstance(bar, BacktestBarInput):
        return bar

    def _get(name: str, default: Any = None) -> Any:
        if isinstance(bar, Mapping):
            return bar.get(name, default)
        return getattr(bar, name, default)

    timestamp = _get("timestamp", _get("bar_time", _get("date", "")))
    return BacktestBarInput(
        timestamp=str(timestamp),
        close=float(_get("close")),
        open=_optional_float(_get("open")),
        high=_optional_float(_get("high")),
        low=_optional_float(_get("low")),
        volume=_optional_float(_get("volume")) or 0.0,
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
