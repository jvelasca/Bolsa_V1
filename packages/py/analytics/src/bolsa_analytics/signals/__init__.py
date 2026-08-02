"""SC-0 — evaluación de señales preset (base unificada backtest / screener)."""

from bolsa_analytics.signals.evaluate import (
    PresetFeatureSeries,
    PresetStrategyType,
    SignalEvent,
    SignalKind,
    build_preset_features,
    evaluate_preset_bar_raw,
    evaluate_preset_signals,
    evaluate_preset_signals_gated,
)
from bolsa_analytics.signals.strategy import (
    SignalEvaluationMode,
    SignalEventV1,
    StrategyBarInput,
    drawing_marker_to_signal_event_v1,
    evaluate_strategy,
    evaluate_strategy_last_bar,
    resolve_preset_key,
)

__all__ = [
    "PresetFeatureSeries",
    "PresetStrategyType",
    "SignalEvaluationMode",
    "SignalEvent",
    "SignalEventV1",
    "SignalKind",
    "StrategyBarInput",
    "build_preset_features",
    "drawing_marker_to_signal_event_v1",
    "evaluate_preset_bar_raw",
    "evaluate_preset_signals",
    "evaluate_preset_signals_gated",
    "evaluate_strategy",
    "evaluate_strategy_last_bar",
    "resolve_preset_key",
]
