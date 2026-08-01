"""FundamentalCard — DTO de lectura FIE (F1–F2.8). Solo ensambla; no escribe BD.

Derived: Altman, Piotroski, Graham, DCF(+escenarios), WACC/CAPM, ROIC, Beneish,
beta, ADV (null si incompletos). Filings no forman parte del card numérico.

@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md §12
@see docs/engineering/fa-status-and-test-plan-2026-07-31.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from bolsa_analytics.knowledge.as_of_cut import (
    LOOKAHEAD_BLOCKED_WARNING,
    RECONSTRUCTED_WARNING,
    normalize_as_of_date,
    resolve_fundamentals_pit,
    strip_lookahead_fundamentals,
)
from bolsa_analytics.knowledge.fundamental_assessment import build_fundamental_assessment
from bolsa_analytics.knowledge.fundamental_inputs import FundamentalInputs
from bolsa_analytics.knowledge.score_fund import (
    SCORE_FUND_VERSION,
    DataConfidence,
    coverage_to_confidence,
)

FUND_CARD_SCHEMA_VERSION = "fund_card_v1"
STALE_DAYS_DEFAULT = 30

# Cobertura de inputs Yahoo (confianza de datos; distinta del coverage de pilares).
_INPUT_CONFIDENCE_KEYS = (
    "roe",
    "debtToEquity",
    "currentRatio",
    "operatingMargin",
    "revenueGrowth",
    "freeCashflow",
)

_FACT_KEYS = (
    "marketCap",
    "trailingPe",
    "forwardPe",
    "sector",
    "roe",
    "roa",
    "operatingMargin",
    "profitMargin",
    "revenueGrowth",
    "earningsGrowth",
    "debtToEquity",
    "currentRatio",
    "quickRatio",
    "totalCash",
    "totalDebt",
    "ebitda",
    "freeCashflow",
    "priceToBook",
)

_DERIVED_KEYS = (
    "fcfYield",
    "altmanZ",
    "altmanMethod",
    "altmanEbitSource",
    "piotroski",
    "piotroskiMethod",
    "roic",
    "roicMethod",
    "beneishM",
    "beneishMethod",
    "grahamNumber",
    "grahamMethod",
    "grahamUpside",
    "beta",
    "averageVolume",
    "advUsd",
    "wacc",
    "waccMethod",
    "capmRf",
    "capmErp",
    "dcfEquityValue",
    "dcfUpside",
    "dcfMethod",
    "dcfScenarios",
    "totalAssets",
    "retainedEarnings",
    "totalLiabilities",
)


def fund_score_to_display_100(score: float | None) -> int | None:
    """Mapea Score_FUND [-1,1] → scoreDisplay100 [0,100] (neutro=50)."""
    if score is None:
        return None
    clamped = max(-1.0, min(1.0, float(score)))
    return int(round(((clamped + 1.0) / 2.0) * 100))


def compute_data_confidence(raw: dict[str, Any] | None) -> DataConfidence:
    """HIGH si ≥80% de inputs clave presentes; MEDIUM ≥50%; else LOW."""
    if not isinstance(raw, dict):
        return "LOW"
    present = sum(1 for k in _INPUT_CONFIDENCE_KEYS if raw.get(k) is not None)
    ratio = present / len(_INPUT_CONFIDENCE_KEYS)
    if ratio >= 0.8:
        return "HIGH"
    if ratio >= 0.5:
        return "MEDIUM"
    return "LOW"


def resolve_card_confidence(
    *,
    input_confidence: DataConfidence,
    pillar_coverage: float | None,
    is_stale: bool,
) -> DataConfidence:
    """
    Confianza de la tarjeta (dominio Python; UI solo pinta).
    - Stale → LOW (datos pueden mentir vs precio).
    - Peor entre cobertura de inputs y coverage de pilares Score_FUND.
    """
    if is_stale:
        return "LOW"
    rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    conf = input_confidence
    if pillar_coverage is not None:
        pillar_conf = coverage_to_confidence(pillar_coverage)
        if rank[pillar_conf] < rank[conf]:
            conf = pillar_conf
    return conf


def _parse_fetched_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _freshness(fetched_at: str | None, *, max_age_days: int = STALE_DAYS_DEFAULT) -> tuple[int | None, bool]:
    dt = _parse_fetched_at(fetched_at)
    if dt is None:
        return None, True
    age = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    days = int(age) if age >= 0 else 0
    return days, days > max_age_days


def _pick_facts(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Todas las keys siempre presentes (null explícito — hidratación UI)."""
    src = raw if isinstance(raw, dict) else {}
    return {k: src.get(k) for k in _FACT_KEYS}


