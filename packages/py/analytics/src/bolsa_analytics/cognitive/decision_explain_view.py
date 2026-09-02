"""V1.72 — DecisionExplainView: proyección canónica «Por qué» (espejo TS).

No LLM · no muta decisión · Ranking ≠ BUY (LONG ≠ COMPRAR).
"""

from __future__ import annotations

import math
import re
from typing import Any, Literal, Mapping

DECISION_EXPLAIN_VIEW_ARTIFACT = "ART-DECISION-EXPLAIN-VIEW"
DECISION_EXPLAIN_VIEW_SCHEMA = "1.1.0"

THESIS_DIRECTION_LABELS: dict[str, str] = {
    "recommend_long": "LONG",
    "recommend_short": "SHORT",
    "wait": "ESPERAR",
    "reduce": "REDUCIR",
    "exit_hint": "SALIDA",
}

TRADE_PLAN_WHY_NOT_LABELS: dict[str, str] = {
    "fit": "No encaja en la cartera",
    "entry": "Entrada aún no lista",
    "freshness": "Datos no frescos",
    "mandate": "Sin mandato abierto",
    "expired": "La decisión caducó",
    "no_stop": "Falta stop estructural",
    "regime": "Régimen no admite longs",
    "orphan": "Sin paquete de decisión",
    "rr": "Riesgo/beneficio insuficiente",
    "legacy_projection": "Sin plan vivo (proyección; motivo desconocido)",
}

FACTOR_LABELS: dict[str, str] = {
    "tendencia": "Tendencia",
    "momentum": "Momentum",
    "volumen": "Volumen",
    "regimen": "Régimen",
    "rr": "R/R",
    "riesgo": "Riesgo",
    "perfil": "Perfil",
}

JOURNAL_STUDY_OPINION_LABELS: dict[str, str] = {
    "bullish": "Alcista",
    "bearish": "Bajista",
    "neutral": "Neutra",
}

AUTHORIZATION_COPY = "La tesis no es autorización ni orden. Ranking ≠ BUY."

