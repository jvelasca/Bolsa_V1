"""Rules engine v1 — evalúa RuleGroupV1 sobre OHLCV (ADR-010 P7)."""

from __future__ import annotations

from typing import Any, Literal

from bolsa_analytics.indicators.compute import (
    IndicatorSpecInput,
    OhlcvBar,
    compute_adx,
    compute_atr,
    compute_bollinger,
    compute_cci,
    compute_donchian,
    compute_ema,
    compute_ichimoku,
    compute_macd_line,
    compute_macd_signal_line,
    compute_rsi,
    compute_sma,
    compute_stoch_k,
    compute_supertrend,
    compute_vwap,
    compute_williams_r,
    instance_spec_key,
)
from bolsa_analytics.signals.evaluate import SignalEvent, SignalKind
from bolsa_analytics.signals.preset_rules import (
    enrich_definition_with_preset_rules,
    rule_group_has_rules,
)

RuleOperator = Literal["lt", "lte", "gt", "gte", "eq"]


def _spec_input(raw: dict[str, Any]) -> IndicatorSpecInput:
    return IndicatorSpecInput(
        definition_id=str(raw.get("definitionId") or ""),
        parameters=dict(raw.get("parameters") or {}),
    )


def _spec_key(raw: dict[str, Any]) -> str:
    spec = _spec_input(raw)
    return instance_spec_key(spec.definition_id, spec.parameters)


# Resolución de series de indicador: solamente las claves causales se cablean en el
# evaluador de señales backtest/research (F-IND-1). Las salidas no causales (que
# dependen de datos futuros) o no soportadas devuelven `None` para que la regla
# simplemente no dispare, sin look-ahead. La visualización/chart NO pasa por aquí y
# no se ve afectada.
_NON_CAUSAL_OUTPUT_LINES: dict[str, frozenset[str]] = {
    "ich": frozenset({"chikou"}),
}


def _series_for_spec(
    bars: list[OhlcvBar],
    closes: list[float],
    definition_id: str,
    parameters: dict[str, Any],
) -> list[float | None] | None:
    """Resuelve una serie de indicador por `definition_id` (presets v2 incl. dc/adx/ich/vwap/st).

    GUARDIA DE CAUSALIDAD (F-IND-1): este método solo se usa para backtest/research
    (el chart no pasa por aquí). Las salidas que dependen de datos futuros
    (`ich:chikou`, fractals `fr`) devuelven `None` y quedan fuera del feature set de
    señales. Fractals (`fr`) no se cablean en esta fase.
    """
    if definition_id == "fr":
        return None

    if definition_id in _NON_CAUSAL_OUTPUT_LINES:
        line = str(parameters.get("line") or "main")
        if line in _NON_CAUSAL_OUTPUT_LINES[definition_id]:
            # p. ej. ich:chikou usa `bars[i+displacement].close` (datos futuros) →
            # no puede usarse como feature de señal en backtest.
            return None

    try:
        period = int(parameters.get("period", 14))
    except (TypeError, ValueError):
        period = 14

    line = str(parameters.get("line") or "main")

    if definition_id == "sma":
        return compute_sma(closes, period)
    if definition_id == "ema":
        return compute_ema(closes, period)
    if definition_id == "rsi":
        return compute_rsi(closes, period)
    if definition_id == "cci":
        return compute_cci(bars, period)
    if definition_id == "stoch":
        k_period = int(parameters.get("kPeriod", period))
        return compute_stoch_k(bars, k_period)
    if definition_id == "bb":
        std_dev = float(parameters.get("stdDev", 2))
        mid, upper, lower = compute_bollinger(closes, period, std_dev)
        if line == "upper":
            return upper
        if line == "lower":
            return lower
        return mid
    if definition_id == "macd":
        fast = int(parameters.get("fastPeriod", 12))
        slow = int(parameters.get("slowPeriod", 26))
        signal_period = int(parameters.get("signalPeriod", 9))
        if line == "signal":
            return compute_macd_signal_line(closes, fast, slow, signal_period)
        return compute_macd_line(closes, fast, slow)
    if definition_id == "atr":
        return compute_atr(bars, period)
    if definition_id == "willr":
        return compute_williams_r(bars, period)
    if definition_id == "dc":
        upper, mid, lower = compute_donchian(bars, period)
        if line == "upper":
            return upper
        if line == "lower":
            return lower
        return mid
    if definition_id == "adx":
        adx, plus_di, minus_di = compute_adx(bars, period)
        if line == "plus_di":
            return plus_di
        if line == "minus_di":
            return minus_di
        return adx
    if definition_id == "vwap":
        return compute_vwap(bars)
    if definition_id == "st":
        atr_period = int(parameters.get("atrPeriod", 10))
        multiplier = float(parameters.get("multiplier", 3))
        return compute_supertrend(bars, atr_period, multiplier)
    if definition_id == "ich":
        tenkan_p = int(parameters.get("tenkanPeriod", 9))
        kijun_p = int(parameters.get("kijunPeriod", 26))
        senkou_b = int(parameters.get("senkouBPeriod", 52))
        disp = int(parameters.get("displacement", 26))
        tenkan, kijun, span_a, span_b, chikou = compute_ichimoku(
            bars, tenkan_p, kijun_p, senkou_b, disp
        )
        if line == "kijun":
            return kijun
        if line in ("spanA", "span_a"):
            return span_a
        if line in ("spanB", "span_b"):
            return span_b
        if line == "chikou":
            return chikou
        return tenkan
    return None


