"""V2.32 / A12 — fase SHADOW: evidencia ejecutada del finalista (no el flag).

Cierra el P2 diferido por V2.31: hasta ahora el Promotion Gate aceptaba
``AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1`` como sustituto de validación shadow, pero el
sistema **nunca ejecutaba** nada. Esta fase produce la evidencia real:

    FINALISTA ──▶ SHADOW REPLAY ──▶ ShadowValidationResult ──▶ PROMOTION GATE

El replay es **determinista y puro** (sin DB, sin red, sin IA): reutiliza el motor
declarativo de reglas (``evaluate_rules_signals`` en modo ``gated``) sobre una ventana
de barras **separada del LAB**, con la misma contabilidad de equity/drawdown y la misma
causalidad ``index-1 → open(index)`` que el LAB. Sin look-ahead.

V2.32.1 (auditoría P1-01): la separación del LAB deja de ser documental. El replay
exige un **hold-out estricto**: la ventana shadow empieza *después* del último dato
usado por el LAB (``shadow_start > lab_end``) y no puede solaparse con él. Si no se
puede demostrar la separación o el hold-out es demasiado corto, la evidencia es
``passed=False`` (fail-closed). Además se graba un *fingerprint* reproducible del
dataset (rango, ``bars_hash``, hash de definición, versión de motor y hash de config).

Fail-closed: sin barras suficientes, sin definición ejecutable, sin separación del LAB
o sin operaciones ⇒ ``passed=False`` con motivo explícito. No se inventa evidencia.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    ShadowPolicy,
    ShadowValidationResult,
    StrategyFinalist,
)

__all__ = [
    "ENGINE_VERSION",
    "ShadowReplayConfig",
    "extract_executable",
    "run_shadow_replay",
]

# Versión del motor de replay: parte del fingerprint de la evidencia. Súbela cuando
# cambie la semántica de contabilidad/causalidad del replay.
ENGINE_VERSION = "shadow-replay/2.32.1"


@dataclass(frozen=True, slots=True)
class ShadowReplayConfig:
    """Ventana y capital del replay shadow (defaults conservadores).

    ``lab_end`` es el último timestamp usado por el LAB. Si se aporta, el replay
    calcula el hold-out estricto (solo barras con timestamp ``> lab_end``) y falla
    cerrado si no hay separación. Si es ``None``, se asume que ``bars`` ya contiene
    únicamente el hold-out (compatibilidad con llamantes que ya recortan).
    """

    initial_cash: float = 10000.0
    window_bars: int = 250
    min_bars: int = 60
    lab_end: str | None = None
    require_holdout: bool = False
    config_hash: str | None = None


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


def split_holdout(
    bars: Sequence[Any],
    *,
    lab_end: str,
) -> tuple[list[Any], list[Any]] | None:
    """Separa ``bars`` en (LAB, hold-out) por timestamp; ``None`` si no hay separación.

    Regla estricta: el hold-out contiene SOLO barras con timestamp ``> lab_end``. Si
    ninguna barra cae en el hold-out (o el rango no es demostrable), devuelve ``None``:
    el llamante debe resolver fail-closed (no se inventa una ventana "separada").
    """
    ordered = list(bars)
    if not ordered or not lab_end:
        return None
    lab: list[Any] = []
    holdout: list[Any] = []
    for bar in ordered:
        ts = _bar_timestamp(bar)
        if ts is None:
            # Un timestamp ausente impide demostrar la separación: fail-closed.
            return None
        if ts <= lab_end:
            lab.append(bar)
        else:
            holdout.append(bar)
    if not holdout:
        return None
    return lab, holdout


def run_shadow_replay(
    *,
    finalist: StrategyFinalist,
    bars: Sequence[Any],
    policy: ShadowPolicy | None = None,
    config: ShadowReplayConfig | None = None,
    as_of: str | None = None,
    data_snapshot_id: str | None = None,
) -> ShadowValidationResult:
    """Ejecuta la validación shadow del finalista sobre ``bars`` (ventana separada).

    Devuelve SIEMPRE un ``ShadowValidationResult``: nunca lanza por falta de evidencia
    (un fallo del replay es ``passed=False``, no una excepción que rompa el ciclo).

    Con ``config.lab_end`` fijado, el hold-out es estricto (``timestamp > lab_end``) y
    su ausencia es ``shadow_solape_lab``/``shadow_barras_holdout_insuficientes``.
    """
    effective_policy = policy or ShadowPolicy()
    effective_config = config or ShadowReplayConfig()
    executable = extract_executable(finalist)
    definition_hash = finalist.definition_hash
    fingerprint = _fingerprint_kwargs(
        finalist=finalist,
        definition_hash=definition_hash,
        engine_version=ENGINE_VERSION,
        config_hash=effective_config.config_hash,
        data_snapshot_id=data_snapshot_id,
    )

    if executable is None:
        return _denied(finalist, "shadow_sin_definicion_ejecutable", as_of=as_of, **fingerprint)

    lab_end = effective_config.lab_end
    if effective_config.require_holdout and not lab_end:
        # El llamante exige separación demostrable y no la aporta: fail-closed.
        return _denied(
            finalist,
            "shadow_lab_end_ausente",
            bars_used=len(bars),
            as_of=as_of,
            **fingerprint,
        )

    source_bars = list(bars)
    if lab_end:
        split = split_holdout(source_bars, lab_end=lab_end)
        if split is None:
            return _denied(
                finalist,
                "shadow_solape_lab",
                bars_used=len(source_bars),
                as_of=as_of,
                lab_end=lab_end,
                **fingerprint,
            )
        _lab, source_bars = split

    if len(source_bars) < effective_config.min_bars:
        return _denied(
            finalist,
            ("shadow_barras_holdout_insuficientes" if lab_end else "shadow_barras_insuficientes"),
            bars_used=len(source_bars),
            as_of=as_of,
            lab_end=lab_end,
            **fingerprint,
        )

    window = source_bars[-max(1, int(effective_config.window_bars)) :]
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
        return _denied(
            finalist,
            "shadow_replay_fallido",
            bars_used=len(window),
            as_of=as_of,
            lab_end=lab_end,
            window=window,
            **fingerprint,
        )

    trades = int(metrics.get("tradeCount") or 0)
    round_trips = _round_trip_count(metrics, trades)
    return effective_policy.evaluate(
        version_id=finalist.version_id,
        trades=trades,
        round_trips=round_trips,
        return_pct=_as_float(metrics.get("totalReturnPct")),
        max_drawdown_pct=_as_float(metrics.get("maxDrawdownPct")),
        win_rate=_as_float(metrics.get("winRate")),
        instrument_id=_finalist_instrument(finalist),
        bars_used=len(window),
        as_of=as_of,
        shadow_start=_bar_timestamp(window[0]) if window else None,
        shadow_end=_bar_timestamp(window[-1]) if window else None,
        bars_hash=_bars_hash(window),
        lab_end=lab_end,
        **fingerprint,
    )


def _denied(
    finalist: StrategyFinalist,
    reason: str,
    *,
    bars_used: int = 0,
    as_of: str | None = None,
    lab_end: str | None = None,
    window: Sequence[Any] | None = None,
    **fingerprint: Any,
) -> ShadowValidationResult:
    return ShadowValidationResult(
        version_id=finalist.version_id,
        trades=0,
        passed=False,
        reasons=(reason,),
        instrument_id=_finalist_instrument(finalist),
        bars_used=bars_used,
        as_of=as_of,
        lab_end=lab_end,
        shadow_start=_bar_timestamp(window[0]) if window else None,
        shadow_end=_bar_timestamp(window[-1]) if window else None,
        bars_hash=_bars_hash(window) if window else None,
        **fingerprint,
    )


def _fingerprint_kwargs(
    *,
    finalist: StrategyFinalist,
    definition_hash: str | None,
    engine_version: str,
    config_hash: str | None,
    data_snapshot_id: str | None,
) -> dict[str, Any]:
    """Campos de identidad del dataset en cada resultado (evidencia reproducible)."""
    definition = finalist.definition if isinstance(finalist.definition, Mapping) else {}
    snapshot = data_snapshot_id
    if snapshot is None:
        raw_snapshot = definition.get("data_snapshot_id")
        snapshot = str(raw_snapshot) if raw_snapshot else None
    return {
        "data_snapshot_id": snapshot,
        "strategy_definition_hash": definition_hash,
        "engine_version": engine_version,
        "config_hash": config_hash,
    }


def _round_trip_count(metrics: Mapping[str, Any], trades: int) -> int:
    """Operaciones **cerradas** (no piernas). Fallback conservador si el motor no las da."""
    pnls = metrics.get("roundTripPnls")
    if isinstance(pnls, (list, tuple)):
        return len(pnls)
    # Sin detalle de round-trips, el mínimo garantizado es la mitad de las piernas
    # (cada operación cerrada son dos piernas: entrada + salida).
    return trades // 2


def _bars_hash(window: Sequence[Any]) -> str | None:
    """Hash determinista del hold-out exacto (timestamps + OHLCV)."""
    if not window:
        return None
    digest = hashlib.sha256()
    for bar in window:
        ts = _bar_timestamp(bar)
        if ts is None:
            return None
        parts = [
            ts,
            _fmt(_get_field(bar, "open")),
            _fmt(_get_field(bar, "high")),
            _fmt(_get_field(bar, "low")),
            _fmt(_get_field(bar, "close")),
            _fmt(_get_field(bar, "volume")),
        ]
        digest.update("|".join(parts).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.10g}"
    except (TypeError, ValueError):
        return str(value)


def _get_field(bar: Any, name: str) -> Any:
    if isinstance(bar, Mapping):
        return bar.get(name)
    return getattr(bar, name, None)


def _bar_timestamp(bar: Any) -> str | None:
    ts = _get_field(bar, "timestamp")
    if ts is None:
        ts = _get_field(bar, "bar_time")
    if ts is None:
        return None
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)


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
