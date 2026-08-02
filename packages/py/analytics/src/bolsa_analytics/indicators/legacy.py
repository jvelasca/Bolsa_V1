from dataclasses import dataclass
from typing import Literal


def sma(values: list[float], period: int) -> list[float | None]:

    result: list[float | None] = []

    for i in range(len(values)):

        if i < period - 1:

            result.append(None)

            continue

        window = values[i - period + 1 : i + 1]

        result.append(sum(window) / period)

    return result





def ema(values: list[float], period: int) -> list[float | None]:

    result: list[float | None] = []

    k = 2 / (period + 1)

    prev_ema: float | None = None



    for i in range(len(values)):

        if i < period - 1:

            result.append(None)

            continue

        if prev_ema is None:

            seed = sum(values[:period]) / period

            prev_ema = seed

            result.append(seed)

            continue

        prev_ema = values[i] * k + prev_ema * (1 - k)

        result.append(prev_ema)



    return result





def rsi(values: list[float], period: int = 14) -> list[float | None]:

    if len(values) < period + 1:

        return [None] * len(values)



    result: list[float | None] = [None] * period

    avg_gain = 0.0

    avg_loss = 0.0



    for i in range(1, period + 1):

        change = values[i] - values[i - 1]

        if change >= 0:

            avg_gain += change

        else:

            avg_loss += abs(change)



    avg_gain /= period

    avg_loss /= period

    first_rsi = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)

    result.append(first_rsi)



    for i in range(period + 1, len(values)):

        change = values[i] - values[i - 1]

        gain = change if change > 0 else 0.0

        loss = abs(change) if change < 0 else 0.0

        avg_gain = (avg_gain * (period - 1) + gain) / period

        avg_loss = (avg_loss * (period - 1) + loss) / period

        rsi_value = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)

        result.append(rsi_value)



    return result





@dataclass(frozen=True, slots=True)

class IndicatorPoint:

    timestamp: str

    sma20: float | None

    sma50: float | None

    ema20: float | None

    rsi14: float | None





@dataclass(frozen=True, slots=True)

class IndicatorSignals:

    rsi_zone: Literal["overbought", "oversold", "neutral"]

    sma_cross: Literal["bullish", "bearish"] | None





def build_indicator_series(timestamps: list[str], closes: list[float]) -> list[IndicatorPoint]:

    sma20 = sma(closes, 20)

    sma50 = sma(closes, 50)

    ema20 = ema(closes, 20)

    rsi14 = rsi(closes, 14)



    return [

        IndicatorPoint(

            timestamp=timestamps[i],

            sma20=sma20[i],

            sma50=sma50[i],

            ema20=ema20[i],

            rsi14=rsi14[i],

        )

        for i in range(len(timestamps))

    ]





def latest_indicator_signals(points: list[IndicatorPoint]) -> IndicatorSignals:

    if len(points) < 2:

        return IndicatorSignals(rsi_zone="neutral", sma_cross=None)



    last = points[-1]

    prev = points[-2]



    rsi_zone: Literal["overbought", "oversold", "neutral"] = "neutral"

    if last.rsi14 is not None:

        if last.rsi14 >= 70:

            rsi_zone = "overbought"

        elif last.rsi14 <= 30:

            rsi_zone = "oversold"



    sma_cross: Literal["bullish", "bearish"] | None = None

    if (

        last.sma20 is not None

        and last.sma50 is not None

        and prev.sma20 is not None

        and prev.sma50 is not None

    ):

        was_below = prev.sma20 < prev.sma50

        is_above = last.sma20 > last.sma50

        if was_below and is_above:

            sma_cross = "bullish"

        if not was_below and not is_above and prev.sma20 > prev.sma50 and last.sma20 < last.sma50:

            sma_cross = "bearish"



    return IndicatorSignals(rsi_zone=rsi_zone, sma_cross=sma_cross)