def build_indicator_context(
    bars: list[OhlcvBar],
    indicator_specs: list[dict[str, Any]],
) -> dict[str, list[float | None]]:
    """Construye ``indicator_context``."""
    if not indicator_specs:
        return {}
    closes = [bar.close for bar in bars]
    context: dict[str, list[float | None]] = {}
    for spec in indicator_specs:
        key = _spec_key(spec)
        definition_id = str(spec.get("definitionId") or "")
        parameters = dict(spec.get("parameters") or {})
        series = _series_for_spec(bars, closes, definition_id, parameters)
        if series is not None:
            context[key] = series
    return context


def _value_at(
    context: dict[str, list[float | None]], spec: dict[str, Any], index: int
) -> float | None:
    series = context.get(_spec_key(spec))
    if series is None or index >= len(series):
        return None
    return series[index]


def _compare(left: float, operator: RuleOperator, right: float) -> bool:
    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    return left == right


def _detect_cross(
    left: list[float | None],
    right: list[float | None],
    index: int,
    direction: Literal["bullish", "bearish"],
) -> bool:
    if index < 1:
        return False
    prev_left = left[index - 1]
    prev_right = right[index - 1]
    curr_left = left[index]
    curr_right = right[index]
    if None in (prev_left, prev_right, curr_left, curr_right):
        return False
    if direction == "bullish":
        return prev_left <= prev_right and curr_left > curr_right
    return prev_left >= prev_right and curr_left < curr_right


