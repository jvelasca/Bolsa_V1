"""Knowledge Layer TA — Features → ART-FACT-SET (RFC-008 D2.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from bolsa_analytics.knowledge.models import Fact, FactSet, TechnicalInputs

# Umbrales v1 (documentados; versionables más adelante)
ADX_STRONG = 25.0
RSI_STRONG = 60.0
RSI_WEAK = 40.0
RSI_EXHAUST_HIGH = 80.0
RSI_EXHAUST_LOW = 20.0
BB_WIDTH_HIGH = 8.0
BB_WIDTH_LOW = 2.5
ATR_PCT_HIGH = 75.0
ATR_PCT_LOW = 25.0


def _fid(prefix: str) -> str:
    return f"fact-{prefix}-{uuid4().hex[:8]}"


def _trend_fact(inp: TechnicalInputs) -> Fact:
    refs: dict[str, str] = {}
    if inp.adx is not None:
        refs["adx"] = str(inp.adx)
    if inp.plus_di is not None:
        refs["plus_di"] = str(inp.plus_di)
    if inp.minus_di is not None:
        refs["minus_di"] = str(inp.minus_di)

    if inp.adx is None or inp.plus_di is None or inp.minus_di is None:
        return Fact(
            fact_id=_fid("trend"),
            key="trend.primary",
            value="unknown",
            confidence=0.2,
            claim="Tendencia desconocida: faltan ADX / DI",
            refs=refs or None,
        )

    if inp.adx <= ADX_STRONG:
        return Fact(
            fact_id=_fid("trend"),
            key="trend.primary",
            value="weak",
            confidence=0.7,
            claim=f"Tendencia débil / rango (ADX={inp.adx:.1f} ≤ {ADX_STRONG})",
            refs=refs,
        )

    if inp.plus_di > inp.minus_di:
        return Fact(
            fact_id=_fid("trend"),
            key="trend.primary",
            value="strong_bullish",
            confidence=0.85,
            claim=(
                f"Tendencia primaria alcista fuerte "
                f"(ADX={inp.adx:.1f}, DI+={inp.plus_di:.1f} > DI-={inp.minus_di:.1f})"
            ),
            refs=refs,
        )

    if inp.minus_di > inp.plus_di:
        return Fact(
            fact_id=_fid("trend"),
            key="trend.primary",
            value="strong_bearish",
            confidence=0.85,
            claim=(
                f"Tendencia primaria bajista fuerte "
                f"(ADX={inp.adx:.1f}, DI-={inp.minus_di:.1f} > DI+={inp.plus_di:.1f})"
            ),
            refs=refs,
        )

    return Fact(
        fact_id=_fid("trend"),
        key="trend.primary",
        value="weak",
        confidence=0.6,
        claim="Tendencia indiscernible (DI+ ≈ DI-)",
        refs=refs,
    )


def _momentum_fact(inp: TechnicalInputs) -> Fact:
    if inp.rsi is None:
        return Fact(
            fact_id=_fid("mom"),
            key="momentum",
            value="unknown",
            confidence=0.2,
            claim="Momentum desconocido: falta RSI",
        )
    refs = {"rsi": str(inp.rsi)}
    if inp.rsi > RSI_STRONG:
        return Fact(
            fact_id=_fid("mom"),
            key="momentum",
            value="strong",
            confidence=0.8,
            claim=f"Momentum fuerte (RSI={inp.rsi:.1f} > {RSI_STRONG})",
            refs=refs,
        )
    if inp.rsi < RSI_WEAK:
        return Fact(
            fact_id=_fid("mom"),
            key="momentum",
            value="weak",
            confidence=0.8,
            claim=f"Momentum débil (RSI={inp.rsi:.1f} < {RSI_WEAK})",
            refs=refs,
        )
    return Fact(
        fact_id=_fid("mom"),
        key="momentum",
        value="neutral",
        confidence=0.75,
        claim=f"Momentum neutro (RSI={inp.rsi:.1f})",
        refs=refs,
    )


def _exhaustion_fact(inp: TechnicalInputs) -> Fact:
    if inp.rsi is None:
        return Fact(
            fact_id=_fid("exh"),
            key="exhaustion",
            value="unknown",
            confidence=0.2,
            claim="Agotamiento desconocido: falta RSI",
        )
    refs = {"rsi": str(inp.rsi)}
    exhausted = inp.rsi > RSI_EXHAUST_HIGH or inp.rsi < RSI_EXHAUST_LOW
    return Fact(
        fact_id=_fid("exh"),
        key="exhaustion",
        value="true" if exhausted else "false",
        confidence=0.85 if exhausted else 0.7,
        claim=(
            f"Agotamiento de momentum (RSI={inp.rsi:.1f})"
            if exhausted
            else f"Sin agotamiento extremo (RSI={inp.rsi:.1f})"
        ),
        refs=refs,
    )


def _participation_fact(inp: TechnicalInputs) -> Fact:
    if inp.obv_slope is None or inp.price_slope is None:
        return Fact(
            fact_id=_fid("part"),
            key="participation",
            value="unknown",
            confidence=0.2,
            claim="Participación desconocida: faltan slopes OBV/precio",
        )
    refs = {
        "obv_slope": str(inp.obv_slope),
        "price_slope": str(inp.price_slope),
    }
    same_sign = (inp.obv_slope > 0 and inp.price_slope > 0) or (
        inp.obv_slope < 0 and inp.price_slope < 0
    )
    if same_sign and abs(inp.obv_slope) > 0:
        return Fact(
            fact_id=_fid("part"),
            key="participation",
            value="institutional_bias",
            confidence=0.75,
            claim="OBV confirma el movimiento de precio (sesgo institucional)",
            refs=refs,
        )
    if (inp.obv_slope > 0 and inp.price_slope < 0) or (
        inp.obv_slope < 0 and inp.price_slope > 0
    ):
        return Fact(
            fact_id=_fid("part"),
            key="participation",
            value="diverging",
            confidence=0.8,
            claim="Divergencia OBV vs precio",
            refs=refs,
        )
    return Fact(
        fact_id=_fid("part"),
        key="participation",
        value="aligned",
        confidence=0.55,
        claim="Participación alineada / neutra",
        refs=refs,
    )


def _volatility_fact(inp: TechnicalInputs) -> Fact:
    refs: dict[str, str] = {}
    if inp.atr_percentile is not None:
        refs["atr_percentile"] = str(inp.atr_percentile)
        if inp.atr_percentile >= ATR_PCT_HIGH:
            return Fact(
                fact_id=_fid("vol"),
                key="volatility",
                value="high",
                confidence=0.8,
                claim=f"Volatilidad alta (ATR percentil={inp.atr_percentile:.0f})",
                refs=refs,
            )
        if inp.atr_percentile <= ATR_PCT_LOW:
            return Fact(
                fact_id=_fid("vol"),
                key="volatility",
                value="low",
                confidence=0.8,
                claim=f"Volatilidad baja (ATR percentil={inp.atr_percentile:.0f})",
                refs=refs,
            )
        return Fact(
            fact_id=_fid("vol"),
            key="volatility",
            value="normal",
            confidence=0.7,
            claim=f"Volatilidad normal (ATR percentil={inp.atr_percentile:.0f})",
            refs=refs,
        )

    if inp.bb_width_pct is not None:
        refs["bb_width_pct"] = str(inp.bb_width_pct)
        if inp.bb_width_pct >= BB_WIDTH_HIGH:
            return Fact(
                fact_id=_fid("vol"),
                key="volatility",
                value="high",
                confidence=0.7,
                claim=f"Volatilidad alta (BB width={inp.bb_width_pct:.1f}%)",
                refs=refs,
            )
        if inp.bb_width_pct <= BB_WIDTH_LOW:
            return Fact(
                fact_id=_fid("vol"),
                key="volatility",
                value="low",
                confidence=0.7,
                claim=f"Volatilidad baja / squeeze (BB width={inp.bb_width_pct:.1f}%)",
                refs=refs,
            )
        return Fact(
            fact_id=_fid("vol"),
            key="volatility",
            value="normal",
            confidence=0.65,
            claim=f"Volatilidad normal (BB width={inp.bb_width_pct:.1f}%)",
            refs=refs,
        )

    return Fact(
        fact_id=_fid("vol"),
        key="volatility",
        value="unknown",
        confidence=0.2,
        claim="Volatilidad desconocida: faltan ATR percentil / BB width",
    )


def _structure_fact(inp: TechnicalInputs) -> Fact:
    if inp.close is None or inp.sma_20 is None or inp.sma_50 is None:
        return Fact(
            fact_id=_fid("sma"),
            key="structure.sma",
            value="unknown",
            confidence=0.2,
            claim="Estructura SMA desconocida: faltan close / SMA20 / SMA50",
        )
    refs = {
        "close": str(inp.close),
        "sma_20": str(inp.sma_20),
        "sma_50": str(inp.sma_50),
    }
    if inp.close > inp.sma_20 > inp.sma_50:
        return Fact(
            fact_id=_fid("sma"),
            key="structure.sma",
            value="bullish_stack",
            confidence=0.8,
            claim="Estructura alcista (close > SMA20 > SMA50)",
            refs=refs,
        )
    if inp.close < inp.sma_20 < inp.sma_50:
        return Fact(
            fact_id=_fid("sma"),
            key="structure.sma",
            value="bearish_stack",
            confidence=0.8,
            claim="Estructura bajista (close < SMA20 < SMA50)",
            refs=refs,
        )
    return Fact(
        fact_id=_fid("sma"),
        key="structure.sma",
        value="mixed",
        confidence=0.65,
        claim="Estructura mixta en SMAs",
        refs=refs,
    )


def build_technical_fact_set(
    instrument_id: str,
    inputs: TechnicalInputs | dict,
    *,
    timestamp: str | None = None,
    fact_set_id: str | None = None,
) -> FactSet:
    """Transforma inputs técnicos en ART-FACT-SET interpretable."""
    inp = inputs if isinstance(inputs, TechnicalInputs) else TechnicalInputs.from_feature_map(inputs)
    ts = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    facts = (
        _trend_fact(inp),
        _momentum_fact(inp),
        _exhaustion_fact(inp),
        _participation_fact(inp),
        _volatility_fact(inp),
        _structure_fact(inp),
    )
    return FactSet(
        fact_set_id=fact_set_id or f"FS-TA-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        timestamp=ts,
        facts=facts,
    )
