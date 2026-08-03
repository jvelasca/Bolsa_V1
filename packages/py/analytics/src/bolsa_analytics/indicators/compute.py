"""Multi-spec indicator compute — paridad con chart TS (indicator-compute.ts)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

STYLE_PARAMETER_IDS = frozenset({"color"})


@dataclass(frozen=True, slots=True)
class OhlcvBar:
    """Barra OHLCV / input: Ohlcv Bar."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class IndicatorSpecInput:
    """Especificación / input: Indicator Spec Input."""
    definition_id: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LinePoint:
    """Serie / evento: Line Point."""
    timestamp: str
    value: float


@dataclass(frozen=True, slots=True)
class ComputedLine:
    """Tipo analytics: Computed Line."""
    key: str
    points: list[LinePoint]


@dataclass(frozen=True, slots=True)
class ComputedSpecResult:
    """Resultado: Computed Spec Result."""
    definition_id: str
    parameters: dict[str, Any]
    spec_key: str
    lines: list[ComputedLine]


def parameters_key(parameters: dict[str, Any]) -> str:
    """Helper: ``parameters_key``."""
    entries = sorted(parameters.items(), key=lambda item: item[0])
    if not entries:
        return "default"
    return "|".join(f"{key}={value}" for key, value in entries)


def data_parameters_key(parameters: dict[str, Any]) -> str:
    """Helper: ``data_parameters_key``."""
    entries = sorted(
        (key, value) for key, value in parameters.items() if key not in STYLE_PARAMETER_IDS
    )
    if not entries:
        return "default"
    return "|".join(f"{key}={value}" for key, value in entries)


def instance_spec_key(definition_id: str, parameters: dict[str, Any]) -> str:
    """Helper: ``instance_spec_key``."""
    return f"{definition_id}::{parameters_key(parameters)}"


def _param_num(parameters: dict[str, Any], key: str, default: float) -> float | None:
    raw = parameters.get(key, default)
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    return num


def _series_from_values(bars: list[OhlcvBar], values: list[float | None]) -> list[LinePoint]:
    points: list[LinePoint] = []
    for index, bar in enumerate(bars):
        if index >= len(values):
            break
        value = values[index]
        if value is None or not math.isfinite(value):
            continue
        points.append(LinePoint(timestamp=bar.timestamp, value=value))
    return points


def compute_sma(closes: list[float], period: int) -> list[float | None]:
    """Calcula serie/indicador ``sma``."""
    result: list[float | None] = []
    for index in range(len(closes)):
        if index + 1 < period:
            result.append(None)
            continue
        window = closes[index - period + 1 : index + 1]
        result.append(sum(window) / period)
    return result


def compute_ema(closes: list[float], period: int) -> list[float | None]:
    """Calcula serie/indicador ``ema``."""
    result: list[float | None] = []
    smoothing = 2 / (period + 1)
    ema: float | None = None
    for index in range(len(closes)):
        close = closes[index]
        if index + 1 < period:
            result.append(None)
            continue
        if ema is None:
            seed = sum(closes[index - period + 1 : index + 1]) / period
            ema = seed
            result.append(seed)
            continue
        ema = close * smoothing + ema * (1 - smoothing)
        result.append(ema)
    return result


def compute_wma(closes: list[float], period: int) -> list[float | None]:
    """Calcula serie/indicador ``wma``."""
    result: list[float | None] = []
    denominator = (period * (period + 1)) / 2
    for index in range(len(closes)):
        if index + 1 < period:
            result.append(None)
            continue
        total = 0.0
        for weight in range(1, period + 1):
            total += closes[index - period + weight] * weight
        result.append(total / denominator)
    return result


def compute_rsi(closes: list[float], period: int) -> list[float | None]:
    """Calcula serie/indicador ``rsi``."""
    if not closes:
        return []
    result: list[float | None] = [None]
    avg_gain = 0.0
    avg_loss = 0.0
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0
        if index < period:
            avg_gain += gain
            avg_loss += loss
            result.append(None)
            continue
        if index == period:
            avg_gain = (avg_gain + gain) / period
            avg_loss = (avg_loss + loss) / period
        else:
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            result.append(100 - 100 / (1 + avg_gain / avg_loss))
    return result


