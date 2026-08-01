"""Mapa IndicatorUniverse IND-* → chart definitionId (compute_spec).

Fuente de verdad de metadatos: packages/shared/src/indicator-universe.ts
Este mapa solo resuelve cómputo hasta que el bridge lea shared exportado.
"""

from __future__ import annotations

# IND-* → id legacy del gráfico / compute_spec
CANONICAL_TO_CHART_DEFINITION: dict[str, str] = {
    "IND-VOL": "volume",
    "IND-SMA": "sma",
    "IND-EMA": "ema",
    "IND-LWMA": "wma",
    "IND-BB": "bb",
    "IND-RSI": "rsi",
    "IND-MACD": "macd",
    "IND-SO": "stoch",
    "IND-ATR": "atr",
    "IND-CCI": "cci",
    "IND-AI-TECH-RATING": "technical_rating_v1",
    "IND-AI-DATA-QUALITY": "bar_data_quality_v1",
    "IND-AI-GLOBAL-SCORE": "ai_global_score_v1",
    "IND-AI-HYBRID-STRATEGY": "strategy_hybrid_score_v1",
    # Oleada 1
    "IND-WILLR": "willr",
    "IND-MOM": "mom",
    "IND-SD": "sd",
    "IND-DC": "dc",
    # Oleada 2
    "IND-ADX": "adx",
    "IND-SRSI": "srsi",
    "IND-ST": "st",
    "IND-VWAP": "vwap",
    # Oleada 3
    "IND-OBV": "obv",
    "IND-ROC": "roc",
    "IND-MFI": "mfi",
    "IND-AROON": "aroon",
    "IND-SAR": "sar",
    "IND-BEARS": "bears",
    "IND-BULLS": "bulls",
    "IND-ALI": "ali",
    "IND-FR": "fr",
    "IND-ICH": "ich",
}


def resolve_chart_definition_id(ref: str | None, fallback: str | None = None) -> str:
    """Acepta IND-* o id legacy; devuelve definitionId para compute_spec."""
    if not ref:
        if not fallback:
            raise ValueError("Missing indicator/chart reference")
        return fallback
    if ref.startswith("IND-"):
        chart = CANONICAL_TO_CHART_DEFINITION.get(ref)
        if not chart:
            raise ValueError(f"No chart mapping for {ref}")
        return chart
    return ref
