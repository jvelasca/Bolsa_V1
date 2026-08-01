"""Score_TA determinista desde Facts (RFC-008 D2.2). Rango [-1.0, +1.0]."""

from __future__ import annotations

from dataclasses import dataclass

from bolsa_analytics.knowledge.models import FactSet

TREND_WEIGHT = 0.40
MOMENTUM_WEIGHT = 0.25
STRUCTURE_WEIGHT = 0.20
PARTICIPATION_WEIGHT = 0.15

TREND_SCORES = {
    "strong_bullish": 1.0,
    "bullish": 0.55,
    "weak": 0.0,
    "bearish": -0.55,
    "strong_bearish": -1.0,
    "unknown": 0.0,
}

MOMENTUM_SCORES = {
    "strong": 0.75,
    "neutral": 0.0,
    "weak": -0.75,
    "unknown": 0.0,
}

STRUCTURE_SCORES = {
    "bullish_stack": 0.8,
    "mixed": 0.0,
    "bearish_stack": -0.8,
    "unknown": 0.0,
}

PARTICIPATION_SCORES = {
    "institutional_bias": 0.6,  # signo lo da el price_slope vía trend; aquí refuerzo
    "aligned": 0.2,
    "diverging": -0.5,
    "unknown": 0.0,
}


@dataclass(frozen=True, slots=True)
class ScoreTaResult:
    score: float
    components: dict[str, float]
    coverage: float
    exhaustion: bool
    claims: tuple[str, ...]


def _val(fact_set: FactSet, key: str) -> str:
    f = fact_set.get(key)
    return f.value if f else "unknown"


def _conf(fact_set: FactSet, key: str) -> float:
    f = fact_set.get(key)
    return f.confidence if f else 0.0


def score_ta_from_facts(fact_set: FactSet) -> ScoreTaResult:
    """Combina hechos TA en un score direccional determinista."""
    trend_v = _val(fact_set, "trend.primary")
    mom_v = _val(fact_set, "momentum")
    struct_v = _val(fact_set, "structure.sma")
    part_v = _val(fact_set, "participation")
    exh_v = _val(fact_set, "exhaustion")

    trend_s = TREND_SCORES.get(trend_v, 0.0)
    mom_s = MOMENTUM_SCORES.get(mom_v, 0.0)
    struct_s = STRUCTURE_SCORES.get(struct_v, 0.0)
    part_s = PARTICIPATION_SCORES.get(part_v, 0.0)

    # Participación: si hay sesgo institucional, alinea con el signo de tendencia
    if part_v == "institutional_bias" and trend_s != 0:
        part_s = 0.6 if trend_s > 0 else -0.6
    elif part_v == "institutional_bias":
        part_s = 0.0

    raw = (
        TREND_WEIGHT * trend_s
        + MOMENTUM_WEIGHT * mom_s
        + STRUCTURE_WEIGHT * struct_s
        + PARTICIPATION_WEIGHT * part_s
    )

    exhaustion = exh_v == "true"
    if exhaustion:
        # Reduce magnitud; no invierte sola
        raw *= 0.65

    score = max(-1.0, min(1.0, raw))

    known_keys = ("trend.primary", "momentum", "structure.sma", "participation", "exhaustion")
    coverage = sum(1 for k in known_keys if _val(fact_set, k) != "unknown") / len(known_keys)

    claims = tuple(
        f.claim
        for f in fact_set.facts
        if f.key in known_keys and f.value != "unknown"
    )

    return ScoreTaResult(
        score=round(score, 4),
        components={
            "trend": trend_s,
            "momentum": mom_s,
            "structure": struct_s,
            "participation": part_s,
        },
        coverage=round(coverage, 3),
        exhaustion=exhaustion,
        claims=claims,
    )
