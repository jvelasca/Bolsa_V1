"""Macro → ART-FACT-SET (RFC-008 D6). instrument_id canónico = MARKET."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from bolsa_analytics.cognitive.macro_inputs import MacroInputs
from bolsa_analytics.knowledge.models import Fact, FactSet

MARKET_ID = "MARKET"


def _vol_fact(inp: MacroInputs) -> Fact:
    vix = inp.vix
    pct = inp.vix_percentile
    if vix is None and pct is None:
        return Fact(
            f"F-{uuid4().hex[:8]}",
            "macro.volatility_regime",
            "unknown",
            0.2,
            "Sin VIX / percentil",
        )
    # Prefer percentil; fallback niveles clásicos
    if pct is not None:
        if pct >= 90 or (vix is not None and vix >= 35):
            val, conf, claim = "panic", 0.9, f"Vol percentil={pct:.0f} / VIX={vix}"
        elif pct >= 75 or (vix is not None and vix >= 25):
            val, conf, claim = "stress", 0.85, f"Vol elevada pct={pct:.0f}"
        elif pct >= 55 or (vix is not None and vix >= 18):
            val, conf, claim = "elevated", 0.8, f"Vol moderada pct={pct:.0f}"
        else:
            val, conf, claim = "calm", 0.85, f"Vol calmada pct={pct:.0f}"
    else:
        assert vix is not None
        if vix >= 35:
            val, conf, claim = "panic", 0.85, f"VIX={vix:.1f}"
        elif vix >= 25:
            val, conf, claim = "stress", 0.8, f"VIX={vix:.1f}"
        elif vix >= 18:
            val, conf, claim = "elevated", 0.75, f"VIX={vix:.1f}"
        else:
            val, conf, claim = "calm", 0.8, f"VIX={vix:.1f}"
    return Fact(f"F-{uuid4().hex[:8]}", "macro.volatility_regime", val, conf, claim)


def _curve_fact(inp: MacroInputs) -> Fact:
    bps = inp.yield_curve_10y2y_bps
    if bps is None:
        return Fact(
            f"F-{uuid4().hex[:8]}",
            "macro.yield_curve",
            "unknown",
            0.2,
            "Sin spread 10y–2y",
        )
    if bps < -10:
        val, conf = "inverted", 0.9
    elif bps < 20:
        val, conf = "flat", 0.85
    elif bps < 80:
        val, conf = "normal", 0.8
    else:
        val, conf = "steep", 0.8
    return Fact(
        f"F-{uuid4().hex[:8]}",
        "macro.yield_curve",
        val,
        conf,
        f"10y–2y={bps:.0f} bps → {val}",
    )


def _credit_fact(inp: MacroInputs) -> Fact:
    oas = inp.credit_spread_oas_bps
    if oas is None:
        return Fact(
            f"F-{uuid4().hex[:8]}",
            "macro.credit",
            "unknown",
            0.15,
            "Sin OAS crédito",
        )
    if oas >= 600:
        val, conf = "stress", 0.9
    elif oas >= 450:
        val, conf = "wide", 0.85
    elif oas >= 320:
        val, conf = "normal", 0.8
    else:
        val, conf = "tight", 0.8
    return Fact(
        f"F-{uuid4().hex[:8]}",
        "macro.credit",
        val,
        conf,
        f"HY OAS≈{oas:.0f} bps → {val}",
    )


def _breadth_fact(inp: MacroInputs) -> Fact:
    b = inp.breadth_pct_above_ma50
    if b is None:
        return Fact(
            f"F-{uuid4().hex[:8]}",
            "macro.breadth",
            "unknown",
            0.15,
            "Sin amplitud",
        )
    if b >= 65:
        val, conf = "strong", 0.85
    elif b >= 40:
        val, conf = "mixed", 0.8
    else:
        val, conf = "weak", 0.85
    return Fact(
        f"F-{uuid4().hex[:8]}",
        "macro.breadth",
        val,
        conf,
        f"% > MA50 = {b:.0f} → {val}",
    )


def _risk_appetite_fact(
    vol: Fact, curve: Fact, credit: Fact, breadth: Fact
) -> Fact:
    """Agrega hechos → risk_on | neutral | risk_off | unknown."""
    known = [f for f in (vol, curve, credit, breadth) if f.value != "unknown"]
    if len(known) < 2:
        return Fact(
            f"F-{uuid4().hex[:8]}",
            "macro.risk_appetite",
            "unknown",
            0.25,
            "Cobertura macro insuficiente",
        )

    risk_off_hits = 0
    risk_on_hits = 0
    if vol.value in ("stress", "panic"):
        risk_off_hits += 2 if vol.value == "panic" else 1
    elif vol.value == "calm":
        risk_on_hits += 1
    if curve.value == "inverted":
        risk_off_hits += 1
    elif curve.value == "steep":
        risk_on_hits += 1
    if credit.value in ("wide", "stress"):
        risk_off_hits += 2 if credit.value == "stress" else 1
    elif credit.value == "tight":
        risk_on_hits += 1
    if breadth.value == "weak":
        risk_off_hits += 1
    elif breadth.value == "strong":
        risk_on_hits += 1

    if risk_off_hits >= risk_on_hits + 2:
        val = "risk_off"
    elif risk_on_hits >= risk_off_hits + 2:
        val = "risk_on"
    else:
        val = "neutral"
    conf = min(0.95, 0.55 + 0.1 * len(known))
    return Fact(
        f"F-{uuid4().hex[:8]}",
        "macro.risk_appetite",
        val,
        conf,
        f"risk_appetite={val} (off={risk_off_hits} on={risk_on_hits})",
    )


def build_macro_fact_set(
    inputs: MacroInputs | dict,
    *,
    timestamp: str | None = None,
    market_id: str = MARKET_ID,
) -> FactSet:
    inp = inputs if isinstance(inputs, MacroInputs) else MacroInputs.from_dict(inputs)
    ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    vol = _vol_fact(inp)
    curve = _curve_fact(inp)
    credit = _credit_fact(inp)
    breadth = _breadth_fact(inp)
    appetite = _risk_appetite_fact(vol, curve, credit, breadth)
    return FactSet(
        fact_set_id=f"FS-MACRO-{uuid4().hex[:12]}",
        instrument_id=market_id,
        timestamp=ts,
        facts=(vol, curve, credit, breadth, appetite),
        source="macro_v1",
    )
