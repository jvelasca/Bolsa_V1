"""FIE F3 — Composite Investment Score (`composite_score_v1_1`).

Fusión auditable de piernas:
  Technical · Fundamental (Score_FUND) · Risk Profile · Liquidity ·
  Market Regime · Portfolio Constraints (stub / not_evaluated).

Python calcula; LLM no recalcula. ``paperDUnlocked=True`` documenta que el
ranking existe para desbloquear ingeniería de Paper D (no despliega paper).

v1.1 (2026-08-01): buckets ADV/mcap calibrados con audit live US+IBEX.
"""

from __future__ import annotations

from typing import Any, Literal

from bolsa_analytics.cognitive.weight_rules import (
    WEIGHT_RULES_VERSION,
    HorizonHint,
    MarketRegime,
    resolve_weight_rules,
)
from bolsa_analytics.knowledge.fundamental_assessment import build_fundamental_assessment
from bolsa_analytics.knowledge.fundamental_card import fund_score_to_display_100
from bolsa_analytics.knowledge.fundamental_inputs import FundamentalInputs
from bolsa_analytics.knowledge.indice_operativo import compute_indice_operativo
from bolsa_analytics.knowledge.models import TechnicalInputs
from bolsa_analytics.knowledge.technical_assessment import build_technical_assessment

COMPOSITE_SCHEMA_VERSION = "composite_card_v1"
COMPOSITE_SCORE_VERSION = "composite_score_v1_1"

# Piernas extra (no en WeightRules TA/FUND/MACRO); bump COMPOSITE_SCORE_VERSION si cambian.
W_LIQUIDITY = 0.08
W_RISK_PROFILE = 0.07

DataConfidence = Literal["HIGH", "MEDIUM", "LOW"]