def compute_atr(bars: list[OhlcvBar], period: int) -> list[float | None]:
    """Calcula serie/indicador ``atr``."""
    result: list[float | None] = []
    atr: float | None = None
    for index in range(len(bars)):
        bar = bars[index]
        prev = bars[index - 1] if index > 0 else None
        if prev is None:
            true_range = bar.high - bar.low
        else:
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - prev.close),
                abs(bar.low - prev.close),
            )
        if index + 1 < period:
            result.append(None)
            continue
        if atr is None:
            total = 0.0
            for j in range(index - period + 1, index + 1):
                b = bars[j]
                p = bars[j - 1] if j > 0 else None
                if p is None:
                    tr = b.high - b.low
                else:
                    tr = max(
                        b.high - b.low,
                        abs(b.high - p.close),
                        abs(b.low - p.close),
                    )
                total += tr
            atr = total / period
        else:
            atr = (atr * (period - 1) + true_range) / period
        result.append(atr)
    return result


def compute_cci(bars: list[OhlcvBar], period: int) -> list[float | None]:
    """Calcula serie/indicador ``cci``."""
    typical = [(bar.high + bar.low + bar.close) / 3 for bar in bars]
    result: list[float | None] = []
    for index in range(len(typical)):
        if index + 1 < period:
            result.append(None)
            continue
        window = typical[index - period + 1 : index + 1]
        mean = sum(window) / period
        mean_dev = sum(abs(value - mean) for value in window) / period
        if mean_dev == 0:
            result.append(0.0)
        else:
            result.append((typical[index] - mean) / (0.015 * mean_dev))
    return result


def compute_stoch_k(bars: list[OhlcvBar], k_period: int) -> list[float | None]:
    """Calcula serie/indicador ``stoch_k``."""
    result: list[float | None] = []
    for index in range(len(bars)):
        if index + 1 < k_period:
            result.append(None)
            continue
        window = bars[index - k_period + 1 : index + 1]
        low = min(bar.low for bar in window)
        high = max(bar.high for bar in window)
        close = bars[index].close
        if high == low:
            result.append(50.0)
        else:
            result.append(((close - low) / (high - low)) * 100)
    return result


def compute_macd_line(closes: list[float], fast: int, slow: int) -> list[float | None]:
    """Calcula serie/indicador ``macd_line``."""
    fast_ema = compute_ema(closes, fast)
    slow_ema = compute_ema(closes, slow)
    result: list[float | None] = []
    for fast_value, slow_value in zip(fast_ema, slow_ema, strict=False):
        if fast_value is None or slow_value is None:
            result.append(None)
        else:
            result.append(fast_value - slow_value)
    return result


def compute_macd_signal_line(
    closes: list[float],
    fast: int,
    slow: int,
    signal_period: int,
) -> list[float | None]:
    """MACD signal = EMA of MACD line with classic warm-up (no None→0 seed).

    TradingView / classic: wait until MACD is valid, then seed signal EMA on the
    first ``signal_period`` MACD values. Earlier bars stay ``None``.
    """
    return compute_macd_signal_from_line(
        compute_macd_line(closes, fast, slow),
        signal_period,
    )


def compute_macd_signal_from_line(
    macd_line: list[float | None],
    signal_period: int,
) -> list[float | None]:
    """EMA of a (possibly leading-None) MACD line — classic seed, no zero-fill."""
    n = len(macd_line)
    result: list[float | None] = [None] * n
    if signal_period < 1 or n == 0:
        return result
    first = next((i for i, value in enumerate(macd_line) if value is not None), None)
    if first is None:
        return result
    dense: list[float] = []
    for value in macd_line[first:]:
        if value is None:
            break
        dense.append(float(value))
    if len(dense) < signal_period:
        return result
    ema_dense = compute_ema(dense, signal_period)
    for offset, value in enumerate(ema_dense):
        result[first + offset] = value
    return result


