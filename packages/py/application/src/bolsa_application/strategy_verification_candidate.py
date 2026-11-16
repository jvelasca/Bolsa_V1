"""Candidata point-in-time y *shadow forward* para la verificación periódica.

Problema
--------
El brazo ``candidate`` del as-run se quedaba en ``candidate_not_provided``: el CLI nunca
construía sus patas, así que la pregunta «¿seguimos en la mejor estrategia?» no tenía
segunda mitad. Este módulo aporta la pieza que faltaba, con dos caminos **separados** y
honestos:

* **Misma entrada, salida de la candidata** (brazo ``candidate``): la candidata declara las
  patas que tendría en ``D`` y se comparan sus salidas con las de la operativa real.
* **Otra estrategia** (*shadow forward*): la definición ejecutable de la candidata se rejuega
  sobre las barras posteriores a ``D`` con el mismo motor del forward y el mismo modelo de
  coste. No es una columna del mismo ciclo: es un libro paralelo.

Reglas duras
------------
* ``candidateAsOf <= D``. Una candidata construida después de ``D`` no pudo decidir en ``D``;
  medirla sería look-ahead. Sin fecha se declara ``candidate_not_point_in_time``.
* Sin versión canónica se declara ``candidate_version_unavailable``: dos definiciones con el
  mismo nombre y distinta versión no son la misma candidata.
* Sin barras o sin definición ejecutable se declara el hueco; **nunca** se rellena con el
  brazo estructural ni con ceros.
* Módulo puro salvo el motor de replay (import diferido), al que no se le pasa nada posterior
  a la ventana declarada.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_application.dia_d_as_run import (
    DEFAULT_COST_BPS,
    AsRunExecutionModel,
    AsRunLeg,
    execution_model_for,
)

__all__ = [
    "CandidateForwardResult",
    "CandidateSnapshot",
    "CandidateVerificationProvider",
    "candidate_gap_reason",
    "load_candidate_snapshot",
    "run_candidate_shadow_forward",
]

#: Motivos de hueco declarados (nunca un resultado inventado).
GAP_NOT_PROVIDED = "candidate_not_provided"
GAP_NOT_POINT_IN_TIME = "candidate_not_point_in_time"
GAP_VERSION_UNAVAILABLE = "candidate_version_unavailable"
GAP_DEFINITION_UNAVAILABLE = "candidate_definition_unavailable"
GAP_UNIVERSE_MISMATCH = "candidate_outside_universe"
GAP_NO_FORWARD_BARS = "candidate_no_forward_bars"
GAP_FORWARD_FAILED = "candidate_forward_failed"


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    """Candidata **vigente en D**: identidad, versión, patas y definición ejecutable.

    ``as_of`` es la fecha en que la candidata ya existía. El llamante es responsable de
    resolverla en el snapshot point-in-time; este módulo comprueba la frontera temporal.
    """

    candidate_id: str
    as_of: str
    strategy_version: str | None = None
    instrument_id: str | None = None
    legs: tuple[AsRunLeg, ...] = ()
    definition: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not str(self.candidate_id or "").strip():
            raise ValueError("candidateId es obligatorio")
        if len(str(self.as_of or "")) < 10:
            raise ValueError("asOf debe ser una fecha YYYY-MM-DD")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidateId": str(self.candidate_id),
            "asOf": str(self.as_of)[:10],
            "strategyVersion": self.strategy_version,
            "instrumentId": self.instrument_id,
            "legs": [leg.to_dict() for leg in self.legs],
            "definitionHash": (
                None
                if self.definition is None
                else hashlib.sha256(
                    json.dumps(
                        dict(self.definition), sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                ).hexdigest()
            ),
        }


class CandidateVerificationProvider(Protocol):
    """Puerto: devuelve la candidata **conocida** en ``day`` (``None`` si no hay)."""

    async def snapshot(self, *, account_id: str, day: str) -> CandidateSnapshot | None: ...


def candidate_gap_reason(
    snapshot: CandidateSnapshot | None,
    *,
    day: str,
    universe_instruments: Sequence[str],
    require_legs: bool = True,
) -> str | None:
    """Motivo por el que la candidata NO puede medirse, aplicando punto en el tiempo."""
    if snapshot is None:
        return GAP_NOT_PROVIDED
    as_of = str(snapshot.as_of or "")[:10]
    if not as_of or as_of > str(day)[:10]:
        return GAP_NOT_POINT_IN_TIME
    if not str(snapshot.strategy_version or "").strip():
        return GAP_VERSION_UNAVAILABLE
    outside = sorted(
        {leg.instrument_id for leg in snapshot.legs} - set(universe_instruments)
    )
    if outside:
        return f"{GAP_UNIVERSE_MISMATCH}:{','.join(outside)}"
    if require_legs and not snapshot.legs:
        return "candidate_no_legs_at_d"
    return None


def load_candidate_snapshot(payload: Mapping[str, Any]) -> CandidateSnapshot:
    """Construye la candidata desde el JSON declarado por el operador/CLI.

    Acepta ``legs`` con la forma de ``AsRunLeg.to_dict()`` y una ``definition`` ejecutable
    opcional (para el shadow forward).
    """
    legs: list[AsRunLeg] = []
    for raw in payload.get("legs") or ():
        if not isinstance(raw, Mapping):
            raise ValueError("cada pata de la candidata debe ser un objeto")
        legs.append(
            AsRunLeg(
                instrument_id=str(raw.get("instrumentId") or ""),
                direction=str(raw.get("direction") or "long"),  # type: ignore[arg-type]
                quantity=float(raw.get("quantity") or 0.0),
                entry=float(raw.get("entry") or 0.0),
                structural_stop=(
                    None
                    if raw.get("structuralStop") is None
                    else float(raw["structuralStop"])
                ),
                target1=None if raw.get("target1") is None else float(raw["target1"]),
                target2=None if raw.get("target2") is None else float(raw["target2"]),
                cycle_id=None if raw.get("cycleId") is None else str(raw["cycleId"]),
            )
        )
    definition = payload.get("definition")
    return CandidateSnapshot(
        candidate_id=str(payload.get("candidateId") or ""),
        as_of=str(payload.get("asOf") or ""),
        strategy_version=(
            None if payload.get("strategyVersion") is None else str(payload["strategyVersion"])
        ),
        instrument_id=(
            None if payload.get("instrumentId") is None else str(payload["instrumentId"])
        ),
        legs=tuple(legs),
        definition=dict(definition) if isinstance(definition, Mapping) else None,
    )


@dataclass(frozen=True, slots=True)
class CandidateForwardResult:
    """Resultado del shadow forward de la candidata sobre barras posteriores a ``D``."""

    measured: bool
    reason: str | None = None
    candidate_id: str | None = None
    strategy_version: str | None = None
    as_of: str | None = None
    instrument_id: str | None = None
    bars_used: int = 0
    first_bar: str | None = None
    last_bar: str | None = None
    trades: int = 0
    round_trips: int = 0
    return_pct: float | None = None
    max_drawdown_pct: float | None = None
    win_rate: float | None = None
    bars_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "measured": self.measured,
            "reason": self.reason,
            "candidateId": self.candidate_id,
            "strategyVersion": self.strategy_version,
            "asOf": self.as_of,
            "instrumentId": self.instrument_id,
            "barsUsed": self.bars_used,
            "firstBar": self.first_bar,
            "lastBar": self.last_bar,
            "trades": self.trades,
            "roundTrips": self.round_trips,
            "returnPct": self.return_pct,
            "maxDrawdownPct": self.max_drawdown_pct,
            "winRate": self.win_rate,
            "barsHash": self.bars_hash,
        }


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _bar_timestamp(bar: Any) -> str | None:
    if isinstance(bar, Mapping):
        value = bar.get("timestamp", bar.get("bar_time", bar.get("date")))
    else:
        value = getattr(bar, "timestamp", None)
    text = str(value or "").strip()
    return text or None


def _to_backtest_bar(bar: Any) -> Any:
    from bolsa_analytics.backtest import BacktestBarInput

    if isinstance(bar, BacktestBarInput):
        return bar

    def _get(name: str, default: Any = None) -> Any:
        if isinstance(bar, Mapping):
            return bar.get(name, default)
        return getattr(bar, name, default)

    return BacktestBarInput(
        timestamp=str(_get("timestamp", "")),
        close=float(_get("close")),
        open=_as_float(_get("open")),
        high=_as_float(_get("high")),
        low=_as_float(_get("low")),
        volume=_as_float(_get("volume")) or 0.0,
    )


def run_candidate_shadow_forward(
    snapshot: CandidateSnapshot | None,
    bars: Sequence[Any],
    *,
    day: str,
    to_day: str | None = None,
    window_bars: int = 252,
    initial_cash: float = 100_000.0,
    cost_bps: float = DEFAULT_COST_BPS,
    execution: AsRunExecutionModel | None = None,
) -> CandidateForwardResult:
    """Rejuega la candidata sobre las barras **posteriores a D** (sin look-ahead).

    El recorte temporal es explícito: barras ``> day`` y, si se declara ``to_day``,
    ``<= to_day``. La ejecución usa el modelo de coste del perfil (``AsRunExecutionModel``);
    el motor recibe solo esa ventana, así que no puede ver pasado ni futuro fuera de ella.
    """
    execution_model_for(execution, cost_bps)  # valida el modelo declarado
    if snapshot is None:
        return CandidateForwardResult(measured=False, reason=GAP_NOT_PROVIDED)
    if snapshot.definition is None:
        return CandidateForwardResult(
            measured=False,
            reason=GAP_DEFINITION_UNAVAILABLE,
            candidate_id=snapshot.candidate_id,
            strategy_version=snapshot.strategy_version,
            as_of=str(snapshot.as_of)[:10],
            instrument_id=snapshot.instrument_id,
        )
    forward = [
        bar
        for bar in bars
        if (timestamp := _bar_timestamp(bar)) is not None
        and timestamp > str(day)
        and (to_day is None or timestamp[:10] <= str(to_day))
    ]
    forward.sort(key=lambda bar: str(_bar_timestamp(bar)))
    if not forward:
        return CandidateForwardResult(
            measured=False,
            reason=GAP_NO_FORWARD_BARS,
            candidate_id=snapshot.candidate_id,
            strategy_version=snapshot.strategy_version,
            as_of=str(snapshot.as_of)[:10],
            instrument_id=snapshot.instrument_id,
        )
    window = forward[-max(1, int(window_bars)) :]
    try:
        from bolsa_analytics.optimize.rules_grid import _simulate_rules_strategy

        metrics = _simulate_rules_strategy(
            [_to_backtest_bar(bar) for bar in window],
            dict(snapshot.definition),
            initial_cash=float(initial_cash),
            attach_round_trips=True,
        )
    except Exception:  # noqa: BLE001 — sin evidencia no se inventa: hueco declarado.
        return CandidateForwardResult(
            measured=False,
            reason=GAP_FORWARD_FAILED,
            candidate_id=snapshot.candidate_id,
            strategy_version=snapshot.strategy_version,
            as_of=str(snapshot.as_of)[:10],
            instrument_id=snapshot.instrument_id,
            bars_used=len(window),
        )

    first_bar = _bar_timestamp(window[0])
    last_bar = _bar_timestamp(window[-1])
    trades = int(metrics.get("tradeCount") or 0)
    round_trip_pnls = metrics.get("roundTripPnls") or ()
    bars_hash = hashlib.sha256(
        json.dumps(
            [[_bar_timestamp(bar), round(float(bar.close), 6)] for bar in window],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return CandidateForwardResult(
        measured=True,
        candidate_id=snapshot.candidate_id,
        strategy_version=snapshot.strategy_version,
        as_of=str(snapshot.as_of)[:10],
        instrument_id=snapshot.instrument_id,
        bars_used=len(window),
        first_bar=first_bar,
        last_bar=last_bar,
        trades=trades,
        round_trips=len(round_trip_pnls),
        return_pct=_as_float(metrics.get("totalReturnPct")),
        max_drawdown_pct=_as_float(metrics.get("maxDrawdownPct")),
        win_rate=_as_float(metrics.get("winRate")),
        bars_hash=bars_hash,
    )