def _clamp_score(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def liquidity_score_from_mcap(market_cap: float | None) -> tuple[float | None, str]:
    """Proxy de liquidez por capitalización (fallback sin ADV).

    Calibrado 2026-08-01 (US mega + IBEX large): AAPL/MSFT ≥500B ·
    SAN/JNJ ≥100B · ACS ~30B · mid/small debajo.
    """
    if market_cap is None or market_cap <= 0:
        return None, "mcap_missing"
    if market_cap >= 5e11:
        return 0.8, "mcap_mega"
    if market_cap >= 1e11:
        return 0.55, "mcap_large"
    if market_cap >= 2e10:
        return 0.3, "mcap_mid_large"
    if market_cap >= 5e9:
        return 0.1, "mcap_mid"
    if market_cap >= 1e9:
        return -0.2, "mcap_small"
    return -0.55, "mcap_micro"


def liquidity_score_from_adv_usd(adv_usd: float | None) -> tuple[float | None, str]:
    """Liquidez por ADV notional USD/día (`adv_usd_v1` input · buckets v1.1).

    Calibrado 2026-08-01: AAPL/MSFT ~17B ADV · JNJ ~2B · IBEX large ~100–300M ·
    ACS ~51M. Antes todo ≥50M caía en ``adv_very_high`` (techo bajo).
    """
    if adv_usd is None or adv_usd <= 0:
        return None, "adv_missing"
    if adv_usd >= 1e9:
        return 0.85, "adv_mega"
    if adv_usd >= 1e8:
        return 0.65, "adv_very_high"
    if adv_usd >= 2e7:
        return 0.4, "adv_high"
    if adv_usd >= 5e6:
        return 0.15, "adv_medium"
    if adv_usd >= 1e6:
        return -0.15, "adv_low"
    return -0.55, "adv_very_low"


def resolve_liquidity_score(
    *,
    adv_usd: float | None,
    market_cap: float | None,
) -> tuple[float | None, str]:
    """Prefiere ADV; si falta, proxy mcap. Sin blend (ADV es señal de trading)."""
    liq, method = liquidity_score_from_adv_usd(adv_usd)
    if liq is not None:
        return liq, method
    return liquidity_score_from_mcap(market_cap)


def regime_to_score(regime: MarketRegime) -> float:
    return {
        "risk_on": 0.45,
        "neutral": 0.0,
        "risk_off": -0.4,
        "crisis": -0.85,
        "uncertain": -0.15,
    }.get(regime, 0.0)


def risk_profile_score(
    *,
    size_hint: float,
    veto_new_long: bool,
    risk_tolerance: str | None,
) -> float:
    """Modulador de perfil (stub v1): size_hint + veto + tolerancia declarada."""
    base = _clamp_score((float(size_hint) - 0.5) * 1.2)
    if veto_new_long:
        base = min(base, -0.35)
    tol = (risk_tolerance or "").strip().lower()
    if tol in {"conservative", "low"}:
        base -= 0.15
    elif tol in {"aggressive", "high"}:
        base += 0.1
    return round(_clamp_score(base), 4)


def _fuse(
    scored: dict[str, float],
    weights: dict[str, float],
) -> tuple[float | None, dict[str, float]]:
    active = {k: v for k, v in scored.items() if k in weights and weights[k] > 0}
    if not active:
        return None, {}
    total_w = sum(weights[k] for k in active)
    if total_w <= 0:
        return None, {}
    applied = {k: weights[k] / total_w for k in active}
    combined = sum(active[k] * applied[k] for k in active)
    return round(_clamp_score(combined), 4), {k: round(v, 4) for k, v in applied.items()}


def _confidence(legs_ok: int, legs_total: int, *, fund_distress: bool) -> DataConfidence:
    if fund_distress:
        return "LOW"
    ratio = legs_ok / max(1, legs_total)
    if ratio >= 0.7:
        return "HIGH"
    if ratio >= 0.4:
        return "MEDIUM"
    return "LOW"


def build_composite_card(
    *,
    instrument_id: str,
    ticker: str,
    fundamentals: dict[str, Any] | None,
    technical: TechnicalInputs | dict | None = None,
    technical_score: float | None = None,
    technical_method: str | None = None,
    horizon: HorizonHint = "swing",
    regime: MarketRegime = "neutral",
    risk_tolerance: str | None = None,
) -> dict[str, Any]:
    """
    Ensambla CompositeCardDto (camelCase).

    Prioridad TA: ``technical`` (Score_TA) > ``technical_score`` override
    (p.ej. rating 0–100 mapeado) > missing.
    """
    warnings: list[str] = []
    narrative: list[str] = []
    wr = resolve_weight_rules(horizon=horizon, regime=regime)

    # --- Fundamental ---
    score_fund: float | None = None
    fund_method: str | None = None
    fund_distress = False
    fund_source = None
    if isinstance(fundamentals, dict) and fundamentals:
        fund_source = fundamentals.get("sourceVersion")
        inputs = FundamentalInputs.from_dict(fundamentals)
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
            _assess, _fs, score_result = build_fundamental_assessment(
                instrument_id, inputs
            )
            score_fund = float(score_result.score)
            fund_method = score_result.score_version
            fund_distress = bool(score_result.distress)
            narrative.extend(list(score_result.claims)[:4])
            if fund_distress:
                warnings.append("Score_FUND en distress — Composite con confianza baja.")
        else:
            warnings.append("Sin señales fundamentales suficientes.")
    else:
        warnings.append("Sin snapshot fundamentals.")

    # --- Technical ---
    score_ta: float | None = None
    ta_method = technical_method
    if technical is not None:
        _ta_assess, _ta_fs, ta_result = build_technical_assessment(
            instrument_id, technical
        )
        score_ta = float(ta_result.score)
        ta_method = "score_ta_v1"
        if ta_result.exhaustion:
            warnings.append("Exhaustion TA detectada.")
    elif technical_score is not None:
        score_ta = _clamp_score(float(technical_score))
        ta_method = ta_method or "technical_score_override"

    # --- Other legs ---
    mcap = fundamentals.get("marketCap") if isinstance(fundamentals, dict) else None
    adv_raw = fundamentals.get("advUsd") if isinstance(fundamentals, dict) else None
    try:
        mcap_f = float(mcap) if mcap is not None else None
    except (TypeError, ValueError):
        mcap_f = None
    try:
        adv_f = float(adv_raw) if adv_raw is not None else None
    except (TypeError, ValueError):
        adv_f = None
    liq_score, liq_method = resolve_liquidity_score(adv_usd=adv_f, market_cap=mcap_f)
    regime_score = regime_to_score(regime)
    risk_score = risk_profile_score(
        size_hint=wr.size_hint,
        veto_new_long=wr.veto_new_long,
        risk_tolerance=risk_tolerance,
    )

    # Pesos brutos (news no vota en Composite v1; portfolio stub weight 0)
    raw_weights = {
        "technical": wr.w_ta,
        "fundamental": wr.w_fund,
        "marketRegime": wr.w_macro,
        "liquidity": W_LIQUIDITY,
        "riskProfile": W_RISK_PROFILE,
        "portfolioConstraints": 0.0,
    }
    scored: dict[str, float] = {}
    if score_ta is not None:
        scored["technical"] = score_ta
    if score_fund is not None:
        scored["fundamental"] = score_fund
    scored["marketRegime"] = regime_score
    if liq_score is not None:
        scored["liquidity"] = liq_score
    scored["riskProfile"] = risk_score

    combined, applied = _fuse(scored, raw_weights)

    def leg(
        key: str,
        label: str,
        score: float | None,
        *,
        status: str,
        method: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "score": score,
            "weight": applied.get(key, 0.0),
            "status": status,
            "method": method,
            "note": note,
        }

    legs = [
        leg(
            "technical",
            "Technical",
            score_ta,
            status="ok" if score_ta is not None else "missing",
            method=ta_method,
            note=None if score_ta is not None else "Sin barras/inputs TA",
        ),
        leg(
            "fundamental",
            "Fundamental",
            score_fund,
            status="ok" if score_fund is not None else "missing",
            method=fund_method,
        ),
        leg(
            "riskProfile",
            "Risk Profile",
            risk_score,
            status="stub",
            method="risk_profile_stub_v1",
            note="size_hint + veto + tolerancia (no optimizador)",
        ),
        leg(
            "liquidity",
            "Liquidity",
            liq_score,
            status="ok" if liq_score is not None else "missing",
            method=liq_method,
            note="Proxy por marketCap (no ADV/spread)",
        ),
        leg(
            "marketRegime",
            "Market Regime",
            regime_score,
            status="ok",
            method=f"regime_{regime}",
        ),
        leg(
            "portfolioConstraints",
            "Portfolio Constraints",
            None,
            status="not_evaluated",
            method=None,
            note="Stub Composite: Fit de cesta vive en check_opening (PortfolioFit), no en esta pata",
        ),
    ]

    legs_ok = sum(1 for L in legs if L["status"] == "ok")
    conf = _confidence(legs_ok, 5, fund_distress=fund_distress)  # 5 votantes potenciales
    coverage = round(legs_ok / 5.0, 3)

    if wr.veto_new_long:
        warnings.append("Régimen con veto_new_long (WeightRules).")

    narrative.insert(
        0,
        f"Composite {COMPOSITE_SCORE_VERSION}: combined={combined} "
        f"horizon={horizon} regime={regime}",
    )

    score_display_100 = fund_score_to_display_100(combined)
    return {
        "schemaVersion": COMPOSITE_SCHEMA_VERSION,
        "instrumentId": instrument_id,
        "ticker": ticker,
        "combinedScore": combined,
        "scoreDisplay100": score_display_100,
        "indiceOperativo": compute_indice_operativo(
            score_display_100, distress=fund_distress
        ),
        "legs": legs,
        "weights": {
            "ta": round(wr.w_ta, 4),
            "fund": round(wr.w_fund, 4),
            "macro": round(wr.w_macro, 4),
            "news": round(wr.w_news, 4),
            "liquidity": W_LIQUIDITY,
            "riskProfile": W_RISK_PROFILE,
            "horizon": wr.horizon,
            "regime": wr.regime,
            "rationale": wr.rationale,
            "sizeHint": wr.size_hint,
            "vetoNewLong": wr.veto_new_long,
            "weightRulesVersion": WEIGHT_RULES_VERSION,
        },
        "metadata": {
            "scoreVersion": COMPOSITE_SCORE_VERSION,
            "schemaVersion": COMPOSITE_SCHEMA_VERSION,
            "confidence": conf,
            "coverage": coverage,
            "horizon": horizon,
            "regime": regime,
            "fundSourceVersion": fund_source,
            "technicalMethod": ta_method,
            "paperDUnlocked": True,
        },
        "warnings": warnings,
        "narrativeFacts": narrative[:8],
    }


def _leg_score_display100(legs: Any, key: str) -> int | None:
    if not isinstance(legs, list):
        return None
    for leg in legs:
        if not isinstance(leg, dict) or leg.get("key") != key:
            continue
        raw = leg.get("score")
        if raw is None:
            return None
        try:
            clamped = max(-1.0, min(1.0, float(raw)))
        except (TypeError, ValueError):
            return None
        return int(round(((clamped + 1.0) / 2.0) * 100.0))
    return None


def composite_to_chip(card: dict[str, Any]) -> dict[str, Any]:
    meta = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
    score_display = card.get("scoreDisplay100")
    io = card.get("indiceOperativo")
    if io is None:
        io = compute_indice_operativo(score_display, distress=False)
    return {
        "instrumentId": card.get("instrumentId"),
        "ticker": card.get("ticker"),
        "scoreDisplay100": score_display,
        "indiceOperativo": io,
        "confidence": meta.get("confidence") or "LOW",
        "combinedScore": card.get("combinedScore"),
        "regime": meta.get("regime") or "neutral",
        "paperDUnlocked": bool(meta.get("paperDUnlocked")),
        "technicalDisplay100": _leg_score_display100(card.get("legs"), "technical"),
    }