FactorState = Literal["pass", "fail", "unknown"]


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def format_explain_score_label(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + "/10"


def entry_mark_distance(
    entry: float | None, mark_price: float | None
) -> tuple[float | None, float | None]:
    if entry is None or mark_price is None:
        return None, None
    if not _finite(entry) or not _finite(mark_price):
        return None, None
    distance_abs = float(mark_price) - float(entry)
    distance_pct = None if float(entry) == 0 else (distance_abs / float(entry)) * 100
    return distance_abs, distance_pct


def _factor(fid: str, state: FactorState, detail: str) -> dict[str, str]:
    return {"id": fid, "label": FACTOR_LABELS[fid], "state": state, "detail": detail}


def _signed_component(value: object) -> tuple[FactorState, str]:
    if not _finite(value):
        return "unknown", "sin dato"
    n = float(value)
    if n > 0:
        return "pass", f"{n:.2f}"
    if n < 0:
        return "fail", f"{n:.2f}"
    return "unknown", "neutro"


def _trend_lines(study: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for trend in study.get("trends") or []:
        if not isinstance(trend, Mapping):
            continue
        text = (
            str(trend.get("display") or "").strip()
            or str(trend.get("label") or "").strip()
            or str(trend.get("value") or "").strip()
        )
        if text:
            lines.append(text)
    return lines


def _tendencia(study: Mapping[str, Any]) -> dict[str, str]:
    opinion = study.get("opinion")
    lines = _trend_lines(study)
    values = [
        str(t.get("value") or "")
        for t in (study.get("trends") or [])
        if isinstance(t, Mapping)
    ]
    blob = " ".join([str(opinion or ""), *lines, *values]).lower()
    bullish = opinion == "bullish" or bool(re.search(r"alcista|bull|up|strong_bull", blob))
    bearish = opinion == "bearish" or bool(re.search(r"bajista|bear|down", blob))
    if bullish and not bearish:
        detail = JOURNAL_STUDY_OPINION_LABELS.get(str(opinion), "") or (lines[0] if lines else "alcista")
        return _factor("tendencia", "pass", detail)
    if bearish and not bullish:
        detail = JOURNAL_STUDY_OPINION_LABELS.get(str(opinion), "") or (lines[0] if lines else "bajista")
        return _factor("tendencia", "fail", detail)
    if not opinion and not lines:
        return _factor("tendencia", "unknown", "sin dato")
    return _factor("tendencia", "unknown", "señales mixtas")


def _build_factors(
    study: Mapping[str, Any],
    why_not: list[str],
    entries_blocked: bool,
    ta_components: Mapping[str, Any] | None,
    regime_hint: str | None,
) -> list[dict[str, str]]:
    ta = ta_components or {}
    mom_state, mom_detail = _signed_component(ta.get("momentum"))
    vol_state, vol_detail = _signed_component(ta.get("volume"))

    if "regime" in why_not:
        regimen = _factor("regimen", "fail", TRADE_PLAN_WHY_NOT_LABELS["regime"])
    elif isinstance(regime_hint, str) and regime_hint.strip():
        hint = regime_hint.strip()
        low = hint.lower()
        if re.search(r"bajista|bear|no admite", low):
            regimen = _factor("regimen", "fail", hint)
        elif re.search(r"alcista|bull", low):
            regimen = _factor("regimen", "pass", hint)
        else:
            regimen = _factor("regimen", "unknown", hint)
    else:
        regimen = _factor("regimen", "unknown", "sin dato")

    expected_rr = study.get("expectedRR")
    if "rr" in why_not:
        rr = _factor("rr", "fail", TRADE_PLAN_WHY_NOT_LABELS["rr"])
    elif _finite(expected_rr) and float(expected_rr) > 0:
        rr = _factor("rr", "pass", f"{float(expected_rr):.1f}:1")
    else:
        rr = _factor("rr", "unknown", "sin dato")

    risk_amount = study.get("riskAmount")
    if entries_blocked:
        riesgo = _factor("riesgo", "fail", "Entradas bloqueadas")
    elif _finite(risk_amount) and float(risk_amount) > 0:
        riesgo = _factor("riesgo", "pass", f"planificado {float(risk_amount):.0f}")
    else:
        riesgo = _factor("riesgo", "unknown", "sin dato")

    if "fit" in why_not:
        perfil = _factor("perfil", "fail", TRADE_PLAN_WHY_NOT_LABELS["fit"])
    elif "mandate" in why_not:
        perfil = _factor("perfil", "fail", TRADE_PLAN_WHY_NOT_LABELS["mandate"])
    else:
        perfil = _factor("perfil", "unknown", "sin dato")

    return [
        _tendencia(study),
        _factor("momentum", mom_state, mom_detail),
        _factor("volumen", vol_state, vol_detail),
        regimen,
        rr,
        riesgo,
        perfil,
    ]


def build_decision_explain_view(
    study: Mapping[str, Any],
    *,
    entries_blocked: bool = False,
    gate_status: str | None = None,
    why_not: list[str] | None = None,
    mark_price: float | None = None,
    ta_components: Mapping[str, Any] | None = None,
    regime_hint: str | None = None,
    execution_allowed: bool | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    """Proyección determinista. No muta study. LONG ≠ COMPRAR."""
    codes = list(why_not or [])
    resolved_action = action if action is not None else study.get("action")
    direction_label = None
    if isinstance(resolved_action, str) and resolved_action in THESIS_DIRECTION_LABELS:
        direction_label = THESIS_DIRECTION_LABELS[resolved_action]
    else:
        resolved_action = None

    strength = study.get("strength")
    score = (
        {"value": float(strength), "label": format_explain_score_label(float(strength))}
        if _finite(strength)
        else {"value": None, "label": None}
    )

    entry = float(study["entry"]) if _finite(study.get("entry")) else None
    mark = float(mark_price) if _finite(mark_price) else None
    distance_abs, distance_pct = entry_mark_distance(entry, mark)

    symbol = study.get("symbol")
    symbol_out = str(symbol).strip() if isinstance(symbol, str) and symbol.strip() else None

    return {
        "artifactType": DECISION_EXPLAIN_VIEW_ARTIFACT,
        "schemaVersion": DECISION_EXPLAIN_VIEW_SCHEMA,
        "symbol": symbol_out,
        "score": score,
        "thesisDirection": {"action": resolved_action, "label": direction_label},
        "factors": _build_factors(
            study, codes, entries_blocked, ta_components, regime_hint
        ),
        "levels": {
            "entry": entry,
            "stop": float(study["stop"]) if _finite(study.get("stop")) else None,
            "target1": float(study["target1"]) if _finite(study.get("target1")) else None,
            "target2": float(study["target2"]) if _finite(study.get("target2")) else None,
        },
        "entryGeometry": {
            "entry": entry,
            "currentPrice": mark,
            "distanceAbs": distance_abs,
            "distancePct": distance_pct,
        },
        "authorization": {
            "entriesBlocked": entries_blocked,
            "gateStatus": gate_status,
            "executionAllowed": execution_allowed,
            "copy": AUTHORIZATION_COPY,
        },
    }