def _pick_derived(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    return {k: src.get(k) for k in _DERIVED_KEYS}


def build_fundamental_card(
    *,
    instrument_id: str,
    ticker: str,
    fundamentals: dict[str, Any] | None,
    max_age_days: int = STALE_DAYS_DEFAULT,
    provider: str = "yahoo",
    as_of: str | None = None,
) -> dict[str, Any]:
    """Ensambla FundamentalCardDto (dict camelCase) desde snapshot Yahoo v3.

    ``as_of`` (YYYY-MM-DD): corte DÍA D. Si el pack es posterior a D, bloquea
    scores/ratios (sin look-ahead). Ver ``as_of_cut``.
    """
    raw_in = fundamentals if isinstance(fundamentals, dict) else None
    fetched_at = str(raw_in.get("fetchedAt")) if raw_in and raw_in.get("fetchedAt") else None
    as_of_norm = normalize_as_of_date(as_of)
    reconstructed = bool(raw_in and raw_in.get("asOfReconstructed"))
    pit = resolve_fundamentals_pit(
        as_of=as_of_norm,
        fetched_at=fetched_at,
        reconstructed=reconstructed,
    )

    raw = raw_in
    if pit == "blocked":
        raw = strip_lookahead_fundamentals(raw_in)

    stale_days, is_stale = _freshness(fetched_at, max_age_days=max_age_days)
    if not raw or pit == "blocked":
        is_stale = True
    if pit == "reconstructed":
        # Vintage is synthetic as-of; not "stale live".
        is_stale = False
        stale_days = None
    input_conf = compute_data_confidence(raw)
    source_version = str(raw.get("sourceVersion")) if raw and raw.get("sourceVersion") else None

    score_fund: float | None = None
    score_display: int | None = None
    distress = False
    pillars: dict[str, float] | None = None
    coverage: float | None = None
    narrative: list[str] = []
    warnings: list[str] = []
    assessment_id: str | None = None
    score_version = SCORE_FUND_VERSION

    if pit == "blocked":
        warnings.append(LOOKAHEAD_BLOCKED_WARNING)
    elif raw:
        if pit == "reconstructed":
            warnings.append(RECONSTRUCTED_WARNING)
        inputs = FundamentalInputs.from_dict(raw)
        has_signal = any(
            v is not None
            for v in (
                inputs.market_cap,
                inputs.trailing_pe,
                inputs.forward_pe,
                inputs.roe,
                inputs.operating_margin,
                inputs.revenue_growth,
                inputs.debt_to_equity,
                inputs.current_ratio,
                inputs.altman_z,
                inputs.fcf_yield,
            )
        )
        if has_signal:
            assessment, _, score_result = build_fundamental_assessment(instrument_id, inputs)
            score_fund = assessment.score
            score_display = fund_score_to_display_100(score_fund)
            distress = assessment.distress
            coverage = score_result.coverage
            score_version = score_result.score_version
            narrative = list(score_result.claims)
            # Assessment warnings (runtime) + score pillar warnings
            warnings = list(
                dict.fromkeys([*warnings, *score_result.warnings, *assessment.warnings])
            )
            assessment_id = assessment.assessment_id
            pillars = {
                "value": score_result.components["value"],
                "quality": score_result.components["quality"],
                "growth": score_result.components["growth"],
                "risk": score_result.components["risk"],
            }

    confidence = resolve_card_confidence(
        input_confidence=input_conf,
        pillar_coverage=coverage,
        is_stale=is_stale,
    )
    if pit == "blocked":
        confidence = "LOW"

    return {
        "schemaVersion": FUND_CARD_SCHEMA_VERSION,
        "instrumentId": instrument_id,
        "ticker": ticker,
        "scoreFund": score_fund,
        "scoreDisplay100": score_display,
        "distress": distress,
        "pillars": pillars,
        "facts": _pick_facts(raw),
        "derived": _pick_derived(raw),
        "metadata": {
            "provider": provider,
            "sourceVersion": source_version,
            "scoreVersion": score_version,
            "fetchedAt": fetched_at,
            "staleDays": stale_days,
            "isStale": is_stale,
            "confidence": confidence,
            "coverage": coverage,
            "asOfDate": as_of_norm,
            "pointInTime": pit,
        },
        "assessmentId": assessment_id,
        "narrativeFacts": narrative,
        "warnings": warnings,
    }


def card_to_chip(card: dict[str, Any]) -> dict[str, Any]:
    """Proyecta FundamentalCard → chip lista (PR3)."""
    meta = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
    facts = card.get("facts") if isinstance(card.get("facts"), dict) else {}
    derived = card.get("derived") if isinstance(card.get("derived"), dict) else {}
    return {
        "instrumentId": card.get("instrumentId"),
        "ticker": card.get("ticker"),
        "scoreDisplay100": card.get("scoreDisplay100"),
        "confidence": meta.get("confidence", "LOW"),
        "isStale": bool(meta.get("isStale", True)),
        "distress": bool(card.get("distress", False)),
        "roe": facts.get("roe"),
        "debtToEquity": facts.get("debtToEquity"),
        "altmanZ": derived.get("altmanZ"),
    }