def evaluate_rule(
    rule: dict[str, Any],
    *,
    index: int,
    context: dict[str, list[float | None]],
    closes: list[float],
) -> SignalKind | None:
    """Evalúa ``rule``."""
    rule_type = rule.get("type")
    signal_kind = rule.get("signalKind")
    if signal_kind not in ("entry_long", "entry_short", "exit"):
        return None

    if rule_type == "indicator_cross":
        left_spec = rule.get("leftSpec") or {}
        right_spec = rule.get("rightSpec") or {}
        direction = rule.get("direction")
        if direction not in ("bullish", "bearish"):
            return None
        left_key = _spec_key(left_spec)
        right_key = _spec_key(right_spec)
        left_series = context.get(left_key)
        right_series = context.get(right_key)
        if left_series is None or right_series is None:
            return None
        if _detect_cross(left_series, right_series, index, direction):
            return signal_kind  # type: ignore[return-value]
        return None

    if rule_type == "indicator_compare":
        left_spec = rule.get("leftSpec") or {}
        operator = rule.get("operator")
        if operator not in ("lt", "lte", "gt", "gte", "eq"):
            return None
        try:
            right_value = float(rule.get("rightValue"))
        except (TypeError, ValueError):
            return None
        left_value = _value_at(context, left_spec, index)
        if left_value is None:
            return None
        if _compare(left_value, operator, right_value):
            return signal_kind  # type: ignore[return-value]
        return None

    if rule_type == "price_vs_indicator":
        indicator_spec = rule.get("indicatorSpec") or {}
        operator = rule.get("operator")
        if operator not in ("lt", "lte", "gt", "gte", "eq"):
            return None
        indicator_value = _value_at(context, indicator_spec, index)
        if indicator_value is None:
            return None
        price = closes[index]
        if _compare(price, operator, indicator_value):
            return signal_kind  # type: ignore[return-value]
        return None

    if rule_type == "indicator_vs_indicator":
        left_spec = rule.get("leftSpec") or {}
        right_spec = rule.get("rightSpec") or {}
        operator = rule.get("operator")
        if operator not in ("lt", "lte", "gt", "gte", "eq"):
            return None
        left_value = _value_at(context, left_spec, index)
        right_value = _value_at(context, right_spec, index)
        if left_value is None or right_value is None:
            return None
        if _compare(left_value, operator, right_value):
            return signal_kind  # type: ignore[return-value]
        return None

    if rule_type == "price_compare":
        operator = rule.get("operator")
        if operator not in ("lt", "lte", "gt", "gte", "eq"):
            return None
        try:
            target = float(rule.get("value"))
        except (TypeError, ValueError):
            return None
        price = closes[index]
        if _compare(price, operator, target):
            return signal_kind  # type: ignore[return-value]
        return None

    return None


def _spec_label(spec: dict[str, Any]) -> str:
    definition_id = str(spec.get("definitionId") or "?")
    params = spec.get("parameters") or {}
    if not isinstance(params, dict) or not params:
        return definition_id
    bits: list[str] = []
    for key in ("period", "fastPeriod", "slowPeriod", "signalPeriod", "line", "stdDev"):
        if key in params:
            bits.append(f"{key}={params[key]}")
    return f"{definition_id}({', '.join(bits)})" if bits else definition_id


def _operator_label(operator: str) -> str:
    return {
        "lt": "<",
        "lte": "≤",
        "gt": ">",
        "gte": "≥",
        "eq": "=",
    }.get(operator, operator)


def explain_rule(
    rule: dict[str, Any],
    *,
    index: int,
    context: dict[str, list[float | None]],
    closes: list[float],
) -> dict[str, Any] | None:
    """Human-readable snapshot of a rule that fired at `index` (None if not fired)."""
    if evaluate_rule(rule, index=index, context=context, closes=closes) is None:
        return None

    rule_type = str(rule.get("type") or "")
    signal_kind = str(rule.get("signalKind") or "")
    detail: dict[str, Any] = {
        "type": rule_type,
        "signalKind": signal_kind,
    }
    summary = rule_type

    if rule_type == "indicator_cross":
        left_spec = rule.get("leftSpec") or {}
        right_spec = rule.get("rightSpec") or {}
        direction = str(rule.get("direction") or "")
        left_val = _value_at(context, left_spec, index)
        right_val = _value_at(context, right_spec, index)
        left_label = _spec_label(left_spec if isinstance(left_spec, dict) else {})
        right_label = _spec_label(right_spec if isinstance(right_spec, dict) else {})
        detail.update(
            {
                "direction": direction,
                "left": left_label,
                "right": right_label,
                "leftValue": left_val,
                "rightValue": right_val,
            }
        )
        verb = "cruzó al alza" if direction == "bullish" else "cruzó a la baja"
        summary = f"{left_label} {verb} {right_label}"
        if left_val is not None and right_val is not None:
            summary += f" ({left_val:.4g} vs {right_val:.4g})"

    elif rule_type == "indicator_compare":
        left_spec = rule.get("leftSpec") or {}
        operator = str(rule.get("operator") or "")
        right_value = rule.get("rightValue")
        left_val = _value_at(context, left_spec, index)
        left_label = _spec_label(left_spec if isinstance(left_spec, dict) else {})
        detail.update(
            {
                "left": left_label,
                "operator": operator,
                "rightValue": right_value,
                "leftValue": left_val,
            }
        )
        summary = f"{left_label} {_operator_label(operator)} {right_value}"
        if left_val is not None:
            summary += f" (valor {left_val:.4g})"

    elif rule_type == "price_vs_indicator":
        indicator_spec = rule.get("indicatorSpec") or {}
        operator = str(rule.get("operator") or "")
        ind_val = _value_at(context, indicator_spec, index)
        ind_label = _spec_label(indicator_spec if isinstance(indicator_spec, dict) else {})
        price = closes[index]
        detail.update(
            {
                "operator": operator,
                "indicator": ind_label,
                "indicatorValue": ind_val,
                "price": price,
            }
        )
        summary = f"precio {_operator_label(operator)} {ind_label}"
        if ind_val is not None:
            summary += f" ({price:.4g} vs {ind_val:.4g})"

    elif rule_type == "indicator_vs_indicator":
        left_spec = rule.get("leftSpec") or {}
        right_spec = rule.get("rightSpec") or {}
        operator = str(rule.get("operator") or "")
        left_val = _value_at(context, left_spec, index)
        right_val = _value_at(context, right_spec, index)
        left_label = _spec_label(left_spec if isinstance(left_spec, dict) else {})
        right_label = _spec_label(right_spec if isinstance(right_spec, dict) else {})
        detail.update(
            {
                "left": left_label,
                "right": right_label,
                "operator": operator,
                "leftValue": left_val,
                "rightValue": right_val,
            }
        )
        summary = f"{left_label} {_operator_label(operator)} {right_label}"
        if left_val is not None and right_val is not None:
            summary += f" ({left_val:.4g} vs {right_val:.4g})"

    elif rule_type == "price_compare":
        operator = str(rule.get("operator") or "")
        target = rule.get("value")
        price = closes[index]
        detail.update({"operator": operator, "value": target, "price": price})
        summary = f"precio {_operator_label(operator)} {target} ({price:.4g})"

    detail["summary"] = summary
    return detail


