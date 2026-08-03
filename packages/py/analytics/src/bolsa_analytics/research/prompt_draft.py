"""P11 — borrador StrategyDefinitionV1 desde prompt (heurístico catalog-aware, sin LLM runtime)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.research.hybrid_definition import (
    DEFAULT_HYBRID_MIN_SCORE,
    HYBRID_GATE_PRESET_KEYS,
    strategy_definition_from_hybrid,
)
from bolsa_analytics.research.strategy_definition_validator import validate_strategy_definition
from bolsa_analytics.signals.fundamental_gate import build_fundamental_gate
from bolsa_analytics.signals.preset_catalog import (
    load_preset_catalog,
    preset_label,
    strategy_definition_from_preset,
)

DraftKind = Literal["classic", "hybrid"]

_EXTRA_PATTERNS: dict[str, tuple[str, ...]] = {
    "sma_crossover": (r"cruce\s+sma", r"sma\s*20", r"media[s]?\s+m[oó]vil"),
    "rsi_mean_reversion": (r"reversi[oó]n", r"mean\s+reversion", r"rsi\s*<\s*30"),
    "ema_crossover": (r"cruce\s+ema", r"ema\s*12"),
    "golden_cross": (r"golden\s+cross", r"cruce\s+dorado", r"50\s*/\s*200"),
    "death_cross": (r"death\s+cross", r"cruce\s+de\s+la\s+muerte", r"bajista\s+50"),
    "macd_signal_cross": (r"macd\s*/\s*se[nñ]al", r"cruce\s+macd"),
    "macd_zero_line": (r"macd\s*>\s*0", r"l[ií]nea\s+cero"),
    "rsi_momentum": (r"rsi\s*>\s*50", r"momentum\s+rsi"),
    "rsi_oversold_bounce": (r"sobreventa", r"oversold", r"rebote\s+rsi"),
    "stoch_oversold": (r"estoc[aá]stic", r"stoch", r"%k\s*<\s*20"),
    "bollinger_lower_bounce": (r"bb\s+inferior", r"bollinger\s+inferior", r"rebote\s+bb"),
    "bollinger_upper_breakout": (r"ruptura\s+bb", r"bollinger\s+superior", r"breakout"),
    "price_above_sma200": (r"sma\s*200", r"200\s+periodos", r"por\s+encima\s+de\s+200"),
    "ma_stack_bullish": (r"apilamiento", r"stack\s+bullish", r"medias\s+alineadas"),
    "pullback_in_uptrend": (r"pullback", r"retroceso\s+en\s+tendencia", r"correcci[oó]n\s+alcista"),
    "cci_oversold": (r"\bcci\b", r"commodity\s+channel"),
    "donchian_breakout": (r"\bdonchian\b", r"canal\s+donchian", r"rotura\s+de?\s*canal"),
    "adx_di_trend": (r"\badx\b", r"\b\+?\-?di\b", r"directional\s+index"),
    "ichimoku_tk_cross": (r"\bichimoku\b", r"\btenkan\b", r"\bkijun\b", r"\bnube\b"),
    "vwap_reclaim": (r"\bvwap\b", r"volumen\s+ponderad"),
    "supertrend_follow": (r"\bsuper\s*trend\b", r"\bsupertrend\b"),
}

_HYBRID_PATTERNS: tuple[str, ...] = (
    r"\bh[ií]brid[oa]s?\b",
    r"\bhybrid\b",
    r"\brating\b",
    r"\bscore\b",
    r"\bpuntuaci[oó]n\b",
    r"\branking\b",
    r"\bmejor\s+valorad",
    r"\btop\s+\d",
    r"\bfiltr(?:ar|o).+(?:puntu|rating|score)",
    r"\bseleccionar\s+los\s+mejores\b",
)

_TIMEFRAME_MAP: list[tuple[str, str]] = [
    (r"\b(1\s*wk|semanal|weekly|1\s*semana)\b", "1wk"),
    (r"\b(4\s*h|4h|cuatro\s+horas)\b", "1d"),
    (r"\b(1\s*h|1h|horari[oa]|hourly)\b", "1d"),
    (r"\b(1\s*d|1d|diari[oa]|daily|d[ií]a)\b", "1d"),
]

# Intención operativa explícita (gana sobre menciones incidentales tipo «pivote (Semanal)»).
_STRONG_DAILY_TF: tuple[str, ...] = (
    r"periodo\s+diari",
    r"operativ\w*\s+diari",
    r"\ben\s+diario\b",
    r"timeframe\s*[:=]?\s*(?:1d|diari)",
    r"barras?\s+diari",
    r"velas?\s+diari",
)
_STRONG_WEEKLY_TF: tuple[str, ...] = (
    r"periodo\s+semanal",
    r"operativ\w*\s+semanal",
    r"\ben\s+semanal\b",
    r"timeframe\s*[:=]?\s*(?:1wk|semanal|weekly)",
    r"barras?\s+semanal",
    r"velas?\s+semanal",
)

# Condiciones multi-TF entre paréntesis no definen el TF de la estrategia.
_PAREN_TF_LABEL = re.compile(
    r"\(\s*(?:diario|semanal|mensual|weekly|daily|monthly|1d|1wk)\s*\)",
    flags=re.IGNORECASE,
)

_MIN_SCORE_PATTERN = re.compile(
    r"(?:rating|score|puntuaci[oó]n)\s*(?:>=|≥|m[ií]n(?:imo)?|m[aá]ximo)?\s*(\d{2})",
    flags=re.IGNORECASE,
)
_MAX_PE_PATTERN = re.compile(
    r"(?:per|p/e)\s*(?:<=|≤|<|m[aá]ximo|max)?\s*(\d+(?:\.\d+)?)",
    flags=re.IGNORECASE,
)
_MIN_CAP_PATTERN = re.compile(
    r"(?:cap(?:italizaci[oó]n)?|market\s+cap)\s*(?:>=|≥|>|m[ií]n(?:imo)?)?\s*(\d+(?:\.\d+)?)\s*(?:m|mm|millones?)?",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PromptDraftResult:
    draft_kind: DraftKind
    preset_key: str
    timeframe: str
    suggested_name: str
    confidence: float
    explanation: str
    definition: dict[str, Any]
    engine: str
    validated: bool
    gate_preset_key: str | None = None
    min_score: float | None = None
    validation_errors: tuple[str, ...] = ()
    feedback: dict[str, Any] | None = None


def _score_patterns(text: str, patterns: tuple[str, ...]) -> int:
    score = 0
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            score += 1
    return score


def _intraday_note(text: str) -> str | None:
    if re.search(r"\b(1\s*h|1h|4\s*h|4h|horari[oa]|hourly)\b", text, flags=re.IGNORECASE):
        return "intraday detectado; kernel usa timeframe diario (1d)"
    return None


def _detect_timeframe(text: str) -> tuple[str, str | None]:
    """Detecta TF operativo 1d/1wk.

    Prioridad:
    1. Frases fuertes («periodo diario», «operativa semanal»…).
    2. Menciones sueltas, ignorando etiquetas entre paréntesis («pivote (Semanal)»).
    3. Default 1d.
    """
    stripped = _PAREN_TF_LABEL.sub(" ", text)
    daily_strong = _score_patterns(stripped, _STRONG_DAILY_TF) > 0
    weekly_strong = _score_patterns(stripped, _STRONG_WEEKLY_TF) > 0
    if daily_strong and not weekly_strong:
        return "1d", _intraday_note(text)
    if weekly_strong and not daily_strong:
        return "1wk", None
    if daily_strong and weekly_strong:
        # Conflicto de intención operativa → diario (más común en Probar).
        return "1d", _intraday_note(text)

    has_weekly = bool(
        re.search(r"\b(1\s*wk|semanal|weekly|1\s*semana)\b", stripped, flags=re.IGNORECASE)
    )
    has_daily = bool(
        re.search(r"\b(1\s*d|1d|diari[oa]|daily|d[ií]a)\b", stripped, flags=re.IGNORECASE)
    )
    if has_weekly and not has_daily:
        return "1wk", None
    if has_daily:
        return "1d", _intraday_note(text)

    # Fallback: primer match débil en texto sin paréntesis TF.
    for pattern, timeframe in _TIMEFRAME_MAP:
        if re.search(pattern, stripped, flags=re.IGNORECASE):
            return timeframe, _intraday_note(text) if timeframe == "1d" else None
    return "1d", None


def _detect_fundamental_gate(text: str) -> dict[str, Any] | None:
    max_pe = None
    pe_match = _MAX_PE_PATTERN.search(text)
    if pe_match:
        max_pe = float(pe_match.group(1))
    min_cap = None
    cap_match = _MIN_CAP_PATTERN.search(text)
    if cap_match:
        min_cap = float(cap_match.group(1))
    return build_fundamental_gate(
        max_trailing_pe=max_pe,
        min_market_cap_millions=min_cap,
    )


def _detect_min_score(text: str) -> float:
    match = _MIN_SCORE_PATTERN.search(text)
    if match:
        return float(max(40, min(85, int(match.group(1)))))
    alt = re.search(r"\b(?:>=|≥)\s*(\d{2})\b", text)
    if alt:
        return float(max(40, min(85, int(alt.group(1)))))
    return float(DEFAULT_HYBRID_MIN_SCORE)


def _is_hybrid_intent(text: str) -> bool:
    return _score_patterns(text, _HYBRID_PATTERNS) > 0


def _preset_scores(text: str) -> dict[str, int]:
    catalog = load_preset_catalog()
    presets: dict[str, Any] = catalog.get("presets") or {}
    scores: dict[str, int] = {}

    for preset_key, preset in presets.items():
        score = 0
        for tag in preset.get("tags") or []:
            if re.search(rf"\b{re.escape(str(tag))}\b", text, flags=re.IGNORECASE):
                score += 2
        label = str(preset.get("label") or "")
        for word in re.findall(r"[a-zA-Záéíóúñ]{3,}", label.lower()):
            if re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE):
                score += 1
        score += _score_patterns(text, _EXTRA_PATTERNS.get(preset_key, ()))
        if score > 0:
            scores[preset_key] = score

    return scores


def _pick_preset(scores: dict[str, int], *, allow_weak_match: bool = False) -> tuple[str, int, int]:
    if not scores:
        raise ValueError(
            "No reconozco el patrón. Prueba: «cruce SMA diario», «RSI sobreventa» "
            "o «híbrido con rating ≥ 65 en tendencia alcista»."
        )
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner_key, winner_score = ranked[0]
    if winner_score < 2 and not allow_weak_match:
        raise ValueError(
            "No reconozco el patrón. Prueba: «cruce SMA diario», «RSI sobreventa» "
            "o «híbrido con rating ≥ 65 en tendencia alcista»."
        )
    runner_score = ranked[1][1] if len(ranked) > 1 else 0
    return winner_key, winner_score, winner_score - runner_score


def _confidence(winner_score: int, margin: int, hybrid: bool) -> float:
    base = 0.42 + winner_score * 0.08 + margin * 0.06
    if hybrid:
        base += 0.05
    return round(min(0.97, base), 2)


def _build_explanation(
    *,
    draft_kind: DraftKind,
    preset_key: str,
    timeframe: str,
    winner_score: int,
    intraday_note: str | None,
    min_score: float | None,
) -> str:
    label = preset_label(preset_key)
    tf_label = {"1d": "diario", "1wk": "semanal"}.get(timeframe, timeframe)
    parts = [
        f"Interpretado como {'rastreador híbrido' if draft_kind == 'hybrid' else 'preset clásico'} "
        f"«{label}» en {tf_label} ({winner_score} coincidencias en catálogo)."
    ]
    if draft_kind == "hybrid" and min_score is not None:
        parts.append(f"Rating técnico mínimo: {int(min_score)}.")
    if intraday_note:
        parts.append(intraday_note)
    return " ".join(parts)


_ENGINE_LABELS: dict[str, str] = {
    "prompt_catalog_v1": "Catálogo heurístico (local)",
    "openai_structured_v1": "OpenAI + validación catálogo",
}


def _fundamental_signal_details(gate: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not gate:
        return []
    details: list[tuple[str, str]] = []
    for condition in gate.get("conditions") or []:
        if not isinstance(condition, dict):
            continue
        metric = str(condition.get("metric") or "")
        operator = str(condition.get("operator") or "")
        value = condition.get("value")
        if metric == "trailingPe" and operator == "lte" and isinstance(value, (int, float)):
            details.append(("per_max", f"PER trailing ≤ {value:g}"))
        if metric == "marketCap" and operator == "gte" and isinstance(value, (int, float)):
            details.append(("cap_min", f"Cap. mínima ≥ {value / 1_000_000:g} M€"))
    sectors = gate.get("sectors") or []
    if sectors:
        details.append(("sectors", f"Sectores: {', '.join(str(s) for s in sectors)}"))
    return details


def _build_fundamental_preview(gate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not gate:
        return None
    conditions_raw = gate.get("conditions") or []
    sectors = gate.get("sectors") or []
    if not conditions_raw and not sectors:
        return None
    metric_labels = {
        "trailingPe": "PER trailing",
        "forwardPe": "PER forward",
        "marketCap": "Capitalización",
    }
    operator_labels = {"lt": "<", "lte": "≤", "gt": ">", "gte": "≥", "eq": "="}
    conditions: list[dict[str, Any]] = []
    for condition in conditions_raw:
        if not isinstance(condition, dict):
            continue
        metric = str(condition.get("metric") or "")
        operator = str(condition.get("operator") or "")
        value = condition.get("value")
        if not isinstance(value, (int, float)):
            continue
        if metric == "marketCap":
            millions = float(value) / 1_000_000
            value_label = (
                f"{millions / 1000:.1f} B€" if millions >= 1000 else f"{millions:.0f} M€"
            )
        else:
            value_label = f"{float(value):g}"
        conditions.append(
            {
                "metric": metric,
                "label": metric_labels.get(metric, metric),
                "operator": operator,
                "valueLabel": f"{operator_labels.get(operator, operator)} {value_label}",
            }
        )
    return {
        "enabled": True,
        "conditions": conditions,
        "sectors": [str(s) for s in sectors],
        "maxAgeDays": int(gate.get("maxAgeDays") or 30),
        "dataSource": "Yahoo Finance (quoteSummary)",
        "refreshNote": (
            "Antes del scan se refrescan fundamentales en lote desde Yahoo (P14). "
            "Instrumentos sin datos recientes pueden quedar fuera."
        ),
        "rejectNote": (
            "Si PER o capitalización no cumplen el filtro, el instrumento se descarta "
            "antes del rating técnico."
        ),
    }


def _build_feedback(
    *,
    prompt: str,
    draft_kind: DraftKind,
    matched_preset_key: str,
    gate_preset_key: str | None,
    preset_key: str,
    timeframe: str,
    winner_score: int,
    margin: int,
    confidence: float,
    min_score: float | None,
    fundamental_gate: dict[str, Any] | None,
    intraday_note: str | None,
    hybrid_intent: bool,
    allow_weak_match: bool,
    scores: dict[str, int],
    engine: str,
    gate_candidates: dict[str, int],
) -> dict[str, Any]:
    tf_label = {"1d": "diario (1d)", "1wk": "semanal (1wk)"}.get(timeframe, timeframe)
    gate_label = preset_label(gate_preset_key or preset_key)
    matched_label = preset_label(matched_preset_key)
    catalog = load_preset_catalog()
    preset_def = (catalog.get("presets") or {}).get(preset_key) or {}
    preset_description = str(preset_def.get("description") or "")

    detected: list[dict[str, str]] = [
        {
            "id": "mode",
            "label": "Modo",
            "detail": "Híbrido IA" if draft_kind == "hybrid" else "Preset clásico",
        },
        {"id": "timeframe", "label": "Timeframe", "detail": tf_label},
    ]
    if hybrid_intent:
        detected.append({"id": "hybrid_intent", "label": "Ranking IA", "detail": "Sí"})
    if min_score is not None:
        detected.append(
            {
                "id": "min_score",
                "label": "Rating mínimo",
                "detail": str(int(min_score)),
            }
        )
    for signal_id, detail in _fundamental_signal_details(fundamental_gate):
        detected.append({"id": signal_id, "label": "Fundamental", "detail": detail})

    detected.append(
        {
            "id": "preset_match",
            "label": "Patrón en tu texto",
            "detail": matched_label,
        }
    )
    if draft_kind == "hybrid":
        detected.append(
            {
                "id": "gate",
                "label": "Gate técnico (filtro duro)",
                "detail": gate_label,
            }
        )

    warnings: list[str] = []
    ambiguous = margin <= 1 and len(scores) > 1
    if confidence < 0.55:
        warnings.append(
            "Confianza baja: el texto encaja poco con el catálogo. Revisa el preset antes de guardar."
        )
    elif confidence < 0.72:
        warnings.append("Confianza moderada: conviene confirmar que el preset elegido es el que buscas.")
    if ambiguous:
        warnings.append(
            "Varios presets encajan parecido en tu mensaje; mira las alternativas abajo."
        )
    if allow_weak_match and winner_score < 2:
        warnings.append(
            "Detecté pocas coincidencias literales; interpreté tu intención híbrida con valores por defecto."
        )
    if intraday_note:
        warnings.append(
            "Mencionaste timeframe intraday; los rastreadores usan barras diarias o semanales (1d/1wk)."
        )
    if draft_kind == "hybrid":
        if not gate_candidates:
            warnings.append(
                f"No identifiqué un gate híbrido claro; uso «{gate_label}» por defecto."
            )
        elif matched_preset_key != (gate_preset_key or preset_key):
            warnings.append(
                f"Tu texto encaja con «{matched_label}», pero el gate híbrido será «{gate_label}» "
                "(solo ciertos presets pueden filtrar antes del rating)."
            )

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    alternatives: list[dict[str, Any]] = []
    for key, score in ranked[:4]:
        alternatives.append(
            {
                "presetKey": key,
                "label": preset_label(key),
                "score": score,
                "selected": key == preset_key,
            }
        )

    scan_steps: list[str] = [
        "Tomar el universo de la lista seleccionada en el laboratorio.",
    ]
    if draft_kind == "hybrid":
        scan_steps.append(
            f"Aplicar gate técnico «{gate_label}» en la última barra (condición obligatoria)."
        )
        if fundamental_gate and (fundamental_gate.get("conditions") or fundamental_gate.get("sectors")):
            scan_steps.append(
                "Filtrar por fundamentales Yahoo (PER, capitalización, sector) si hay datos recientes."
            )
        scan_steps.append(
            f"Calcular rating técnico v1.1 y descartar instrumentos por debajo de {int(min_score or DEFAULT_HYBRID_MIN_SCORE)}."
        )
        scan_steps.append("Ordenar supervivientes por score y devolver los mejores (maxResults).")
    else:
        if preset_description:
            scan_steps.append(f"Evaluar en la última barra: {preset_description}")
        else:
            scan_steps.append(f"Evaluar reglas del preset «{preset_label(preset_key)}» en la última barra.")
        scan_steps.append("Devolver instrumentos con señal de entrada activa.")

    summary_parts = [
        f"He leído tu mensaje y lo interpreto como "
        f"{'un rastreador híbrido' if draft_kind == 'hybrid' else 'un preset clásico'} "
        f"en timeframe {tf_label}."
    ]
    if draft_kind == "hybrid":
        summary_parts.append(f"Gate: {gate_label}. Rating mínimo: {int(min_score or DEFAULT_HYBRID_MIN_SCORE)}.")
    else:
        summary_parts.append(f"Preset: {preset_label(preset_key)}.")
    if fundamental_gate and _fundamental_signal_details(fundamental_gate):
        summary_parts.append("Incluyo filtros fundamentales.")
    if ambiguous:
        summary_parts.append("Hay ambigüedad; revisa las alternativas.")
    summary_parts.append(f"Confianza: {int(confidence * 100)}%.")

    return {
        "summary": " ".join(summary_parts),
        "detectedSignals": detected,
        "alternatives": alternatives,
        "warnings": warnings,
        "scanSteps": scan_steps,
        "engineLabel": _ENGINE_LABELS.get(engine, engine),
        "ambiguous": ambiguous,
        "matchedPresetKey": matched_preset_key,
        "userPrompt": prompt.strip(),
        "fundamentalPreview": _build_fundamental_preview(fundamental_gate),
    }


def draft_strategy_from_prompt(
    prompt: str,
    *,
    instrument_ids: list[str] | None = None,
) -> PromptDraftResult:
    cleaned = prompt.strip()
    if len(cleaned) < 4:
        raise ValueError("Describe la estrategia en al menos 4 caracteres")

    normalized = cleaned.lower()
    scores = _preset_scores(normalized)
    hybrid_intent = _is_hybrid_intent(normalized)
    matched_preset_key, winner_score, margin = _pick_preset(scores, allow_weak_match=hybrid_intent)
    timeframe, intraday_note = _detect_timeframe(normalized)
    draft_kind: DraftKind = "hybrid" if hybrid_intent else "classic"
    confidence = _confidence(winner_score, margin, hybrid_intent)
    fundamental_gate: dict[str, Any] | None = None
    gate_candidates: dict[str, int] = {}

    if draft_kind == "hybrid":
        gate_candidates = {
            key: score for key, score in scores.items() if key in HYBRID_GATE_PRESET_KEYS
        }
        gate_preset_key = (
            max(gate_candidates, key=gate_candidates.get)
            if gate_candidates
            else "price_above_sma200"
        )
        min_score = _detect_min_score(normalized)
        fundamental_gate = _detect_fundamental_gate(normalized)
        gate_label = preset_label(gate_preset_key)
        suggested_name = f"Híbrido · {gate_label} · ≥{int(min_score)} ({timeframe})"
        definition = strategy_definition_from_hybrid(
            name=suggested_name,
            gate_preset_key=gate_preset_key,
            min_score=min_score,
            instrument_ids=instrument_ids or [],
            timeframe=timeframe,  # type: ignore[arg-type]
            fundamental_gate=fundamental_gate,
        )
        preset_key = gate_preset_key
    else:
        min_score = None
        gate_preset_key = None
        preset_key = matched_preset_key
        suggested_name = f"{preset_label(preset_key)} ({timeframe})"
        definition = strategy_definition_from_preset(
            preset_key,
            instrument_ids or [],
            timeframe=timeframe,  # type: ignore[arg-type]
        )

    definition["origin"] = "assisted"
    definition["sourcePrompt"] = cleaned
    definition["name"] = suggested_name

    validation_errors = tuple(validate_strategy_definition(definition))
    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    engine = "prompt_catalog_v1"
    explanation = _build_explanation(
        draft_kind=draft_kind,
        preset_key=preset_key,
        timeframe=timeframe,
        winner_score=winner_score,
        intraday_note=intraday_note,
        min_score=min_score,
    )
    feedback = _build_feedback(
        prompt=cleaned,
        draft_kind=draft_kind,
        matched_preset_key=matched_preset_key,
        gate_preset_key=gate_preset_key,
        preset_key=preset_key,
        timeframe=timeframe,
        winner_score=winner_score,
        margin=margin,
        confidence=confidence,
        min_score=min_score,
        fundamental_gate=fundamental_gate,
        intraday_note=intraday_note,
        hybrid_intent=hybrid_intent,
        allow_weak_match=hybrid_intent,
        scores=scores,
        engine=engine,
        gate_candidates=gate_candidates,
    )

    return PromptDraftResult(
        draft_kind=draft_kind,
        preset_key=preset_key,
        timeframe=timeframe,
        suggested_name=suggested_name,
        confidence=confidence,
        explanation=explanation,
        definition=definition,
        engine=engine,
        validated=True,
        gate_preset_key=gate_preset_key,
        min_score=min_score,
        validation_errors=validation_errors,
        feedback=feedback,
    )
