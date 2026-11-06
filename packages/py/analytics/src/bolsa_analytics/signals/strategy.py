"""SC-1 — evalúa StrategyDefinitionV1 sobre barras → SignalEventV1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.signals.evaluate import (
    PresetFeatureSeries,
    PresetStrategyType,
    SignalEvent,
    build_preset_features,
    evaluate_preset_signals,
    evaluate_preset_signals_gated,
)
from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_analytics.signals.preset_rules import (
    definition_has_rules,
    enrich_definition_with_preset_rules,
)
from bolsa_analytics.signals.rules_engine import evaluate_rules_signals

SignalEvaluationMode = Literal["raw", "gated"]


@dataclass(frozen=True, slots=True)
class StrategyBarInput:
    """Especificación / input: Strategy Bar Input."""
    timestamp: str
    close: float


@dataclass(frozen=True, slots=True)
class SignalEventV1:
    """Tipo analytics: Signal Event 1.

    S4 (auditoría .183) — contrato de tiempo explícito: la señal se decide sobre la
    barra **cerrada** ``signal_bar`` y se ejecuta en la barra **siguiente**
    ``execution_bar = signal_bar + 1``. Los dos campos son opcionales para no romper a
    los consumidores históricos: si faltan, se resuelven con ``bar_index`` y
    ``bar_index + 1`` respectivamente.

    Un evento cuyo ``execution_bar`` no sea posterior a ``signal_bar`` es **lookahead**
    y quien vaya a ejecutarlo debe rechazarlo: ``has_lookahead()`` lo expone y
    ``ExecutionRouter`` lo filtra fail-closed.
    """
    id: str
    instrument_id: str
    timestamp: str
    kind: Literal["entry_long", "entry_short", "exit", "watch"]
    strategy_definition_id: str
    strategy_version: int
    bar_index: int
    price: float
    data_version: str | None = None
    indicator_snapshot_hash: str | None = None
    preset_key: PresetStrategyType | None = None
    signal_bar: int | None = None
    execution_bar: int | None = None

    @property
    def resolved_signal_bar(self) -> int:
        """Barra cerrada usada para decidir; ``bar_index`` si el campo es ``None``."""
        return self.bar_index if self.signal_bar is None else self.signal_bar

    @property
    def resolved_execution_bar(self) -> int:
        """Barra de ejecución; ``signal_bar + 1`` si el campo es ``None``."""
        if self.execution_bar is not None:
            return self.execution_bar
        return self.resolved_signal_bar + 1

    def has_lookahead(self) -> bool:
        """``True`` si la ejecución declarada no es posterior a la señal."""
        return self.resolved_execution_bar <= self.resolved_signal_bar


def _infer_preset_from_indicator_specs(specs: list[dict[str, Any]]) -> PresetStrategyType | None:
    def has_sma(period: int) -> bool:
        return any(
            spec.get("definitionId") == "sma" and int(spec.get("parameters", {}).get("period", 0)) == period
            for spec in specs
        )

    if has_sma(20) and has_sma(50):
        return "sma_crossover"

    if specs and all(spec.get("definitionId") == "rsi" for spec in specs):
        if any(int(spec.get("parameters", {}).get("period", 0)) == 14 for spec in specs):
            return "rsi_mean_reversion"

    return None


def resolve_preset_key(definition: dict[str, Any]) -> PresetStrategyType:
    """Resuelve ``preset_key``."""
    preset = definition.get("presetKey")
    if is_valid_preset_key(preset):
        return preset

    inferred = _infer_preset_from_indicator_specs(definition.get("indicatorSpecs") or [])
    if inferred is not None:
        return inferred

    raise ValueError(
        "StrategyDefinitionV1 requires presetKey or recognizable indicatorSpecs"
    )


def _signal_event_id(
    strategy_definition_id: str,
    strategy_version: int,
    bar_index: int,
    kind: str,
) -> str:
    return f"sig:{strategy_definition_id}:v{strategy_version}:{bar_index}:{kind}"


def _to_signal_event_v1(
    event: SignalEvent,
    *,
    instrument_id: str,
    strategy_definition_id: str,
    strategy_version: int,
    data_version: str | None = None,
    indicator_snapshot_hash: str | None = None,
) -> SignalEventV1:
    return SignalEventV1(
        id=_signal_event_id(strategy_definition_id, strategy_version, event.bar_index, event.kind),
        instrument_id=instrument_id,
        timestamp=event.timestamp,
        kind=event.kind,
        strategy_definition_id=strategy_definition_id,
        strategy_version=strategy_version,
        bar_index=event.bar_index,
        price=event.price,
        data_version=data_version,
        indicator_snapshot_hash=indicator_snapshot_hash,
        preset_key=event.preset_key,
        # S4: la señal nace de la barra cerrada ``t``; su ejecución es la ``t + 1``.
        signal_bar=event.bar_index,
        execution_bar=event.bar_index + 1,
    )


def evaluate_strategy(
    definition: dict[str, Any],
    bars: list[StrategyBarInput],
    *,
    instrument_id: str | None = None,
    mode: SignalEvaluationMode = "raw",
    data_version: str | None = None,
    indicator_snapshot_hash: str | None = None,
    features: PresetFeatureSeries | None = None,
    indicator_context: dict[str, list[float | None]] | None = None,
    assume_long: bool = False,
) -> list[SignalEventV1]:
    """Evalúa StrategyDefinitionV1 H0 (presets) sobre OHLCV → señales discretas.

    ``assume_long`` (B-3): con ``mode="gated"`` el estado de cartera se **replaya** desde
    el inicio de la ventana. Si la posición ya estaba abierta **antes** de la ventana,
    ese replay no ve la entrada y suprime la salida. Declarar ``assume_long=True``
    arranca el replay con la posición abierta —que es la verdad del libro— y **suprime
    las entradas**: dentro no se vuelve a comprar, ni siquiera si el replay consume una
    salida a mitad de ventana (re-entrar en la misma evaluación no es una decisión
    posible).

    Ojo: esto sigue siendo un replay de **transiciones**. Si la salida ya se cumplía al
    empezar la ventana, el replay la consume ahí y la última barra puede no emitir nada
    aunque la condición de salida vuelva a cumplirse. La pregunta «¿cierro ahora?» es de
    **nivel** y la responde el decisor de la ACTIVE sobre la última barra
    (``active_strategy_signal_evaluator``), no este motor.

    Solo aplica al camino **declarativo** (definiciones con reglas en ``entries``/
    ``exits``). El camino legacy de presets sin reglas lo ignora; los 21 presets del
    catálogo llevan reglas, así que no queda fuera ningún preset.
    """
    if not bars:
        raise ValueError("bars must not be empty")

    strategy_definition_id = str(definition.get("id") or "unknown")
    strategy_version = int(definition.get("version") or 1)
    resolved_instrument_id = instrument_id
    if resolved_instrument_id is None:
        universe = definition.get("universe") or {}
        instrument_ids = universe.get("instrumentIds") or []
        if not instrument_ids:
            raise ValueError("instrumentId or universe.instrumentIds[0] is required")
        resolved_instrument_id = str(instrument_ids[0])

    preset_key = resolve_preset_key(definition)
    timestamps = [bar.timestamp for bar in bars]
    closes = [bar.close for bar in bars]

    resolved = enrich_definition_with_preset_rules(definition)
    if definition_has_rules(resolved):
        preset_events = evaluate_rules_signals(
            resolved,
            timestamps,
            closes,
            mode=mode,
            assume_long=assume_long,
            context=indicator_context,
        )
    else:
        resolved_features = features or build_preset_features(timestamps, closes)
        if mode == "gated":
            preset_events = evaluate_preset_signals_gated(
                preset_key, timestamps, closes, resolved_features
            )
        else:
            preset_events = evaluate_preset_signals(preset_key, timestamps, closes, resolved_features)

    return [
        _to_signal_event_v1(
            event,
            instrument_id=resolved_instrument_id,
            strategy_definition_id=strategy_definition_id,
            strategy_version=strategy_version,
            data_version=data_version,
            indicator_snapshot_hash=indicator_snapshot_hash,
        )
        for event in preset_events
    ]


def evaluate_strategy_last_bar(
    definition: dict[str, Any],
    bars: list[StrategyBarInput],
    *,
    instrument_id: str | None = None,
    mode: SignalEvaluationMode = "raw",
    data_version: str | None = None,
    indicator_snapshot_hash: str | None = None,
    features: PresetFeatureSeries | None = None,
    indicator_context: dict[str, list[float | None]] | None = None,
    assume_long: bool = False,
) -> list[SignalEventV1]:
    """Señales en la última barra — modo screener (SC-2).

    ``assume_long`` (B-3) delega en ``evaluate_strategy``: arranca la posición abierta y
    suprime las entradas. La decisión de **cerrar** con la posición abierta es una
    pregunta de nivel que resuelve el decisor de la ACTIVE, no esta proyección.
    """
    events = evaluate_strategy(
        definition,
        bars,
        instrument_id=instrument_id,
        mode=mode,
        data_version=data_version,
        indicator_snapshot_hash=indicator_snapshot_hash,
        features=features,
        indicator_context=indicator_context,
        assume_long=assume_long,
    )
    if not bars:
        return []
    last_index = len(bars) - 1
    return [event for event in events if event.bar_index == last_index]


def drawing_marker_to_signal_event_v1(
    marker: dict[str, Any],
    *,
    instrument_id: str,
    strategy_definition_id: str,
    strategy_version: int,
    bar_index: int,
) -> SignalEventV1:
    """Convierte DrawingReplayMarker → SignalEventV1 (cruce nivel → entry/exit)."""
    direction = marker.get("direction")
    if direction == "up":
        kind: Literal["entry_long", "entry_short", "exit", "watch"] = "entry_long"
    elif direction == "down":
        kind = "exit"
    else:
        kind = "watch"

    marker_id = str(marker.get("id") or f"draw:{marker.get('drawingId', 'unknown')}:{bar_index}")
    timestamp = str(marker["timestamp"])
    price = float(marker["price"])

    return SignalEventV1(
        id=f"sig:draw:{marker_id}",
        instrument_id=instrument_id,
        timestamp=timestamp,
        kind=kind,
        strategy_definition_id=strategy_definition_id,
        strategy_version=strategy_version,
        bar_index=bar_index,
        price=price,
        signal_bar=bar_index,
        execution_bar=bar_index + 1,
    )