def explain_signal_at_bar(
    definition: dict[str, Any],
    *,
    index: int,
    context: dict[str, list[float | None]],
    closes: list[float],
    side: Literal["entries", "exits"],
) -> dict[str, Any] | None:
    """Explain why entries/exits fired at bar index (for trade rationale UI)."""
    resolved = enrich_definition_with_preset_rules(definition)
    group = resolved.get(side) or {}
    if not isinstance(group, dict):
        return None
    kind = evaluate_rule_group(group, index=index, context=context, closes=closes)
    if kind is None:
        return None

    rules = group.get("rules") or []
    fired: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        explained = explain_rule(rule, index=index, context=context, closes=closes)
        if explained is not None:
            fired.append(explained)

    preset_key = resolved.get("presetKey")
    action = "entrada long" if kind == "entry_long" else ("salida" if kind == "exit" else str(kind))
    if fired:
        summary = f"{action}: " + "; ".join(str(item.get("summary") or "") for item in fired)
    else:
        summary = f"{action} (preset {preset_key or 'custom'})"

    return {
        "summary": summary,
        "signalKind": kind,
        "side": side,
        "presetKey": preset_key,
        "price": closes[index],
        "barIndex": index,
        "rules": fired,
    }


def evaluate_rule_group(
    group: dict[str, Any],
    *,
    index: int,
    context: dict[str, list[float | None]],
    closes: list[float],
) -> SignalKind | None:
    """Evalúa ``rule_group``."""
    rules = group.get("rules") or []
    if not rules:
        return None
    operator = group.get("operator", "all")

    if operator == "all":
        kinds: list[SignalKind] = []
        for rule in rules:
            kind = evaluate_rule(rule, index=index, context=context, closes=closes)
            if kind is None:
                return None
            kinds.append(kind)
        return kinds[0] if kinds else None

    for rule in rules:
        kind = evaluate_rule(rule, index=index, context=context, closes=closes)
        if kind is not None:
            return kind
    return None


def rule_group_passes_at_index(
    group: dict[str, Any],
    *,
    index: int,
    context: dict[str, list[float | None]],
    closes: list[float],
) -> bool:
    """Función pública ``rule_group_passes_at_index``."""
    rules = group.get("rules") or []
    if not rules:
        return True
    return evaluate_rule_group(group, index=index, context=context, closes=closes) is not None


