"""F1b — variables de prompt y explicación heurística (sin LLM).

El LLM solo recibe estos strings; nunca recalcula Score_FUND.
@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md §10
"""

from __future__ import annotations

import re
from typing import Any


def _fmt(v: Any, *, pct: bool = False, digits: int = 2) -> str:
    if v is None:
        return "—"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)
    if pct:
        return f"{n * 100:.{digits}f}%"
    return f"{n:.{digits}f}"


def _altman_label(derived: dict[str, Any]) -> str:
    z = derived.get("altmanZ")
    if z is None:
        return "sin dato"
    try:
        zv = float(z)
    except (TypeError, ValueError):
        return "sin dato"
    src = derived.get("altmanEbitSource") or ""
    zone = "zona segura" if zv >= 2.99 else ("zona gris" if zv >= 1.81 else "distress")
    if src == "financial_ebitda_proxy":
        return f"{zone}; EBIT=proxy EBITDA"
    return zone


def build_fundamental_copilot_variables(card: dict[str, Any]) -> dict[str, str]:
    """Aplana FundamentalCardDto → variables del prompt §10."""
    facts = card.get("facts") if isinstance(card.get("facts"), dict) else {}
    derived = card.get("derived") if isinstance(card.get("derived"), dict) else {}
    meta = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
    pe = facts.get("forwardPe") if facts.get("forwardPe") is not None else facts.get("trailingPe")
    evidence = card.get("narrativeFacts") or []
    warnings = card.get("warnings") or []
    return {
        "ticker": str(card.get("ticker") or "—"),
        "sector": str(facts.get("sector") or "—"),
        "pe": _fmt(pe, digits=1),
        "roe": _fmt(facts.get("roe"), pct=True, digits=1),
        "operatingMargin": _fmt(facts.get("operatingMargin"), pct=True, digits=1),
        "debtToEquity": _fmt(facts.get("debtToEquity"), digits=2),
        "altmanZ": _fmt(derived.get("altmanZ"), digits=2),
        "altmanLabel": _altman_label(derived),
        "fcfYield": _fmt(derived.get("fcfYield"), pct=True, digits=1),
        "wacc": _fmt(derived.get("wacc"), pct=True, digits=1),
        "dcfUpside": _fmt(derived.get("dcfUpside"), pct=True, digits=1),
        "grahamUpside": _fmt(derived.get("grahamUpside"), pct=True, digits=1),
        "scoreFund": _fmt(card.get("scoreFund"), digits=2),
        "score100": str(card.get("scoreDisplay100") if card.get("scoreDisplay100") is not None else "—"),
        "confidence": str(meta.get("confidence") or "LOW"),
        "scoreVersion": str(meta.get("scoreVersion") or "—"),
        "fetchedAt": str(meta.get("fetchedAt") or "—"),
        "sourceVersion": str(meta.get("sourceVersion") or "—"),
        "evidence": "; ".join(str(x) for x in evidence[:6]) if evidence else "—",
        "warnings": "; ".join(str(x) for x in warnings[:6]) if warnings else "—",
    }