def compute_bollinger(
    closes: list[float],
    period: int,
    std_dev: float,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Calcula serie/indicador ``bollinger``."""
    mid = compute_sma(closes, period)
    upper: list[float | None] = []
    lower: list[float | None] = []
    for index in range(len(closes)):
        center = mid[index]
        if center is None or index + 1 < period:
            upper.append(None)
            lower.append(None)
            continue
        window = closes[index - period + 1 : index + 1]
        variance = sum((value - center) ** 2 for value in window) / period
        sd = math.sqrt(variance)
        upper.append(center + std_dev * sd)
        lower.append(center - std_dev * sd)
    return mid, upper, lower


def compute_williams_r(bars: list[OhlcvBar], period: int) -> list[float | None]:
    """Williams %R = -100 * (HH - Close) / (HH - LL)."""
    result: list[float | None] = []
    for index in range(len(bars)):
        if index + 1 < period:
            result.append(None)
            continue
        window = bars[index - period + 1 : index + 1]
        highest = max(bar.high for bar in window)
        lowest = min(bar.low for bar in window)
        denom = highest - lowest
        if denom <= 0:
            result.append(None)
            continue
        result.append(-100.0 * (highest - bars[index].close) / denom)
    return result


def compute_momentum(closes: list[float], period: int) -> list[float | None]:
    """Momentum = Close(t) - Close(t - period)."""
    result: list[float | None] = []
    for index in range(len(closes)):
        if index < period:
            result.append(None)
            continue
        result.append(closes[index] - closes[index - period])
    return result


def compute_std_dev(closes: list[float], period: int) -> list[float | None]:
    """Rolling population stddev of close (misma convención que BB mid window)."""
    result: list[float | None] = []
    for index in range(len(closes)):
        if index + 1 < period:
            result.append(None)
            continue
        window = closes[index - period + 1 : index + 1]
        mean = sum(window) / period
        variance = sum((value - mean) ** 2 for value in window) / period
        result.append(math.sqrt(variance))
    return result


def compute_donchian(
    bars: list[OhlcvBar],
    period: int,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Donchian: upper=max(high), lower=min(low), mid=(upper+lower)/2."""
    upper: list[float | None] = []
    lower: list[float | None] = []
    mid: list[float | None] = []
    for index in range(len(bars)):
        if index + 1 < period:
            upper.append(None)
            lower.append(None)
            mid.append(None)
            continue
        window = bars[index - period + 1 : index + 1]
        hi = max(bar.high for bar in window)
        lo = min(bar.low for bar in window)
        upper.append(hi)
        lower.append(lo)
        mid.append((hi + lo) / 2.0)
    return upper, mid, lower


def _wilder_smooth(values: list[float], period: int) -> list[float | None]:
    """Wilder smoothing: first = SMA, then prev - prev/period + value."""
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    prev = seed
    for index in range(period, len(values)):
        prev = prev - prev / period + values[index]
        result[index] = prev
    return result


def compute_adx(
    bars: list[OhlcvBar],
    period: int,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """ADX, +DI, −DI (Wilder)."""
    n = len(bars)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for index in range(n):
        bar = bars[index]
        if index == 0:
            tr[index] = bar.high - bar.low
            continue
        prev = bars[index - 1]
        up_move = bar.high - prev.high
        down_move = prev.low - bar.low
        plus_dm[index] = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm[index] = down_move if down_move > up_move and down_move > 0 else 0.0
        tr[index] = max(
            bar.high - bar.low,
            abs(bar.high - prev.close),
            abs(bar.low - prev.close),
        )

    smooth_tr = _wilder_smooth(tr, period)
    smooth_plus = _wilder_smooth(plus_dm, period)
    smooth_minus = _wilder_smooth(minus_dm, period)

    plus_di: list[float | None] = [None] * n
    minus_di: list[float | None] = [None] * n
    dx: list[float | None] = [None] * n
    for index in range(n):
        str_v = smooth_tr[index]
        sp = smooth_plus[index]
        sm = smooth_minus[index]
        if str_v is None or sp is None or sm is None or str_v == 0:
            continue
        pdi = 100.0 * sp / str_v
        mdi = 100.0 * sm / str_v
        plus_di[index] = pdi
        minus_di[index] = mdi
        denom = pdi + mdi
        dx[index] = 0.0 if denom == 0 else 100.0 * abs(pdi - mdi) / denom

    # ADX = Wilder smooth of DX starting when DX is available (index period-1)
    adx: list[float | None] = [None] * n
    first_dx = period - 1
    if n >= first_dx + period:
        seed_vals = [dx[i] for i in range(first_dx, first_dx + period) if dx[i] is not None]
        if len(seed_vals) == period:
            seed = sum(seed_vals) / period
            adx_index = first_dx + period - 1
            adx[adx_index] = seed
            prev = seed
            for index in range(adx_index + 1, n):
                cur = dx[index]
                if cur is None:
                    adx[index] = None
                    continue
                prev = (prev * (period - 1) + cur) / period
                adx[index] = prev
    return adx, plus_di, minus_di


def _sma_of_series(values: list[float | None], period: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < period:
            result.append(None)
            continue
        window = values[index - period + 1 : index + 1]
        if any(v is None for v in window):
            result.append(None)
            continue
        result.append(sum(v for v in window if v is not None) / period)
    return result


def compute_stoch_rsi(
    closes: list[float],
    rsi_period: int,
    stoch_period: int,
    k_period: int,
    d_period: int,
) -> tuple[list[float | None], list[float | None]]:
    """Stochastic RSI → %K, %D (0–100)."""
    rsi = compute_rsi(closes, rsi_period)
    raw: list[float | None] = []
    for index in range(len(rsi)):
        if index + 1 < stoch_period:
            raw.append(None)
            continue
        window = rsi[index - stoch_period + 1 : index + 1]
        if any(v is None for v in window):
            raw.append(None)
            continue
        vals = [v for v in window if v is not None]
        lo = min(vals)
        hi = max(vals)
        cur = rsi[index]
        if cur is None:
            raw.append(None)
        elif hi == lo:
            raw.append(50.0)
        else:
            raw.append(100.0 * (cur - lo) / (hi - lo))
    k_line = _sma_of_series(raw, k_period) if k_period > 1 else raw
    d_line = _sma_of_series(k_line, d_period)
    return k_line, d_line


def compute_supertrend(
    bars: list[OhlcvBar],
    atr_period: int,
    multiplier: float,
) -> list[float | None]:
    """SuperTrend line (ATR-based)."""
    atr = compute_atr(bars, atr_period)
    n = len(bars)
    result: list[float | None] = [None] * n
    final_ub: list[float | None] = [None] * n
    final_lb: list[float | None] = [None] * n
    trend = 1
    for index in range(n):
        atr_v = atr[index]
        if atr_v is None:
            continue
        hl2 = (bars[index].high + bars[index].low) / 2.0
        basic_ub = hl2 + multiplier * atr_v
        basic_lb = hl2 - multiplier * atr_v
        if index == 0 or final_ub[index - 1] is None:
            final_ub[index] = basic_ub
            final_lb[index] = basic_lb
        else:
            prev_ub = final_ub[index - 1]
            prev_lb = final_lb[index - 1]
            assert prev_ub is not None and prev_lb is not None
            prev_close = bars[index - 1].close
            final_ub[index] = (
                basic_ub if basic_ub < prev_ub or prev_close > prev_ub else prev_ub
            )
            final_lb[index] = (
                basic_lb if basic_lb > prev_lb or prev_close < prev_lb else prev_lb
            )

        cur_ub = final_ub[index]
        cur_lb = final_lb[index]
        assert cur_ub is not None and cur_lb is not None
        close = bars[index].close
        if index > 0 and final_ub[index - 1] is not None and close > final_ub[index - 1]:
            trend = 1
        elif index > 0 and final_lb[index - 1] is not None and close < final_lb[index - 1]:
            trend = -1
        result[index] = cur_lb if trend == 1 else cur_ub
    return result


def compute_vwap(bars: list[OhlcvBar]) -> list[float | None]:
    """Cumulative VWAP from series start (typical price × volume)."""
    result: list[float | None] = []
    cum_pv = 0.0
    cum_vol = 0.0
    for bar in bars:
        tp = (bar.high + bar.low + bar.close) / 3.0
        vol = float(bar.volume)
        if vol <= 0:
            result.append(None if cum_vol == 0 else cum_pv / cum_vol)
            continue
        cum_pv += tp * vol
        cum_vol += vol
        result.append(cum_pv / cum_vol)
    return result


def compute_obv(bars: list[OhlcvBar]) -> list[float | None]:
    """Calcula serie/indicador ``obv``."""
    result: list[float | None] = []
    obv = 0.0
    for index, bar in enumerate(bars):
        if index == 0:
            result.append(0.0)
            continue
        prev = bars[index - 1].close
        if bar.close > prev:
            obv += float(bar.volume)
        elif bar.close < prev:
            obv -= float(bar.volume)
        result.append(obv)
    return result


def compute_roc(closes: list[float], period: int) -> list[float | None]:
    """Calcula serie/indicador ``roc``."""
    result: list[float | None] = []
    for index, close in enumerate(closes):
        if index < period:
            result.append(None)
            continue
        prev = closes[index - period]
        if prev == 0:
            result.append(None)
        else:
            result.append(100.0 * (close - prev) / prev)
    return result


def compute_mfi(bars: list[OhlcvBar], period: int) -> list[float | None]:
    """Calcula serie/indicador ``mfi``."""
    result: list[float | None] = []
    typical = [(b.high + b.low + b.close) / 3.0 for b in bars]
    raw_mf = [typical[i] * float(bars[i].volume) for i in range(len(bars))]
    for index in range(len(bars)):
        if index < period:
            result.append(None)
            continue
        pos = 0.0
        neg = 0.0
        for j in range(index - period + 1, index + 1):
            if j == 0:
                continue
            if typical[j] > typical[j - 1]:
                pos += raw_mf[j]
            elif typical[j] < typical[j - 1]:
                neg += raw_mf[j]
        if neg == 0:
            result.append(100.0)
        else:
            result.append(100.0 - 100.0 / (1.0 + pos / neg))
    return result


def compute_aroon(
    bars: list[OhlcvBar],
    period: int,
) -> tuple[list[float | None], list[float | None]]:
    """Calcula serie/indicador ``aroon``."""
    up: list[float | None] = []
    down: list[float | None] = []
    for index in range(len(bars)):
        if index + 1 < period:
            up.append(None)
            down.append(None)
            continue
        window = bars[index - period + 1 : index + 1]
        hi = max(b.high for b in window)
        lo = min(b.low for b in window)
        bars_since_high = 0
        bars_since_low = 0
        for offset, bar in enumerate(reversed(window)):
            if bar.high == hi:
                bars_since_high = offset
                break
        for offset, bar in enumerate(reversed(window)):
            if bar.low == lo:
                bars_since_low = offset
                break
        up.append(100.0 * (period - bars_since_high) / period)
        down.append(100.0 * (period - bars_since_low) / period)
    return up, down


def _smma(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    prev = seed
    for index in range(period, len(values)):
        prev = (prev * (period - 1) + values[index]) / period
        result[index] = prev
    return result


def compute_alligator(
    bars: list[OhlcvBar],
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Jaw(13/8), Teeth(8/5), Lips(5/3) on median price."""
    median = [(b.high + b.low) / 2.0 for b in bars]
    jaw_raw = _smma(median, 13)
    teeth_raw = _smma(median, 8)
    lips_raw = _smma(median, 5)
    n = len(bars)
    jaw: list[float | None] = [None] * n
    teeth: list[float | None] = [None] * n
    lips: list[float | None] = [None] * n
    for index in range(n):
        if index >= 8 and jaw_raw[index - 8] is not None:
            jaw[index] = jaw_raw[index - 8]
        if index >= 5 and teeth_raw[index - 5] is not None:
            teeth[index] = teeth_raw[index - 5]
        if index >= 3 and lips_raw[index - 3] is not None:
            lips[index] = lips_raw[index - 3]
    return jaw, teeth, lips


def compute_bears_power(bars: list[OhlcvBar], period: int) -> list[float | None]:
    """Calcula serie/indicador ``bears_power``."""
    ema = compute_ema([b.close for b in bars], period)
    return [
        None if ema[i] is None else bars[i].low - ema[i]  # type: ignore[operator]
        for i in range(len(bars))
    ]


def compute_bulls_power(bars: list[OhlcvBar], period: int) -> list[float | None]:
    """Calcula serie/indicador ``bulls_power``."""
    ema = compute_ema([b.close for b in bars], period)
    return [
        None if ema[i] is None else bars[i].high - ema[i]  # type: ignore[operator]
        for i in range(len(bars))
    ]


def compute_psar(
    bars: list[OhlcvBar],
    step: float = 0.02,
    max_af: float = 0.2,
) -> list[float | None]:
    """Calcula serie/indicador ``psar``."""
    n = len(bars)
    if n == 0:
        return []
    result: list[float | None] = [None] * n
    bull = True
    af = step
    ep = bars[0].high
    sar = bars[0].low
    result[0] = sar
    for index in range(1, n):
        prev_sar = sar
        sar = prev_sar + af * (ep - prev_sar)
        if bull:
            sar = min(sar, bars[index - 1].low)
            if index >= 2:
                sar = min(sar, bars[index - 2].low)
            if bars[index].low < sar:
                bull = False
                sar = ep
                ep = bars[index].low
                af = step
            else:
                if bars[index].high > ep:
                    ep = bars[index].high
                    af = min(af + step, max_af)
        else:
            sar = max(sar, bars[index - 1].high)
            if index >= 2:
                sar = max(sar, bars[index - 2].high)
            if bars[index].high > sar:
                bull = True
                sar = ep
                ep = bars[index].high
                af = step
            else:
                if bars[index].low < ep:
                    ep = bars[index].low
                    af = min(af + step, max_af)
        result[index] = sar
    return result


def compute_fractals(
    bars: list[OhlcvBar],
) -> tuple[list[float | None], list[float | None]]:
    """Williams 5-bar fractals centered at i-2."""
    n = len(bars)
    up: list[float | None] = [None] * n
    down: list[float | None] = [None] * n
    for index in range(2, n - 2):
        highs = [bars[j].high for j in range(index - 2, index + 3)]
        lows = [bars[j].low for j in range(index - 2, index + 3)]
        if bars[index].high == max(highs) and highs.count(bars[index].high) == 1:
            up[index] = bars[index].high
        if bars[index].low == min(lows) and lows.count(bars[index].low) == 1:
            down[index] = bars[index].low
    return up, down


def _midpoint_hl(bars: list[OhlcvBar], period: int, index: int) -> float | None:
    if index + 1 < period:
        return None
    window = bars[index - period + 1 : index + 1]
    return (max(b.high for b in window) + min(b.low for b in window)) / 2.0


def compute_ichimoku(
    bars: list[OhlcvBar],
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> tuple[
    list[float | None],
    list[float | None],
    list[float | None],
    list[float | None],
    list[float | None],
]:
    """Calcula serie/indicador ``ichimoku``."""
    n = len(bars)
    tenkan: list[float | None] = [_midpoint_hl(bars, tenkan_period, i) for i in range(n)]
    kijun: list[float | None] = [_midpoint_hl(bars, kijun_period, i) for i in range(n)]
    span_b_raw: list[float | None] = [_midpoint_hl(bars, senkou_b_period, i) for i in range(n)]
    span_a: list[float | None] = [None] * n
    span_b: list[float | None] = [None] * n
    chikou: list[float | None] = [None] * n
    for index in range(n):
        src = index - displacement
        if src >= 0:
            t = tenkan[src]
            k = kijun[src]
            if t is not None and k is not None:
                span_a[index] = (t + k) / 2.0
            span_b[index] = span_b_raw[src]
        ahead = index + displacement
        if ahead < n:
            chikou[index] = bars[ahead].close
    return tenkan, kijun, span_a, span_b, chikou


def compute_spec(bars: list[OhlcvBar], spec: IndicatorSpecInput) -> ComputedSpecResult:
    """Calcula serie/indicador ``spec``."""
    definition_id = spec.definition_id
    parameters = dict(spec.parameters)
    spec_key = instance_spec_key(definition_id, parameters)
    closes = [bar.close for bar in bars]
    lines: list[ComputedLine] = []

    if definition_id == "sma":
        period = _param_num(parameters, "period", 20)
        if period is not None:
            values = compute_sma(closes, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "ema":
        period = _param_num(parameters, "period", 20)
        if period is not None:
            values = compute_ema(closes, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "wma":
        period = _param_num(parameters, "period", 20)
        if period is not None:
            values = compute_wma(closes, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "rsi":
        period = _param_num(parameters, "period", 14)
        if period is not None:
            values = compute_rsi(closes, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "atr":
        period = _param_num(parameters, "period", 14)
        if period is not None:
            values = compute_atr(bars, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "cci":
        period = _param_num(parameters, "period", 20)
        if period is not None:
            values = compute_cci(bars, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "stoch":
        k_period = _param_num(parameters, "kPeriod", 14)
        if k_period is not None:
            values = compute_stoch_k(bars, int(k_period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "macd":
        fast = _param_num(parameters, "fastPeriod", 12)
        slow = _param_num(parameters, "slowPeriod", 26)
        if fast is not None and slow is not None:
            values = compute_macd_line(closes, int(fast), int(slow))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "bb":
        period = _param_num(parameters, "period", 20)
        std_dev = _param_num(parameters, "stdDev", 2)
        if period is not None and std_dev is not None:
            mid, upper, lower = compute_bollinger(closes, int(period), std_dev)
            lines.extend(
                [
                    ComputedLine(key="upper", points=_series_from_values(bars, upper)),
                    ComputedLine(key="mid", points=_series_from_values(bars, mid)),
                    ComputedLine(key="lower", points=_series_from_values(bars, lower)),
                ],
            )
    elif definition_id == "willr":
        period = _param_num(parameters, "period", 14)
        if period is not None:
            values = compute_williams_r(bars, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "mom":
        period = _param_num(parameters, "period", 10)
        if period is not None:
            values = compute_momentum(closes, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "sd":
        period = _param_num(parameters, "period", 20)
        if period is not None:
            values = compute_std_dev(closes, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "dc":
        period = _param_num(parameters, "period", 20)
        if period is not None:
            upper, mid, lower = compute_donchian(bars, int(period))
            lines.extend(
                [
                    ComputedLine(key="upper", points=_series_from_values(bars, upper)),
                    ComputedLine(key="mid", points=_series_from_values(bars, mid)),
                    ComputedLine(key="lower", points=_series_from_values(bars, lower)),
                ],
            )
    elif definition_id == "adx":
        period = _param_num(parameters, "period", 14)
        if period is not None:
            adx, plus_di, minus_di = compute_adx(bars, int(period))
            lines.extend(
                [
                    ComputedLine(key="main", points=_series_from_values(bars, adx)),
                    ComputedLine(key="plus_di", points=_series_from_values(bars, plus_di)),
                    ComputedLine(key="minus_di", points=_series_from_values(bars, minus_di)),
                ],
            )
    elif definition_id == "srsi":
        rsi_period = _param_num(parameters, "rsiPeriod", 14)
        stoch_period = _param_num(parameters, "stochPeriod", 14)
        k_period = _param_num(parameters, "kPeriod", 3)
        d_period = _param_num(parameters, "dPeriod", 3)
        if None not in (rsi_period, stoch_period, k_period, d_period):
            k_line, d_line = compute_stoch_rsi(
                closes,
                int(rsi_period),
                int(stoch_period),
                int(k_period),
                int(d_period),
            )
            lines.extend(
                [
                    ComputedLine(key="main", points=_series_from_values(bars, k_line)),
                    ComputedLine(key="signal", points=_series_from_values(bars, d_line)),
                ],
            )
    elif definition_id == "st":
        atr_period = _param_num(parameters, "atrPeriod", 10)
        multiplier = _param_num(parameters, "multiplier", 3)
        if atr_period is not None and multiplier is not None:
            values = compute_supertrend(bars, int(atr_period), float(multiplier))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "vwap":
        values = compute_vwap(bars)
        lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "obv":
        values = compute_obv(bars)
        lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "roc":
        period = _param_num(parameters, "period", 12)
        if period is not None:
            values = compute_roc(closes, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "mfi":
        period = _param_num(parameters, "period", 14)
        if period is not None:
            values = compute_mfi(bars, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "aroon":
        period = _param_num(parameters, "period", 25)
        if period is not None:
            up, down = compute_aroon(bars, int(period))
            lines.extend(
                [
                    ComputedLine(key="up", points=_series_from_values(bars, up)),
                    ComputedLine(key="down", points=_series_from_values(bars, down)),
                ],
            )
    elif definition_id == "sar":
        step = _param_num(parameters, "step", 0.02)
        max_af = _param_num(parameters, "maxAf", 0.2)
        if step is not None and max_af is not None:
            values = compute_psar(bars, float(step), float(max_af))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "bears":
        period = _param_num(parameters, "period", 13)
        if period is not None:
            values = compute_bears_power(bars, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "bulls":
        period = _param_num(parameters, "period", 13)
        if period is not None:
            values = compute_bulls_power(bars, int(period))
            lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "ali":
        jaw, teeth, lips = compute_alligator(bars)
        lines.extend(
            [
                ComputedLine(key="jaw", points=_series_from_values(bars, jaw)),
                ComputedLine(key="teeth", points=_series_from_values(bars, teeth)),
                ComputedLine(key="lips", points=_series_from_values(bars, lips)),
            ],
        )
    elif definition_id == "fr":
        up, down = compute_fractals(bars)
        lines.extend(
            [
                ComputedLine(key="up", points=_series_from_values(bars, up)),
                ComputedLine(key="down", points=_series_from_values(bars, down)),
            ],
        )
    elif definition_id == "ich":
        tenkan_p = int(_param_num(parameters, "tenkanPeriod", 9) or 9)
        kijun_p = int(_param_num(parameters, "kijunPeriod", 26) or 26)
        senkou_b = int(_param_num(parameters, "senkouBPeriod", 52) or 52)
        disp = int(_param_num(parameters, "displacement", 26) or 26)
        tenkan, kijun, span_a, span_b, chikou = compute_ichimoku(
            bars,
            tenkan_p,
            kijun_p,
            senkou_b,
            disp,
        )
        lines.extend(
            [
                ComputedLine(key="tenkan", points=_series_from_values(bars, tenkan)),
                ComputedLine(key="kijun", points=_series_from_values(bars, kijun)),
                ComputedLine(key="spanA", points=_series_from_values(bars, span_a)),
                ComputedLine(key="spanB", points=_series_from_values(bars, span_b)),
                ComputedLine(key="chikou", points=_series_from_values(bars, chikou)),
            ],
        )
    elif definition_id == "volume":
        lines.append(
            ComputedLine(
                key="main",
                points=[
                    LinePoint(timestamp=bar.timestamp, value=bar.volume)
                    for bar in bars
                    if bar.volume > 0
                ],
            ),
        )
    elif definition_id == "technical_rating_v1":
        from bolsa_analytics.signals.technical_rating_v1 import compute_technical_rating_series_v1

        warmup = int(_param_num(parameters, "warmupBars", 50) or 50)
        values = compute_technical_rating_series_v1(bars, warmup=warmup)
        lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "bar_data_quality_v1":
        from bolsa_analytics.signals.data_quality_v1 import compute_bar_data_quality_series_v1

        gap_lookback = int(_param_num(parameters, "gapLookback", 90) or 90)
        values = compute_bar_data_quality_series_v1(bars, gap_lookback=gap_lookback)
        lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
    elif definition_id == "ai_global_score_v1":
        from bolsa_analytics.signals.data_quality_v1 import compute_bar_data_quality_series_v1
        from bolsa_analytics.signals.technical_rating_v1 import compute_technical_rating_series_v1

        warmup = int(_param_num(parameters, "warmupBars", 50) or 50)
        setup_weight = float(_param_num(parameters, "setupWeight", 70) or 70)
        data_weight = float(_param_num(parameters, "dataWeight", 30) or 30)
        total_weight = setup_weight + data_weight
        setup_ratio = setup_weight / total_weight if total_weight > 0 else 0.7
        data_ratio = data_weight / total_weight if total_weight > 0 else 0.3
        setup_values = compute_technical_rating_series_v1(bars, warmup=warmup)
        data_values = compute_bar_data_quality_series_v1(bars)
        combined: list[float | None] = []
        for setup, data in zip(setup_values, data_values, strict=False):
            if setup is None or data is None:
                combined.append(None)
            else:
                combined.append(max(0.0, min(100.0, setup * setup_ratio + data * data_ratio)))
        lines.append(ComputedLine(key="main", points=_series_from_values(bars, combined)))
    elif definition_id == "strategy_hybrid_score_v1":
        from bolsa_analytics.signals.preset_catalog import (
            preset_indicator_specs,
            preset_rule_groups,
        )
        from bolsa_analytics.signals.rules_engine import compute_rule_group_pass_series
        from bolsa_analytics.signals.technical_rating_v1 import compute_technical_rating_series_v1

        warmup = int(_param_num(parameters, "warmupBars", 50) or 50)
        values = compute_technical_rating_series_v1(bars, warmup=warmup)
        lines.append(ComputedLine(key="main", points=_series_from_values(bars, values)))
        show_min = parameters.get("showMinScoreLine", True)
        min_score = _param_num(parameters, "minScore", 60)
        if show_min is not False and min_score is not None:
            min_points = _series_from_values(
                bars,
                [float(min_score) if v is not None else None for v in values],
            )
            lines.append(ComputedLine(key="minScore", points=min_points))
        show_gate = parameters.get("showGateLine", True)
        gate_preset_key = str(parameters.get("gatePresetKey") or "").strip()
        if show_gate is not False and gate_preset_key:
            rule_groups = preset_rule_groups(gate_preset_key)
            gate_specs = preset_indicator_specs(gate_preset_key)
            gate_values = compute_rule_group_pass_series(
                bars,
                rule_groups.get("entries") or {},
                [dict(spec) for spec in gate_specs],
            )
            lines.append(ComputedLine(key="gate", points=_series_from_values(bars, gate_values)))
    else:
        raise ValueError(f"Unsupported indicator definitionId: {definition_id}")

    return ComputedSpecResult(
        definition_id=definition_id,
        parameters=parameters,
        spec_key=spec_key,
        lines=lines,
    )


def compute_specs(bars: list[OhlcvBar], specs: list[IndicatorSpecInput]) -> list[ComputedSpecResult]:
    """Calcula serie/indicador ``specs``."""
    return [compute_spec(bars, spec) for spec in specs]