def compute_rule_group_pass_series(
    bars: list[OhlcvBar],
    group: dict[str, Any],
    indicator_specs: list[dict[str, Any]],
) -> list[float | None]:
    """100 = gate abierto, 0 = cerrado."""
    rules = group.get("rules") or []
    if not rules:
        return [100.0 for _ in bars]
    context = build_indicator_context(bars, indicator_specs)
    closes = [bar.close for bar in bars]
    out: list[float | None] = []
    for index in range(len(bars)):
        passed = rule_group_passes_at_index(
            group,
            index=index,
            context=context,
            closes=closes,
        )
        out.append(100.0 if passed else 0.0)
    return out


def evaluate_rules_bar(
    definition: dict[str, Any],
    *,
    index: int,
    context: dict[str, list[float | None]],
    closes: list[float],
    side: Literal["entries", "exits"],
) -> SignalKind | None:
    """Evalúa ``rules_bar``."""
    group = definition.get(side) or {}
    return evaluate_rule_group(group, index=index, context=context, closes=closes)


def evaluate_rules_signals(
    definition: dict[str, Any],
    timestamps: list[str],
    closes: list[float],
    *,
    mode: Literal["raw", "gated"] = "raw",
    sides: tuple[Literal["entries", "exits"], ...] = ("entries", "exits"),
    assume_long: bool = False,
    context: dict[str, list[float | None]] | None = None,
) -> list[SignalEvent]:
    """Evalúa ``rules_signals``."""
    if len(timestamps) != len(closes):
        raise ValueError("timestamps and closes length mismatch")

    resolved = enrich_definition_with_preset_rules(definition)
    if not rule_group_has_rules(resolved.get("entries")) and not rule_group_has_rules(
        resolved.get("exits")
    ):
        raise ValueError("StrategyDefinitionV1 has no rules in entries or exits")

    bars = [
        OhlcvBar(timestamp=ts, open=close, high=close, low=close, close=close, volume=0.0)
        for ts, close in zip(timestamps, closes, strict=True)
    ]
    specs = resolved.get("indicatorSpecs") or []
    resolved_context = context or build_indicator_context(bars, specs)

    preset_key: str | None = resolved.get("presetKey")

    events: list[SignalEvent] = []
    has_long = assume_long

    for index, timestamp in enumerate(timestamps):
        entry_kind = (
            evaluate_rules_bar(
                resolved, index=index, context=resolved_context, closes=closes, side="entries"
            )
            if "entries" in sides
            else None
        )
        exit_kind = (
            evaluate_rules_bar(
                resolved, index=index, context=resolved_context, closes=closes, side="exits"
            )
            if "exits" in sides
            else None
        )

        if mode == "gated":
            if entry_kind == "entry_long" and not has_long:
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
            elif exit_kind == "exit" and has_long:
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
            continue

        for kind in (entry_kind, exit_kind):
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


def evaluate_exit_last_bar_gated(
    definition: dict[str, Any],
    timestamps: list[str],
    closes: list[float],
) -> SignalEvent | None:
    """Evalúa reglas de salida solo en la última barra — posición ya abierta (P7)."""
    if not timestamps:
        return None

    resolved = enrich_definition_with_preset_rules(definition)
    if not rule_group_has_rules(resolved.get("exits")):
        return None

    bars = [
        OhlcvBar(timestamp=ts, open=close, high=close, low=close, close=close, volume=0.0)
        for ts, close in zip(timestamps, closes, strict=True)
    ]
    context = build_indicator_context(bars, resolved.get("indicatorSpecs") or [])
    last_index = len(timestamps) - 1
    exit_kind = evaluate_rules_bar(
        resolved,
        index=last_index,
        context=context,
        closes=closes,
        side="exits",
    )
    if exit_kind != "exit":
        return None

    preset_key: str | None = resolved.get("presetKey")
    return SignalEvent(
        kind="exit",
        bar_index=last_index,
        timestamp=timestamps[last_index],
        price=closes[last_index],
        preset_key=preset_key,
    )
