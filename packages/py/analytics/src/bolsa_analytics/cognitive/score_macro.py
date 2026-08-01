"""Score_MACRO determinista desde Facts (RFC-008 D6). Rango [-1.0, +1.0]."""

from __future__ import annotations

from dataclasses import dataclass

from bolsa_analytics.knowledge.models import FactSet

VOL_SCORES = {
    "calm": 0.55,
    "elevated": 0.05,
    "stress": -0.65,
    "panic": -1.0,
    "unknown": 0.0,
}
CURVE_SCORES = {
    "steep": 0.35,
    "normal": 0.15,
    "flat": -0.15,
    "inverted": -0.55,
    "unknown": 0.0,
}
CREDIT_SCORES = {
    "tight": 0.45,
    "normal": 0.1,
    "wide": -0.55,
    "stress": -0.95,
    "unknown": 0.0,
}
BREADTH_SCORES = {
    "strong": 0.5,
    "mixed": 0.0,
    "weak": -0.55,
    "unknown": 0.0,
}
APPETITE_SCORES = {
    "risk_on": 0.7,
    "neutral": 0.0,
    "risk_off": -0.7,
    "unknown": 0.0,
}

W_VOL = 0.30
W_CURVE = 0.15
W_CREDIT = 0.25
W_BREADTH = 0.15
W_APPETITE = 0.15


@dataclass(frozen=True, slots=True)
class ScoreMacroResult:
    score: float
    components: dict[str, float]
    coverage: float
    claims: tuple[str, ...]
    stress: bool  # vol panic o crédito stress


def score_macro_from_facts(fact_set: FactSet) -> ScoreMacroResult:
    def val(key: str) -> str:
        f = fact_set.get(key)
        return f.value if f else "unknown"

    vol = val("macro.volatility_regime")
    curve = val("macro.yield_curve")
    credit = val("macro.credit")
    breadth = val("macro.breadth")
    appetite = val("macro.risk_appetite")

    comps = {
        "volatility": VOL_SCORES.get(vol, 0.0),
        "yield_curve": CURVE_SCORES.get(curve, 0.0),
        "credit": CREDIT_SCORES.get(credit, 0.0),
        "breadth": BREADTH_SCORES.get(breadth, 0.0),
        "risk_appetite": APPETITE_SCORES.get(appetite, 0.0),
    }
    known = sum(
        1
        for v in (vol, curve, credit, breadth, appetite)
        if v != "unknown"
    )
    coverage = known / 5.0

    raw = (
        W_VOL * comps["volatility"]
        + W_CURVE * comps["yield_curve"]
        + W_CREDIT * comps["credit"]
        + W_BREADTH * comps["breadth"]
        + W_APPETITE * comps["risk_appetite"]
    )
    # Si cobertura baja, atenuar hacia 0
    score = round(max(-1.0, min(1.0, raw * (0.4 + 0.6 * coverage))), 4)
    stress = vol == "panic" or credit == "stress"
    claims = tuple(
        f.claim
        for f in fact_set.facts
        if f.key.startswith("macro.") and f.value != "unknown"
    )
    return ScoreMacroResult(
        score=score,
        components=comps,
        coverage=round(coverage, 3),
        claims=claims,
        stress=stress,
    )