def heuristic_fundamental_explanation(card: dict[str, Any]) -> dict[str, Any]:
    """Fallback sin Ollama: prosa desde facts/warnings ya calculados."""
    vars_ = build_fundamental_copilot_variables(card)
    derived = card.get("derived") if isinstance(card.get("derived"), dict) else {}
    conf = vars_["confidence"]
    p1_bits: list[str] = []
    if conf == "LOW":
        p1_bits.append(
            "La confianza en los datos es LOW: la interpretación es provisional por cobertura incompleta o ficha obsoleta."
        )
    score100 = vars_["score100"]
    p1_bits.append(
        f"Score_FUND mostrado {score100}/100 (raw {vars_['scoreFund']}) con scoreVersion {vars_['scoreVersion']}."
    )
    if vars_["roe"] != "—":
        p1_bits.append(f"ROE {vars_['roe']}.")
    if vars_["operatingMargin"] != "—":
        p1_bits.append(f"Margen operativo {vars_['operatingMargin']}.")
    if vars_["fcfYield"] != "—":
        p1_bits.append(f"FCF Yield {vars_['fcfYield']}.")
    if vars_["dcfUpside"] != "—":
        wacc_bit = f" WACC {vars_['wacc']}" if vars_["wacc"] != "—" else ""
        dcf_scenarios = derived.get("dcfScenarios")
        scen = dcf_scenarios if isinstance(dcf_scenarios, dict) else None
        scen_bit = ""
        if scen and isinstance(scen.get("bear"), dict) and isinstance(scen.get("bull"), dict):
            bear_u = _fmt(scen["bear"].get("upside"), pct=True, digits=1)
            bull_u = _fmt(scen["bull"].get("upside"), pct=True, digits=1)
            if bear_u != "—" and bull_u != "—":
                scen_bit = f" Escenarios bear/bull {bear_u}/{bull_u}."
        p1_bits.append(
            f"DCF upside {vars_['dcfUpside']} (FCF 2 etapas{wacc_bit}; precalculado).{scen_bit}"
        )
    if vars_["grahamUpside"] != "—":
        p1_bits.append(f"Graham upside {vars_['grahamUpside']}.")

    p2_bits: list[str] = []
    if card.get("distress"):
        p2_bits.append("Hay señal de distress en solvencia: el score está limitado a la baja.")
    if vars_["debtToEquity"] != "—":
        p2_bits.append(f"Apalancamiento D/E {vars_['debtToEquity']}.")
    if vars_["altmanZ"] != "—":
        p2_bits.append(f"Altman Z {vars_['altmanZ']} ({vars_['altmanLabel']}).")
    if vars_["pe"] != "—":
        p2_bits.append(f"Valoración PE {vars_['pe']}.")
    if vars_["warnings"] != "—":
        p2_bits.append(f"Avisos: {vars_['warnings']}.")
    if not p2_bits:
        p2_bits.append("No hay avisos adicionales de riesgo en el snapshot.")

    sector = vars_["sector"]
    p3 = (
        f"Sector declarado: {sector}. Compara márgenes, deuda y crecimiento con pares del mismo sector "
        f"usando fuentes propias; este copiloto no inventa peers numéricos."
    )

    return {
        "paragraphs": [
            " ".join(p1_bits),
            " ".join(p2_bits),
            p3,
        ],
        "disclaimer": (
            "Interpretación automática a partir de datos precalculados. "
            "No es consejo de inversión ni sustituye el análisis propio."
        ),
    }


_ROE_CLAIM = re.compile(r"\bROE\b[^0-9%]{0,24}(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE)


def sanitize_copilot_query(text: str, *, max_len: int = 800) -> str:
    """Q2.6 — recorta y limpia query de usuario al copiloto FA."""
    cleaned = " ".join((text or "").split())
    return cleaned[:max_len]


def validate_copilot_does_not_invent_roe(
    prose: str,
    card: dict[str, Any],
) -> list[str]:
    """
    Guardrail: si el texto afirma un ROE %, debe coincidir (aprox) con facts.roe.
    Devuelve lista de violaciones (vacía = OK).
    """
    facts = card.get("facts") if isinstance(card.get("facts"), dict) else {}
    roe = facts.get("roe")
    violations: list[str] = []
    for match in _ROE_CLAIM.finditer(prose or ""):
        claimed = float(match.group(1).replace(",", "."))
        if roe is None:
            violations.append(f"ROE {claimed}% inventado (facts.roe ausente)")
            continue
        try:
            expected_pct = float(roe) * 100.0 if abs(float(roe)) <= 1.5 else float(roe)
        except (TypeError, ValueError):
            violations.append("facts.roe no numérico")
            continue
        if abs(claimed - expected_pct) > 0.6:
            violations.append(
                f"ROE {claimed}% no coincide con facts ({expected_pct:.1f}%)"
            )
    return violations
