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
from bolsa_analytics.signals.preset_rules import definition_has_rules, enrich_definition_with_preset_rules
from bolsa_analytics.signals.rules_engine import evaluate_rules_signals

SignalEvaluationMode = Literal["raw", "gated"]


@dataclass(frozen=True, slots=True)
class StrategyBarInput:
    timestamp: str
    close: float


@dataclass(frozen=True, slots=True)
class SignalEventV1:
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
) -> list[SignalEventV1]:
    """Evalúa StrategyDefinitionV1 H0 (presets) sobre OHLCV → señales discretas."""
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
) -> list[SignalEventV1]:
    """Señales en la última barra — modo screener (SC-2)."""
    events = evaluate_strategy(
        definition,
        bars,
        instrument_id=instrument_id,
        mode=mode,
        data_version=data_version,
        indicator_snapshot_hash=indicator_snapshot_hash,
        features=features,
        indicator_context=indicator_context,
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
    )
