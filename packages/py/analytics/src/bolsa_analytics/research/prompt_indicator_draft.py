"""Borrador IndicatorPreset desde prompt (heurístico, sin LLM runtime)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bolsa_analytics.research.indicator_definition_validator import validate_indicator_draft

_ENGINE = "indicator_prompt_catalog_v1"

_CATALOG: list[dict[str, Any]] = [
    {
        "definition_id": "rsi",
        "label": "RSI",
        "patterns": (r"\brsi\b", r"sobreventa", r"sobrecompra", r"fuerza\s+relativa"),
        "defaults": {"period": 14},
        "source": "builtin",
    },
    {
        "definition_id": "sma",
        "label": "SMA",
        "patterns": (r"\bsma\b", r"media\s+m[oó]vil\s+simple", r"\bmedia\b"),
        "defaults": {"period": 20},
        "source": "builtin",
    },
    {
        "definition_id": "ema",
        "label": "EMA",
        "patterns": (r"\bema\b", r"media\s+exponencial"),
        "defaults": {"period": 20},
        "source": "builtin",
    },
    {
        "definition_id": "macd",
        "label": "MACD",
        "patterns": (r"\bmacd\b",),
        "defaults": {"fastPeriod": 12, "slowPeriod": 26, "signalPeriod": 9},
        "source": "builtin",
    },
    {
        "definition_id": "bb",
        "label": "Bollinger",
        "patterns": (r"bollinger", r"\bbb\b", r"banda[s]?\s+de"),
        "defaults": {"period": 20, "stdDev": 2},
        "source": "builtin",
    },
    {
        "definition_id": "stoch",
        "label": "Estocástico",
        "patterns": (r"estoc[aá]stic", r"\bstoch\b", r"%k"),
        "defaults": {"kPeriod": 14, "dPeriod": 3},
        "source": "builtin",
    },
    {
        "definition_id": "atr",
        "label": "ATR",
        "patterns": (r"\batr\b", r"true\s+range", r"rango\s+verdadero"),
        "defaults": {"period": 14},
        "source": "builtin",
    },
    {
        "definition_id": "cci",
        "label": "CCI",
        "patterns": (r"\bcci\b", r"commodity\s+channel"),
        "defaults": {"period": 20},
        "source": "builtin",
    },
    {
        "definition_id": "technical_rating_v1",
        "label": "Rating técnico IA",
        "patterns": (
            r"\brating\b",
            r"\bscore\b",
            r"puntuaci[oó]n",
            r"ranking\s+t[eé]cnico",
            r"setup\s+t[eé]cnico",
        ),
        "defaults": {"warmupBars": 50, "showComponents": False},
        "source": "ai",
    },
    {
        "definition_id": "bar_data_quality_v1",
        "label": "Calidad datos OHLCV",
        "patterns": (r"calidad\s+de?\s*datos", r"calidad\s+ohlcv", r"integridad\s+de?\s*barras", r"\bgaps?\b"),
        "defaults": {"gapLookback": 90},
        "source": "ai",
    },
    {
        "definition_id": "ai_global_score_v1",
        "label": "Score global IA",
        "patterns": (r"score\s+global", r"global\s+ia", r"combinad[oa]", r"ponderad[oa]"),
        "defaults": {"setupWeight": 70, "dataWeight": 30, "warmupBars": 50},
        "source": "ai",
    },
]

_PERIOD_PATTERN = re.compile(
    r"(?:periodo|period)\s*[:=]?\s*(\d{1,3})",
    flags=re.IGNORECASE,
)
_WEIGHT_PATTERN = re.compile(
    r"(\d{1,3})\s*%\s*(?:setup|rating|t[eé]cnico)",
    flags=re.IGNORECASE,
)
_DATA_WEIGHT_PATTERN = re.compile(
    r"(\d{1,3})\s*%\s*(?:datos|data|ohlcv)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PromptIndicatorDraftResult:
    definition_id: str
    suggested_preset_name: str
    confidence: float
    explanation: str
    preset: dict[str, Any]
    engine: str
    validated: bool
    feedback: dict[str, Any] | None = None


def _score_entry(text: str, entry: dict[str, Any]) -> int:
    score = 0
    for pattern in entry.get("patterns") or ():
        if re.search(pattern, text, flags=re.IGNORECASE):
            score += 2
    label = str(entry.get("label") or "")
    for word in re.findall(r"[a-zA-Záéíóúñ]{3,}", label.lower()):
        if re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE):
            score += 1
    return score


def _pick_definition(text: str) -> tuple[dict[str, Any], dict[str, int], int]:
    scores: dict[str, int] = {}
    by_id = {str(item["definition_id"]): item for item in _CATALOG}
    for entry in _CATALOG:
        definition_id = str(entry["definition_id"])
        score = _score_entry(text, entry)
        if score > 0:
            scores[definition_id] = score
    if not scores:
        raise ValueError(
            "No reconozco el indicador. Prueba: «RSI 14», «rating técnico» o «score global 70/30»."
        )
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner_id, winner_score = ranked[0]
    margin = winner_score - (ranked[1][1] if len(ranked) > 1 else 0)
    if winner_score < 2 and margin <= 0:
        raise ValueError(
            "No reconozco el indicador. Prueba: «RSI 14», «rating técnico» o «score global 70/30»."
        )
    return by_id[winner_id], scores, margin


def _apply_param_overrides(definition_id: str, parameters: dict[str, Any], text: str) -> dict[str, Any]:
    out = dict(parameters)
    period_match = _PERIOD_PATTERN.search(text)
    if period_match and "period" in out:
        out["period"] = int(period_match.group(1))
    if definition_id == "technical_rating_v1" and re.search(
        r"componente|desglos|tendencia\s+y\s+momentum",
        text,
        flags=re.IGNORECASE,
    ):
        out["showComponents"] = True
    if definition_id == "ai_global_score_v1":
        setup_match = _WEIGHT_PATTERN.search(text)
        data_match = _DATA_WEIGHT_PATTERN.search(text)
        if setup_match:
            setup = int(setup_match.group(1))
            out["setupWeight"] = setup
            out["dataWeight"] = max(0, 100 - setup)
        elif data_match:
            data = int(data_match.group(1))
            out["dataWeight"] = data
            out["setupWeight"] = max(0, 100 - data)
    return out


def _build_feedback(
    *,
    prompt: str,
    definition_id: str,
    label: str,
    confidence: float,
    scores: dict[str, int],
    margin: int,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    alternatives = [
        {
            "definitionId": key,
            "label": next(e["label"] for e in _CATALOG if e["definition_id"] == key),
            "score": value,
            "selected": key == definition_id,
        }
        for key, value in ranked[:4]
    ]
    warnings: list[str] = []
    ambiguous = margin <= 1 and len(scores) > 1
    if confidence < 0.55:
        warnings.append("Confianza baja: revisa el indicador sugerido antes de añadirlo al gráfico.")
    elif confidence < 0.72:
        warnings.append("Confianza moderada: confirma parámetros en el editor de preset.")
    if ambiguous:
        warnings.append("Varias opciones encajan parecido; mira las alternativas.")

    param_bits = [f"{key}={value}" for key, value in parameters.items() if key != "color"]
    summary = f"Interpreté «{prompt.strip()[:80]}» como indicador {label}"
    if param_bits:
        summary += f" ({', '.join(param_bits[:4])})."

    return {
        "summary": summary,
        "detectedSignals": [
            {"id": "definition", "label": "Motor", "detail": label},
            {"id": "panel", "label": "Panel", "detail": "Inferior" if definition_id != "sma" else "Precio"},
        ],
        "alternatives": alternatives,
        "warnings": warnings,
        "engineLabel": "Catálogo heurístico (local)",
        "ambiguous": ambiguous,
        "matchedDefinitionId": definition_id,
    }


def draft_indicator_from_prompt(prompt: str) -> PromptIndicatorDraftResult:
    text = prompt.strip()
    if len(text) < 4:
        raise ValueError("Describe el indicador con al menos 4 caracteres.")

    entry, scores, margin = _pick_definition(text.lower())
    definition_id = str(entry["definition_id"])
    label = str(entry["label"])
    winner_score = scores[definition_id]
    confidence = round(min(0.97, 0.45 + winner_score * 0.08 + margin * 0.07), 2)

    parameters = _apply_param_overrides(definition_id, dict(entry["defaults"]), text)
    validated, errors = validate_indicator_draft(definition_id=definition_id, parameters=parameters)
    if not validated:
        raise ValueError("; ".join(errors))

    period_suffix = ""
    if "period" in parameters:
        period_suffix = f" {parameters['period']}"
    suggested_name = f"{label}{period_suffix}".strip()

    preset: dict[str, Any] = {
        "id": f"draft-ind-{definition_id}",
        "name": suggested_name,
        "source": entry.get("source", "builtin"),
        "locked": False,
        "definitionId": definition_id,
        "parameters": parameters,
        "lineWidth": 2,
        "derivedFromDefinitionId": definition_id,
    }

    explanation = (
        f"Indicador «{label}» ({definition_id}) con {winner_score} coincidencias en catálogo."
    )
    feedback = _build_feedback(
        prompt=text,
        definition_id=definition_id,
        label=label,
        confidence=confidence,
        scores=scores,
        margin=margin,
        parameters=parameters,
    )

    return PromptIndicatorDraftResult(
        definition_id=definition_id,
        suggested_preset_name=suggested_name,
        confidence=confidence,
        explanation=explanation,
        preset=preset,
        engine=_ENGINE,
        validated=True,
        feedback=feedback,
    )
