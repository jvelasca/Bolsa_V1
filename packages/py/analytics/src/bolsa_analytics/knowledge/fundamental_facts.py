"""Knowledge Layer FUND — FundamentalInputs → Facts (RFC-008 D5)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from bolsa_analytics.knowledge.fundamental_inputs import FundamentalInputs
from bolsa_analytics.knowledge.models import Fact, FactSet

# Bandas v1 (documentadas; versionables)
PE_CHEAP = 12.0
PE_FAIR_HIGH = 25.0
PE_EXPENSIVE = 40.0
ROE_STRONG = 0.15
ROE_WEAK = 0.05
ROIC_STRONG = 0.12
GROWTH_STRONG = 0.12
GROWTH_WEAK = 0.0
DEBT_HIGH = 2.0
CURRENT_OK = 1.2
ALTMAN_SAFE = 2.99
ALTMAN_DISTRESS = 1.81
# Beneish M-Score: M > −1.78 → manipulación probable (hard-limit Score_FUND).
BENEISH_MANIPULATION = -1.78
PIOTROSKI_STRONG = 7
PIOTROSKI_WEAK = 3
MCAP_LARGE = 10e9
MCAP_MID = 2e9


def _fid(prefix: str) -> str:
    return f"fact-fund-{prefix}-{uuid4().hex[:8]}"


def _valuation_fact(inp: FundamentalInputs) -> Fact:
    pe = inp.forward_pe if inp.forward_pe is not None else inp.trailing_pe
    refs: dict[str, str] = {}
    if inp.trailing_pe is not None:
        refs["trailingPe"] = str(inp.trailing_pe)
    if inp.forward_pe is not None:
        refs["forwardPe"] = str(inp.forward_pe)
    if inp.fcf_yield is not None:
        refs["fcfYield"] = str(inp.fcf_yield)
    if pe is None:
        return Fact(
            fact_id=_fid("val"),
            key="fund.valuation",
            value="unknown",
            confidence=0.2,
            claim="Valoración desconocida: falta P/E",
        )
    if pe <= 0:
        return Fact(
            fact_id=_fid("val"),
            key="fund.valuation",
            value="distorted",
            confidence=0.5,
            claim=f"P/E no interpretable ({pe:.1f})",
            refs=refs,
        )
    if pe < PE_CHEAP:
        return Fact(
            fact_id=_fid("val"),
            key="fund.valuation",
            value="attractive",
            confidence=0.8,
            claim=f"Valoración atractiva (P/E={pe:.1f} < {PE_CHEAP})",
            refs=refs,
        )
    if pe <= PE_FAIR_HIGH:
        return Fact(
            fact_id=_fid("val"),
            key="fund.valuation",
            value="fair",
            confidence=0.75,
            claim=f"Valoración razonable (P/E={pe:.1f})",
            refs=refs,
        )
    if pe <= PE_EXPENSIVE:
        return Fact(
            fact_id=_fid("val"),
            key="fund.valuation",
            value="rich",
            confidence=0.75,
            claim=f"Valoración exigente (P/E={pe:.1f})",
            refs=refs,
        )
    return Fact(
        fact_id=_fid("val"),
        key="fund.valuation",
        value="expensive",
        confidence=0.85,
        claim=f"Valoración cara (P/E={pe:.1f} > {PE_EXPENSIVE})",
        refs=refs,
    )


def _quality_fact(inp: FundamentalInputs) -> Fact:
    refs: dict[str, str] = {}
    if inp.roe is not None:
        refs["roe"] = str(inp.roe)
    if inp.roic is not None:
        refs["roic"] = str(inp.roic)
    if inp.operating_margin is not None:
        refs["operatingMargin"] = str(inp.operating_margin)

    if inp.roe is None and inp.roic is None and inp.operating_margin is None:
        return Fact(
            fact_id=_fid("qual"),
            key="fund.quality",
            value="unknown",
            confidence=0.2,
            claim="Calidad desconocida: faltan ROE/ROIC/margen",
        )

    score_hints = 0
    n = 0
    if inp.roe is not None:
        n += 1
        if inp.roe >= ROE_STRONG:
            score_hints += 1
        elif inp.roe < ROE_WEAK:
            score_hints -= 1
    if inp.roic is not None:
        n += 1
        if inp.roic >= ROIC_STRONG:
            score_hints += 1
        elif inp.roic < ROE_WEAK:
            score_hints -= 1
    if inp.operating_margin is not None:
        n += 1
        if inp.operating_margin >= 0.15:
            score_hints += 1
        elif inp.operating_margin < 0.05:
            score_hints -= 1

    if score_hints >= 1:
        value, claim = "high", "Calidad de negocio alta"
    elif score_hints <= -1:
        value, claim = "low", "Calidad de negocio baja"
    else:
        value, claim = "average", "Calidad de negocio media"

    return Fact(
        fact_id=_fid("qual"),
        key="fund.quality",
        value=value,
        confidence=0.55 + 0.1 * min(n, 3),
        claim=claim,
        refs=refs or None,
    )


def _growth_fact(inp: FundamentalInputs) -> Fact:
    g = inp.eps_growth if inp.eps_growth is not None else inp.revenue_growth
    refs: dict[str, str] = {}
    if inp.revenue_growth is not None:
        refs["revenueGrowth"] = str(inp.revenue_growth)
    if inp.eps_growth is not None:
        refs["epsGrowth"] = str(inp.eps_growth)
    if g is None:
        return Fact(
            fact_id=_fid("grow"),
            key="fund.growth",
            value="unknown",
            confidence=0.2,
            claim="Crecimiento desconocido: faltan tasas",
        )
    if g >= GROWTH_STRONG:
        return Fact(
            fact_id=_fid("grow"),
            key="fund.growth",
            value="strong",
            confidence=0.8,
            claim=f"Crecimiento fuerte ({g:.1%})",
            refs=refs,
        )
    if g > GROWTH_WEAK:
        return Fact(
            fact_id=_fid("grow"),
            key="fund.growth",
            value="moderate",
            confidence=0.7,
            claim=f"Crecimiento moderado ({g:.1%})",
            refs=refs,
        )
    return Fact(
        fact_id=_fid("grow"),
        key="fund.growth",
        value="weak",
        confidence=0.75,
        claim=f"Crecimiento débil/negativo ({g:.1%})",
        refs=refs,
    )


def _solvency_fact(inp: FundamentalInputs) -> Fact:
    refs: dict[str, str] = {}
    if inp.altman_z is not None:
        refs["altmanZ"] = str(inp.altman_z)
    if inp.piotroski is not None:
        refs["piotroski"] = str(inp.piotroski)
    if inp.beneish_m is not None:
        refs["beneishM"] = str(inp.beneish_m)
    if inp.debt_to_equity is not None:
        refs["debtToEquity"] = str(inp.debt_to_equity)
    if inp.current_ratio is not None:
        refs["currentRatio"] = str(inp.current_ratio)

    if not refs:
        # Proxy débil: large cap ≈ más solvente en ausencia de ratios
        if inp.market_cap is not None:
            refs["marketCap"] = str(inp.market_cap)
            if inp.market_cap >= MCAP_LARGE:
                return Fact(
                    fact_id=_fid("solv"),
                    key="fund.solvency",
                    value="adequate",
                    confidence=0.4,
                    claim="Solvencia proxy: large cap (sin ratios de deuda)",
                    refs=refs,
                )
            if inp.market_cap < MCAP_MID:
                return Fact(
                    fact_id=_fid("solv"),
                    key="fund.solvency",
                    value="uncertain",
                    confidence=0.35,
                    claim="Solvencia incierta: small/mid cap sin ratios",
                    refs=refs,
                )
        return Fact(
            fact_id=_fid("solv"),
            key="fund.solvency",
            value="unknown",
            confidence=0.2,
            claim="Solvencia desconocida",
        )

    if inp.altman_z is not None:
        if inp.altman_z < ALTMAN_DISTRESS:
            return Fact(
                fact_id=_fid("solv"),
                key="fund.solvency",
                value="distress",
                confidence=0.9,
                claim=f"Riesgo de solvencia (Altman Z={inp.altman_z:.2f})",
                refs=refs,
            )

    if inp.beneish_m is not None and inp.beneish_m > BENEISH_MANIPULATION:
        return Fact(
            fact_id=_fid("solv"),
            key="fund.solvency",
            value="distress",
            confidence=0.85,
            claim=(
                f"Riesgo de manipulación (Beneish M={inp.beneish_m:.2f} "
                f"> {BENEISH_MANIPULATION})"
            ),
            refs=refs,
        )

    if inp.altman_z is not None and inp.altman_z >= ALTMAN_SAFE:
        return Fact(
            fact_id=_fid("solv"),
            key="fund.solvency",
            value="strong",
            confidence=0.85,
            claim=f"Solvencia fuerte (Altman Z={inp.altman_z:.2f})",
            refs=refs,
        )

    if inp.piotroski is not None:
        if inp.piotroski >= PIOTROSKI_STRONG:
            return Fact(
                fact_id=_fid("solv"),
                key="fund.solvency",
                value="strong",
                confidence=0.8,
                claim=f"Salud financiera alta (Piotroski={inp.piotroski:.0f})",
                refs=refs,
            )
        if inp.piotroski <= PIOTROSKI_WEAK:
            return Fact(
                fact_id=_fid("solv"),
                key="fund.solvency",
                value="weak",
                confidence=0.8,
                claim=f"Salud financiera baja (Piotroski={inp.piotroski:.0f})",
                refs=refs,
            )

    if inp.debt_to_equity is not None and inp.debt_to_equity > DEBT_HIGH:
        return Fact(
            fact_id=_fid("solv"),
            key="fund.solvency",
            value="levered",
            confidence=0.75,
            claim=f"Apalancamiento alto (D/E={inp.debt_to_equity:.2f})",
            refs=refs,
        )
    if inp.current_ratio is not None and inp.current_ratio < CURRENT_OK:
        return Fact(
            fact_id=_fid("solv"),
            key="fund.solvency",
            value="weak",
            confidence=0.7,
            claim=f"Liquidez corta (current ratio={inp.current_ratio:.2f})",
            refs=refs,
        )

    return Fact(
        fact_id=_fid("solv"),
        key="fund.solvency",
        value="adequate",
        confidence=0.65,
        claim="Solvencia adecuada",
        refs=refs,
    )


def _size_fact(inp: FundamentalInputs) -> Fact:
    if inp.market_cap is None:
        return Fact(
            fact_id=_fid("size"),
            key="fund.size",
            value="unknown",
            confidence=0.2,
            claim="Capitalización desconocida",
        )
    refs = {"marketCap": str(inp.market_cap)}
    if inp.market_cap >= MCAP_LARGE:
        value, claim = "large", f"Large cap (${inp.market_cap/1e9:.1f}B)"
    elif inp.market_cap >= MCAP_MID:
        value, claim = "mid", f"Mid cap (${inp.market_cap/1e9:.1f}B)"
    else:
        value, claim = "small", f"Small cap (${inp.market_cap/1e9:.1f}B)"
    return Fact(
        fact_id=_fid("size"),
        key="fund.size",
        value=value,
        confidence=0.9,
        claim=claim,
        refs=refs,
    )


def build_fundamental_fact_set(
    instrument_id: str,
    inputs: FundamentalInputs | dict,
    *,
    timestamp: str | None = None,
    fact_set_id: str | None = None,
) -> FactSet:
    inp = inputs if isinstance(inputs, FundamentalInputs) else FundamentalInputs.from_dict(inputs)
    ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    facts = (
        _valuation_fact(inp),
        _quality_fact(inp),
        _growth_fact(inp),
        _solvency_fact(inp),
        _size_fact(inp),
    )
    return FactSet(
        fact_set_id=fact_set_id or f"FS-FUND-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        timestamp=ts,
        facts=facts,
        source="fundamental_v1",
    )
