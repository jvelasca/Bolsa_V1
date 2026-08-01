"""Score_FUND determinista desde Facts (RFC-008 D5). Rango [-1.0, +1.0].

Pilares públicos (F1): ``value`` | ``quality`` | ``growth`` | ``risk``
Facts internos: ``fund.valuation`` | ``fund.quality`` | ``fund.growth`` | ``fund.solvency``
(mapping solvency → risk documentado; no reabrir nombres en UI).

``scoreVersion`` ``fund_score_v1``: bump si cambian pesos/tablas.
Distress fuerza score ≤ −0.85 (Altman Z bajo o Beneish M > −1.78).
UI: ``scoreDisplay100`` (neutro 50). Sin ``bias`` en card.

@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
@see docs/engineering/fa-status-and-test-plan-2026-07-31.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bolsa_analytics.knowledge.models import FactSet

SCORE_FUND_VERSION = "fund_score_v1"

DataConfidence = Literal["HIGH", "MEDIUM", "LOW"]

# Pesos por pilar (F2 puede añadir management / moat sin reescribir el motor).
FUND_SCORE_WEIGHTS: dict[str, float] = {
    "value": 0.35,
    "quality": 0.25,
    "growth": 0.20,
    "risk": 0.20,
}

VALUE_SCORES = {
    "attractive": 0.85,
    "fair": 0.25,
    "rich": -0.35,
    "expensive": -0.85,
    "distorted": -0.2,
    "unknown": 0.0,
}
QUALITY_SCORES = {
    "high": 0.9,
    "average": 0.1,
    "low": -0.7,
    "unknown": 0.0,
}
GROWTH_SCORES = {
    "strong": 0.85,
    "moderate": 0.25,
    "weak": -0.6,
    "unknown": 0.0,
}
# Fact key fund.solvency → pilar risk
RISK_SCORES = {
    "strong": 0.9,
    "adequate": 0.2,
    "uncertain": -0.15,
    "levered": -0.45,
    "weak": -0.7,
    "distress": -1.0,
    "unknown": 0.0,
}

# Compat aliases (tests / imports antiguos)
VALUATION_W = FUND_SCORE_WEIGHTS["value"]
QUALITY_W = FUND_SCORE_WEIGHTS["quality"]
GROWTH_W = FUND_SCORE_WEIGHTS["growth"]
SOLVENCY_W = FUND_SCORE_WEIGHTS["risk"]
VALUATION_SCORES = VALUE_SCORES
SOLVENCY_SCORES = RISK_SCORES


@dataclass(frozen=True, slots=True)
class ScoreFundResult:
    score: float
    score_version: str
    components: dict[str, float]  # value, quality, growth, risk
    coverage: float
    confidence: DataConfidence
    claims: tuple[str, ...]  # evidencias (narrativeFacts en card)
    distress: bool
    warnings: tuple[str, ...]


def _val(fact_set: FactSet, key: str) -> str:
    f = fact_set.get(key)
    return f.value if f else "unknown"


def coverage_to_confidence(coverage: float) -> DataConfidence:
    if coverage >= 0.8:
        return "HIGH"
    if coverage >= 0.5:
        return "MEDIUM"
    return "LOW"


def _pillar_warnings(val_v: str, qual_v: str, grow_v: str, solv_v: str, *, distress: bool) -> tuple[str, ...]:
    out: list[str] = []
    if val_v == "unknown":
        out.append("Pilar value sin datos; cobertura incompleta")
    if qual_v == "unknown":
        out.append("Pilar quality sin datos; cobertura incompleta")
    if grow_v == "unknown":
        out.append("Pilar growth sin datos; cobertura incompleta")
    if solv_v == "unknown":
        out.append("Pilar risk (solvency) sin datos; cobertura incompleta")
    if distress:
        out.append("Distress / solvencia crítica (override Score_FUND)")
    return tuple(out)


# Beneish M-Score threshold (manipulación probable). Misma constante que facts.
_BENEISH_MANIPULATION = -1.78


def _beneish_distress(fact_set: FactSet) -> bool:
    """True si refs de solvency traen Beneish M por encima del umbral."""
    solv = fact_set.get("fund.solvency")
    if not solv or not solv.refs:
        return False
    raw = solv.refs.get("beneishM")
    if raw is None:
        return False
    try:
        return float(raw) > _BENEISH_MANIPULATION
    except (TypeError, ValueError):
        return False


def _apply_hard_limits(score: float, fact_set: FactSet) -> tuple[float, bool]:
    """Overrides duros: Altman/solvency distress · Beneish M > −1.78."""
    solv_v = _val(fact_set, "fund.solvency")
    distress = solv_v == "distress" or _beneish_distress(fact_set)
    if distress:
        score = min(score, -0.85)
    return score, distress


def score_fund_from_facts(fact_set: FactSet) -> ScoreFundResult:
    val_v = _val(fact_set, "fund.valuation")
    qual_v = _val(fact_set, "fund.quality")
    grow_v = _val(fact_set, "fund.growth")
    solv_v = _val(fact_set, "fund.solvency")

    components = {
        "value": VALUE_SCORES.get(val_v, 0.0),
        "quality": QUALITY_SCORES.get(qual_v, 0.0),
        "growth": GROWTH_SCORES.get(grow_v, 0.0),
        "risk": RISK_SCORES.get(solv_v, 0.0),
    }

    weights = {
        "value": FUND_SCORE_WEIGHTS["value"] if val_v != "unknown" else 0.0,
        "quality": FUND_SCORE_WEIGHTS["quality"] if qual_v != "unknown" else 0.0,
        "growth": FUND_SCORE_WEIGHTS["growth"] if grow_v != "unknown" else 0.0,
        "risk": FUND_SCORE_WEIGHTS["risk"] if solv_v != "unknown" else 0.0,
    }
    w_sum = sum(weights.values())
    w_total = sum(FUND_SCORE_WEIGHTS.values())
    if w_sum <= 0:
        score = 0.0
        coverage = 0.0
    else:
        score = sum(components[k] * weights[k] for k in components) / w_sum
        coverage = w_sum / w_total

    score, distress = _apply_hard_limits(score, fact_set)
    coverage_r = round(coverage, 3)
    warnings = _pillar_warnings(val_v, qual_v, grow_v, solv_v, distress=distress)

    claims = tuple(
        f.claim
        for f in fact_set.facts
        if f.key.startswith("fund.") and f.value != "unknown"
    )

    return ScoreFundResult(
        score=round(max(-1.0, min(1.0, score)), 4),
        score_version=SCORE_FUND_VERSION,
        components=components,
        coverage=coverage_r,
        confidence=coverage_to_confidence(coverage_r),
        claims=claims,
        distress=distress,
        warnings=warnings,
    )
