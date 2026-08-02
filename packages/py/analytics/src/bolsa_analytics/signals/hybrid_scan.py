"""Evaluación de rastreo híbrido — gate + technical_rating_v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.data_quality_v1 import (
    DataQualityBreakdown,
    compute_data_quality_v1,
    compute_global_score,
)
from bolsa_analytics.signals.fundamental_gate import passes_fundamental_gate
from bolsa_analytics.signals.rules_engine import build_indicator_context, evaluate_rule_group
from bolsa_analytics.signals.strategy import SignalEventV1, StrategyBarInput, _signal_event_id
from bolsa_analytics.signals.technical_rating_v1 import (
    TECHNICAL_RATING_V1_VERSION,
    TechnicalRatingBreakdown,
    compute_technical_rating_v1,
)


@dataclass(frozen=True, slots=True)
class DataQualityScanContext:
    bar_count: int
    last_bar_timestamp: str
    expected_last_bar_date: str | None
    last_sync_status: str | None
    last_sync_error: str | None
    recent_timestamps: list[str]
    has_fundamental_gate: bool
    fundamentals_ok: bool


@dataclass(frozen=True, slots=True)
class HybridScanCandidate:
    instrument_id: str
    symbol: str
    name: str
    signal: SignalEventV1
    ai_score: float
    rating_breakdown: TechnicalRatingBreakdown
    data_quality_score: float
    data_quality_breakdown: DataQualityBreakdown
    global_score: float


def _hybrid_config(definition: dict[str, Any]) -> dict[str, Any] | None:
    hybrid = definition.get("hybrid")
    if isinstance(hybrid, dict):
        return hybrid
    return None


def is_hybrid_definition(definition: dict[str, Any]) -> bool:
    return definition.get("kind") == "hybrid" and _hybrid_config(definition) is not None


def passes_hybrid_gate(
    definition: dict[str, Any],
    *,
    bars: list[StrategyBarInput],
    indicator_context: dict[str, list[float | None]],
) -> bool:
    hybrid = _hybrid_config(definition)
    if hybrid is None:
        return False

    rule_gate = hybrid.get("ruleGate") or {}
    if not rule_gate.get("rules"):
        return True

    closes = [bar.close for bar in bars]
    last_index = len(closes) - 1
    kind = evaluate_rule_group(
        rule_gate,
        index=last_index,
        context=indicator_context,
        closes=closes,
    )
    return kind is not None


def hybrid_min_data_quality(definition: dict[str, Any]) -> float:
    hybrid = _hybrid_config(definition) or {}
    return float(hybrid.get("minDataQuality") or 0)


def evaluate_hybrid_candidate(
    definition: dict[str, Any],
    *,
    instrument_id: str,
    symbol: str,
    name: str,
    ohlcv_bars: list[OhlcvBar],
    strategy_bars: list[StrategyBarInput],
    indicator_context: dict[str, list[float | None]],
    strategy_definition_id: str,
    strategy_version: int,
    fundamentals: dict[str, Any] | None = None,
    data_quality_context: DataQualityScanContext | None = None,
) -> HybridScanCandidate | None:
    hybrid = _hybrid_config(definition)
    if hybrid is None:
        return None

    passed_fundamental, _ = passes_fundamental_gate(definition, fundamentals)
    if not passed_fundamental:
        return None

    if not passes_hybrid_gate(
        definition,
        bars=strategy_bars,
        indicator_context=indicator_context,
    ):
        return None

    rating = compute_technical_rating_v1(ohlcv_bars)
    if rating is None:
        return None

    ai_scorer = hybrid.get("aiScorer") or {}
    min_score = float(ai_scorer.get("minScore") or 0)
    if rating.total < min_score:
        return None

    if data_quality_context is None:
        data_quality = compute_data_quality_v1(
            bar_count=len(ohlcv_bars),
            last_bar_timestamp=ohlcv_bars[-1].timestamp if ohlcv_bars else None,
            recent_timestamps=[bar.timestamp for bar in ohlcv_bars],
            has_fundamental_gate=bool(hybrid.get("fundamentalGate")),
            fundamentals_ok=passed_fundamental,
        )
    else:
        ctx = data_quality_context
        data_quality = compute_data_quality_v1(
            bar_count=ctx.bar_count,
            last_bar_timestamp=ctx.last_bar_timestamp,
            expected_last_bar_date=ctx.expected_last_bar_date,
            last_sync_status=ctx.last_sync_status,
            last_sync_error=ctx.last_sync_error,
            recent_timestamps=ctx.recent_timestamps,
            has_fundamental_gate=ctx.has_fundamental_gate,
            fundamentals_ok=ctx.fundamentals_ok,
        )

    min_data_quality = hybrid_min_data_quality(definition)
    if min_data_quality > 0 and data_quality.total < min_data_quality:
        return None

    global_score = compute_global_score(rating.total, data_quality.total)

    last_index = len(strategy_bars) - 1
    last_bar = strategy_bars[last_index]
    signal = SignalEventV1(
        id=_signal_event_id(strategy_definition_id, strategy_version, last_index, "watch"),
        instrument_id=instrument_id,
        timestamp=last_bar.timestamp,
        kind="watch",
        strategy_definition_id=strategy_definition_id,
        strategy_version=strategy_version,
        bar_index=last_index,
        price=last_bar.close,
        preset_key=definition.get("presetKey"),
    )

    return HybridScanCandidate(
        instrument_id=instrument_id,
        symbol=symbol,
        name=name,
        signal=signal,
        ai_score=rating.total,
        rating_breakdown=rating,
        data_quality_score=data_quality.total,
        data_quality_breakdown=data_quality,
        global_score=global_score,
    )


def build_indicator_context_for_definition(
    ohlcv_bars: list[OhlcvBar],
    definition: dict[str, Any],
) -> dict[str, list[float | None]]:
    specs = list(definition.get("indicatorSpecs") or [])
    return build_indicator_context(ohlcv_bars, specs)


def hybrid_scorer_version(definition: dict[str, Any]) -> str:
    hybrid = _hybrid_config(definition) or {}
    ai_scorer = hybrid.get("aiScorer") or {}
    return str(ai_scorer.get("version") or TECHNICAL_RATING_V1_VERSION)
