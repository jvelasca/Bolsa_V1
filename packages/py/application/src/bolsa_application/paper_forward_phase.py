"""V2.33 / A13 — fase PAPER FORWARD: evidencia *forward* de la estrategia ACTIVE.

Cierra el salto que V2.32/A12 deja abierto: el shadow valida el finalista sobre un
hold-out **histórico** del LAB, pero nada mide cómo se comporta la ACTIVE con **mercado
nuevo posterior a la promoción**. Esta fase produce esa evidencia:

    ACTIVE ──▶ DEFINICIÓN EJECUTABLE ──▶ SEÑAL FORWARD ──▶ FILL PAPER
           ──▶ POSICIÓN ──▶ SL/T1/T2/TRAIL/EXIT ──▶ P&L FORWARD ──▶ VIGILANCIA

Reutiliza exactamente el mismo motor determinista que el shadow y el LAB
(``_simulate_rules_strategy`` sobre ``StrategyDefinitionV1``, causalidad
``index-1 → open(index)``): no se introduce un segundo motor de trading. La diferencia
es la **ventana**: el forward solo cuenta barras con ``timestamp > promoted_at``, es
decir mercado que la estrategia no vio durante LAB ni shadow.

Fail-closed (misma filosofía que el shadow):

* Sin definición ejecutable ⇒ ``forward_sin_definicion_ejecutable``.
* Sin barras nuevas post-promoción ⇒ ``forward_sin_barras``.
* Sin operaciones cerradas suficientes / métricas fuera de política ⇒ ``passed=False``.
* Un fallo del motor ⇒ ``forward_replay_fallido`` (no se inventa P&L).

Es **SIM/pure**: sin DB, sin red, sin IA. El bridge/venue LIVE no se toca.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    ActiveStrategy,
    PaperForwardPolicy,
    PaperForwardResult,
)

__all__ = [
    "ENGINE_VERSION",
    "PaperForwardConfig",
    "extract_active_executable",
    "run_paper_forward",
]

# Versión del motor forward: parte del fingerprint de la evidencia. Súbela cuando cambie
# la semántica de contabilidad/causalidad del forward.
ENGINE_VERSION = "paper-forward/2.33.0"


@dataclass(frozen=True, slots=True)
class PaperForwardConfig:
    """Ventana y capital del forward paper (defaults conservadores).

    ``promoted_at`` es el instante de promoción de la ACTIVE. Si se aporta, el forward
    solo cuenta barras con ``timestamp > promoted_at`` (mercado nuevo); si es ``None``,
    se asume que ``bars`` ya contiene únicamente barras posteriores (compatibilidad con
    llamantes que ya recortan) y se emite ``forward_sin_barras`` si no hay ninguna.

    V2.33 hardening (H2): la **identidad del dataset** forma parte del fingerprint.
    ``instrument_id``/``timeframe``/``source``/``adjusted`` se incorporan al
    ``bars_hash`` para que dos series con el mismo OHLCV pero distinto instrumento o
    marco temporal no puedan compartir identidad de evidencia. Si ``instrument_id`` es
    ``None``, el forward usa el de la ACTIVE.
    """

    initial_cash: float = 10000.0
    window_bars: int = 250
    min_bars: int = 20
    promoted_at: str | None = None
    config_hash: str | None = None
    instrument_id: str | None = None
    timeframe: str | None = None
    source: str | None = None
    adjusted: bool | None = None


@dataclass(frozen=True, slots=True)
class _BarsIdentity:
    """Identidad del dataset que entra en el ``bars_hash`` (H2, auditoría V2.32.1)."""

    instrument_id: str | None = None
    timeframe: str | None = None
    source: str | None = None
    adjusted: bool | None = None


# Identidad vacía (H2): singleton para el default de ``_denied`` (evita B008).
_NO_IDENTITY = _BarsIdentity()


def extract_active_executable(active: ActiveStrategy) -> dict[str, Any] | None:
    """Extrae la definición ejecutable de una estrategia ACTIVE.

    Es ``definition["executable"]`` (``StrategyDefinitionV1``). Sin ella no hay señal
    forward posible y el llamante debe resolver fail-closed (sin evidencia forward).
    """
    definition = active.definition if isinstance(active.definition, Mapping) else {}
    executable = definition.get("executable")
    if isinstance(executable, Mapping):
        return dict(executable)
    return None


def split_forward(
    bars: Sequence[Any],
    *,
    promoted_at: str | None,
) -> list[Any]:
    """Devuelve SOLO las barras estrictamente posteriores a ``promoted_at``.

    Si ``promoted_at`` es ``None``, devuelve las barras tal cual (el llamante garantiza
    que ya son forward). Un timestamp ausente impide demostrar la frontera temporal: se
    descarta esa barra (fail-closed, no se asume mercado nuevo).
    """
    if promoted_at is None:
        return list(bars)
    forward: list[Any] = []
    for bar in bars:
        ts = _bar_timestamp(bar)
        if ts is None:
            continue
        if ts > promoted_at:
            forward.append(bar)
    return forward


def run_paper_forward(
    *,
    active: ActiveStrategy,
    bars: Sequence[Any],
    policy: PaperForwardPolicy | None = None,
    config: PaperForwardConfig | None = None,
    as_of: str | None = None,
    data_snapshot_id: str | None = None,
    vetoes: Sequence[str] = (),
) -> PaperForwardResult:
    """Ejecuta la validación forward de la ACTIVE sobre ``bars`` (mercado nuevo).

    Devuelve SIEMPRE un ``PaperForwardResult``: nunca lanza por falta de evidencia (un
    fallo del forward es ``passed=False``, no una excepción que rompa el ciclo).

    Con ``config.promoted_at`` fijado, solo cuentan las barras posteriores a la
    promoción; su ausencia es ``forward_sin_barras``.
    """
    effective_policy = policy or PaperForwardPolicy()
    effective_config = config or PaperForwardConfig()
    executable = extract_active_executable(active)
    identity = _bars_identity(effective_config, active=active)
    fingerprint = _fingerprint_kwargs(
        active=active,
        engine_version=ENGINE_VERSION,
        config_hash=effective_config.config_hash,
        data_snapshot_id=data_snapshot_id,
    )

    if executable is None:
        return _denied(
            active,
            "forward_sin_definicion_ejecutable",
            as_of=as_of,
            promoted_at=effective_config.promoted_at,
            identity=identity,
            **fingerprint,
        )

    source_bars = split_forward(bars, promoted_at=effective_config.promoted_at)
    if not source_bars:
        return _denied(
            active,
            "forward_sin_barras",
            bars_used=0,
            as_of=as_of,
            promoted_at=effective_config.promoted_at,
            identity=identity,
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
            active,
            "forward_replay_fallido",
            bars_used=len(window),
            as_of=as_of,
            promoted_at=effective_config.promoted_at,
            window=window,
            identity=identity,
            **fingerprint,
        )

    trades = int(metrics.get("tradeCount") or 0)
    round_trips = _round_trip_count(metrics, trades)
    return effective_policy.evaluate(
        version_id=active.version_id,
        trades=trades,
        round_trips=round_trips,
        return_pct=_as_float(metrics.get("totalReturnPct")),
        max_drawdown_pct=_as_float(metrics.get("maxDrawdownPct")),
        win_rate=_as_float(metrics.get("winRate")),
        instrument_id=active.instrument_id,
        bars_used=len(window),
        as_of=as_of,
        forward_start=_bar_timestamp(window[0]) if window else None,
        forward_end=_bar_timestamp(window[-1]) if window else None,
        bars_hash=_bars_hash(window, identity),
        promoted_at=effective_config.promoted_at,
        fills=round_trips,
        vetoes=tuple(vetoes),
        **fingerprint,
    )


def _denied(
    active: ActiveStrategy,
    reason: str,
    *,
    bars_used: int = 0,
    as_of: str | None = None,
    promoted_at: str | None = None,
    window: Sequence[Any] | None = None,
    identity: _BarsIdentity = _NO_IDENTITY,
    **fingerprint: Any,
) -> PaperForwardResult:
    return PaperForwardResult(
        version_id=active.version_id,
        trades=0,
        passed=False,
        reasons=(reason,),
        instrument_id=active.instrument_id,
        bars_used=bars_used,
        as_of=as_of,
        promoted_at=promoted_at,
        forward_start=_bar_timestamp(window[0]) if window else None,
        forward_end=_bar_timestamp(window[-1]) if window else None,
        bars_hash=_bars_hash(window, identity) if window else None,
        **fingerprint,
    )


def _fingerprint_kwargs(
    *,
    active: ActiveStrategy,
    engine_version: str,
    config_hash: str | None,
    data_snapshot_id: str | None,
) -> dict[str, Any]:
    """Campos de identidad del dataset en cada resultado (evidencia reproducible)."""
    definition = active.definition if isinstance(active.definition, Mapping) else {}
    snapshot = data_snapshot_id
    if snapshot is None:
        raw_snapshot = definition.get("data_snapshot_id")
        snapshot = str(raw_snapshot) if raw_snapshot else None
    return {
        "data_snapshot_id": snapshot,
        "strategy_definition_hash": _definition_hash(active),
        "engine_version": engine_version,
        "config_hash": config_hash,
    }


def _definition_hash(active: ActiveStrategy) -> str | None:
    """Hash estable de la definición de la ACTIVE (identidad de la evidencia)."""
    definition = active.definition if isinstance(active.definition, Mapping) else {}
    raw = definition.get("executable")
    if not isinstance(raw, Mapping):
        return None
    digest = hashlib.sha256()
    digest.update(repr(sorted(raw.items(), key=lambda kv: str(kv[0]))).encode("utf-8"))
    return digest.hexdigest()


def _round_trip_count(metrics: Mapping[str, Any], trades: int) -> int:
    """Operaciones **cerradas** (no piernas). Fallback conservador si el motor no las da."""
    pnls = metrics.get("roundTripPnls")
    if isinstance(pnls, (list, tuple)):
        return len(pnls)
    return trades // 2


def _bars_hash(window: Sequence[Any], identity: _BarsIdentity) -> str | None:
    """Hash determinista de la ventana forward exacta (identidad + timestamps + OHLCV).

    H2: la cabecera de identidad (``instrument_id|timeframe|source|adjusted``) entra en
    el digest, de modo que el mismo OHLCV con distinto instrumento o marco temporal
    produce hashes distintos. Un campo ausente se serializa como cadena vacía.
    """
    if not window:
        return None
    digest = hashlib.sha256()
    digest.update(_identity_header(identity).encode("utf-8"))
    digest.update(b"\n")
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


def _identity_header(identity: _BarsIdentity) -> str:
    """Serializa la identidad del dataset (H2) de forma estable y determinista."""
    return "|".join(
        (
            identity.instrument_id or "",
            identity.timeframe or "",
            identity.source or "",
            "" if identity.adjusted is None else ("1" if identity.adjusted else "0"),
        )
    )


def _bars_identity(
    config: PaperForwardConfig,
    *,
    active: ActiveStrategy,
) -> _BarsIdentity:
    """Resuelve la identidad del dataset del forward (H2).

    El config manda; si no fija ``instrument_id``, se cae al de la ACTIVE.
    ``timeframe``/``source``/``adjusted`` no se pueden inferir de la ACTIVE: si no se
    aportan, quedan ausentes (se serializan vacíos).
    """
    return _BarsIdentity(
        instrument_id=config.instrument_id or active.instrument_id,
        timeframe=config.timeframe,
        source=config.source,
        adjusted=config.adjusted,
    )


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
