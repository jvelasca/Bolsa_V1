"""Evalúa reglas de presets H0 barra a barra — paridad backtest y futuro screener."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bolsa_analytics.indicators import build_indicator_series

PresetStrategyType = Literal["sma_crossover", "rsi_mean_reversion"]
SignalKind = Literal["entry_long", "entry_short", "exit"]


@dataclass(frozen=True, slots=True)
class PresetFeatureSeries:
    sma20: list[float | None]
    sma50: list[float | None]
    rsi14: list[float | None]

    def __len__(self) -> int:
        return len(self.sma20)


@dataclass(frozen=True, slots=True)
class SignalEvent:
    """Evento discreto — subset de SignalEventV1 (SC-1 añade strategy/instrument metadata)."""

    kind: SignalKind
    bar_index: int
    timestamp: str
    price: float
    preset_key: PresetStrategyType


def build_preset_features(
    timestamps: list[str],
    closes: list[float],
) -> PresetFeatureSeries:
    indicators = build_indicator_series(timestamps, closes)
    return PresetFeatureSeries(
        sma20=[point.sma20 for point in indicators],
        sma50=[point.sma50 for point in indicators],
        rsi14=[point.rsi14 for point in indicators],
    )


def _detect_sma_cross(
    sma20: list[float | None],
    sma50: list[float | None],
    index: int,
) -> Literal["bullish", "bearish"] | None:
    if index < 1:
        return None

    prev20 = sma20[index - 1]
    prev50 = sma50[index - 1]
    curr20 = sma20[index]
    curr50 = sma50[index]

    if prev20 is None or prev50 is None or curr20 is None or curr50 is None:
        return None

    if prev20 <= prev50 and curr20 > curr50:
        return "bullish"
    if prev20 >= prev50 and curr20 < curr50:
        return "bearish"
    return None


def evaluate_preset_bar_raw(
    preset_key: PresetStrategyType,
    features: PresetFeatureSeries,
    bar_index: int,
) -> SignalKind | None:
    """Regla pura en cierre de barra — sin estado de cartera (screener)."""
    if preset_key == "sma_crossover":
        cross = _detect_sma_cross(features.sma20, features.sma50, bar_index)
        if cross == "bullish":
            return "entry_long"
        if cross == "bearish":
            return "exit"
        return None

    if preset_key == "rsi_mean_reversion":
        rsi = features.rsi14[bar_index]
        if rsi is not None and rsi < 30:
            return "entry_long"
        if rsi is not None and rsi > 70:
            return "exit"
        return None

    raise ValueError(f"Unsupported preset: {preset_key}")


def evaluate_preset_signals(
    preset_key: PresetStrategyType,
    timestamps: list[str],
    closes: list[float],
    features: PresetFeatureSeries | None = None,
) -> list[SignalEvent]:
    """Todas las señales raw del preset (sin gating de posición)."""
    if len(timestamps) != len(closes):
        raise ValueError("timestamps and closes length mismatch")
    resolved = features or build_preset_features(timestamps, closes)
    if len(resolved) != len(timestamps):
        raise ValueError("features length mismatch")

    events: list[SignalEvent] = []
    for index, timestamp in enumerate(timestamps):
        kind = evaluate_preset_bar_raw(preset_key, resolved, index)
        if kind is None:
            continue
        events.append(
            SignalEvent(
                kind=kind,
                bar_index=index,
                timestamp=timestamp,
                price=closes[index],
                preset_key=preset_key,
            )
        )
    return events


def evaluate_preset_signals_gated(
    preset_key: PresetStrategyType,
    timestamps: list[str],
    closes: list[float],
    features: PresetFeatureSeries | None = None,
) -> list[SignalEvent]:
    """Señales con gating long-only (paridad motor backtest H0)."""
    resolved = features or build_preset_features(timestamps, closes)
    events: list[SignalEvent] = []
    has_long = False

    for index, timestamp in enumerate(timestamps):
        raw = evaluate_preset_bar_raw(preset_key, resolved, index)
        if raw is None:
            continue
        if raw == "entry_long" and not has_long:
            events.append(
                SignalEvent(
                    kind="entry_long",
                    bar_index=index,
                    timestamp=timestamp,
                    price=closes[index],
                    preset_key=preset_key,
                )
            )
            has_long = True
        elif raw == "exit" and has_long:
            events.append(
                SignalEvent(
                    kind="exit",
                    bar_index=index,
                    timestamp=timestamp,
                    price=closes[index],
                    preset_key=preset_key,
                )
            )
            has_long = False

    return events
