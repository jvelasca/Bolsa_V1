"""TradePlan v0 — plan condicional sobre DecisionPackage (ADR-031).

No sustituye el spine: mapea tesis + gates a un estado operativo
(WATCH / ARMED / TRIGGERED / BLOCKED / EXPIRED) y un size por stop estructural.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

TradePlanStatus = Literal["WATCH", "ARMED", "TRIGGERED", "BLOCKED", "EXPIRED"]
TradePlanDirection = Literal["long", "short", "none"]
EntrySetup = Literal["breakout", "pullback", "wyckoff", "none"]
# Ciclo 4.5/4.6 — evidencia SM (interno; no JSON TradePlan).
WyckoffPhaseEvidence = Literal["none", "spring", "reclaim", "sos", "lps"]
WhyNotCode = Literal[
    "fit",
    "freshness",
    "mandate",
    "entry",
    "no_stop",
    "expired",
    "orphan",
    "rr",
    "regime",
]


@dataclass(frozen=True, slots=True)
class TradePlan:
    """Plan operativo mínimo (v0)."""

    decision_id: str
    instrument_id: str
    direction: TradePlanDirection
    status: TradePlanStatus
    quantity: float
    risk_pct: float
    why_not: tuple[str, ...]
    execution_allowed: bool
    opportunity_score: float | None = None
    actionability: float | None = None
    entry: float | None = None
    structural_stop: float | None = None
    expires_at: str | None = None
    entry_setup: EntrySetup = "none"

    def to_dict(self) -> dict[str, object]:
        return {
            "decisionId": self.decision_id,
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "status": self.status,
            "quantity": self.quantity,
            "riskPct": self.risk_pct,
            "whyNot": list(self.why_not),
            "executionAllowed": self.execution_allowed,
            "opportunityScore": self.opportunity_score,
            "actionability": self.actionability,
            "entry": self.entry,
            "structuralStop": self.structural_stop,
            "expiresAt": self.expires_at,
            "entrySetup": self.entry_setup,
        }


def compliance_fit_ok(compliance_check: object) -> bool:
    """True unless ``compliance_check`` is a dict with ``passed is False``.

    Propose no re-ejecuta cesta: un veto de Fit ya materializado en el package
    marca el plan BLOCKED; ausencia o forma rara no inventa un fail.
    """
    return not (isinstance(compliance_check, dict) and compliance_check.get("passed") is False)


# Ciclo 4.0 — stop estructural.
ATR_MULT = 1.5
SWING_LOOKBACK = 10

# Ciclo 4.1 — Golden G: no nuevos longs en régimen adverso (TradePlan only).
NO_NEW_LONGS_REGIMES = frozenset({"risk_off", "crisis"})

# Ciclo 4.2 — EntrySetup (refina entry_ready).
BREAKOUT_LOOKBACK = 20
PULLBACK_ATR_BAND = 1.0
WYCKOFF_SPRING = 5
WYCKOFF_PRIOR = 10
# Ciclo 4.4 — reclaim formal: close ≥ spring ± k×ATR ó fuera del rango spring.
WYCKOFF_RECLAIM_ATR_K = 0.25
# Ciclo 4.5 — LPS thin: close ≥ pullback extreme ± eps×ATR (0 = solo ≥/≤ extreme).
WYCKOFF_LPS_ATR_EPS = 0.0
# Ciclo 4.6 — scan lookback (cerradas); last aparte. Cabe en propose bar_limit=120.
WYCKOFF_LOOKBACK = 40

# Ciclo 4.3 — ARMED actionability (entre WATCH entry 0.4 y TRIGGERED ~0.95).
ARMED_ACTIONABILITY = 0.7

# Ciclo 4.7 — clave runtime en DecisionSession (no TradePlan / no contract:gen).
WYCKOFF_SPRING_ANCHOR_KEY = "wyckoffSpringAnchor"


@dataclass(frozen=True, slots=True)
class _WyckoffSpringLocate:
    """Spring vivo localizado en lookback (4.6/4.7). No se serializa en TradePlan."""

    prior: tuple[object, ...]
    spring: tuple[object, ...]
    close: float
    ice: float


def no_new_longs_blocks(*, action: str, market_regime: str | None) -> bool:
    """True si long y régimen en risk_off/crisis. Sin régimen → no veta (D6)."""
    if market_regime is None or market_regime not in NO_NEW_LONGS_REGIMES:
        return False
    return _direction_from_action(action) == "long"


def _finite_positive(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:  # NaN or non-positive
        return None
    return number


def _bar_px(bar: object, attr: str) -> float | None:
    return _finite_positive(getattr(bar, attr, None))


def _sma_closes(bars: Sequence[object]) -> float | None:
    closes = [_bar_px(bar, "close") for bar in bars]
    valid = [c for c in closes if c is not None]
    if len(valid) != len(bars) or not valid:
        return None
    return sum(valid) / len(valid)


def _is_breakout(*, direction: TradePlanDirection, bars: Sequence[object]) -> bool:
    need = BREAKOUT_LOOKBACK + 1
    if len(bars) < need:
        return False
    window = bars[-(need):-1]
    last = bars[-1]
    close = _bar_px(last, "close")
    if close is None:
        return False
    if direction == "long":
        highs = [_bar_px(bar, "high") for bar in window]
        valid = [h for h in highs if h is not None]
        return bool(valid) and close > max(valid)
    lows = [_bar_px(bar, "low") for bar in window]
    valid = [low for low in lows if low is not None]
    return bool(valid) and close < min(valid)


def _is_pullback(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    atr: float | None,
) -> bool:
    atr_val = _finite_positive(atr)
    if atr_val is None or len(bars) < BREAKOUT_LOOKBACK + 1:
        return False
    window = bars[-(BREAKOUT_LOOKBACK + 1) : -1]
    close = _bar_px(bars[-1], "close")
    sma = _sma_closes(window)
    if close is None or sma is None:
        return False
    band = PULLBACK_ATR_BAND * atr_val
    if direction == "long":
        return sma <= close <= sma + band
    return sma - band <= close <= sma


def _wyckoff_windows(
    bars: Sequence[object],
) -> tuple[Sequence[object], Sequence[object], float] | None:
    """Ventana fija prior+spring+last (compat / tests cortos). Preferir locator 4.6."""
    need = WYCKOFF_SPRING + WYCKOFF_PRIOR + 1
    if len(bars) < need:
        return None
    closed = bars[-need:-1]
    prior = closed[:WYCKOFF_PRIOR]
    spring = closed[WYCKOFF_PRIOR:]
    close = _bar_px(bars[-1], "close")
    if close is None:
        return None
    return prior, spring, close


def _spring_pattern_at(
    *,
    direction: TradePlanDirection,
    prior: Sequence[object],
    spring: Sequence[object],
) -> bool:
    """Spring: low (long) bajo el mínimo prior, o high (short) sobre el máximo prior."""
    if direction == "long":
        prior_lows = [_bar_px(bar, "low") for bar in prior]
        spring_lows = [_bar_px(bar, "low") for bar in spring]
        p_ok = [v for v in prior_lows if v is not None]
        s_ok = [v for v in spring_lows if v is not None]
        return bool(p_ok and s_ok) and min(s_ok) < min(p_ok)
    prior_highs = [_bar_px(bar, "high") for bar in prior]
    spring_highs = [_bar_px(bar, "high") for bar in spring]
    p_ok = [v for v in prior_highs if v is not None]
    s_ok = [v for v in spring_highs if v is not None]
    return bool(p_ok and s_ok) and max(s_ok) > max(p_ok)


def _ice_from_spring(
    *,
    direction: TradePlanDirection,
    spring: Sequence[object],
) -> float | None:
    if direction == "long":
        lows = [v for v in (_bar_px(bar, "low") for bar in spring) if v is not None]
        return min(lows) if lows else None
    highs = [v for v in (_bar_px(bar, "high") for bar in spring) if v is not None]
    return max(highs) if highs else None


def _ice_broken(
    *,
    direction: TradePlanDirection,
    ice: float,
    post_bars: Sequence[object],
) -> bool:
    """True si algún extreme posterior atraviesa el hielo (estructura muerta)."""
    if direction == "long":
        for bar in post_bars:
            low = _bar_px(bar, "low")
            if low is not None and low <= ice:
                return True
        return False
    for bar in post_bars:
        high = _bar_px(bar, "high")
        if high is not None and high >= ice:
            return True
    return False


def _locate_wyckoff_spring(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    ice_target: float | None = None,
) -> _WyckoffSpringLocate | None:
    """Ciclo 4.6: spring vivo más reciente en lookback.

    Escanea de más reciente a más antigua. Si el primer candidato aceptado
    tiene hielo roto → None (no resucita springs más viejos).
    Con ``ice_target`` (4.7): solo acepta springs con ese hielo (binding).
    """
    need = WYCKOFF_PRIOR + WYCKOFF_SPRING + 1
    if direction == "none" or len(bars) < need:
        return None
    close = _bar_px(bars[-1], "close")
    if close is None:
        return None
    closed = list(bars[:-1])
    scan = closed[-WYCKOFF_LOOKBACK:] if len(closed) > WYCKOFF_LOOKBACK else closed
    win = WYCKOFF_PRIOR + WYCKOFF_SPRING
    if len(scan) < win:
        return None
    for spring_end in range(len(scan), win - 1, -1):
        start = spring_end - win
        prior = scan[start : start + WYCKOFF_PRIOR]
        spring = scan[start + WYCKOFF_PRIOR : spring_end]
        if not _spring_pattern_at(direction=direction, prior=prior, spring=spring):
            continue
        ice = _ice_from_spring(direction=direction, spring=spring)
        if ice is None:
            continue
        if ice_target is not None and ice != ice_target:
            continue
        # Hielo: solo cerradas posteriores. Last wick bajo ice → LPS false, no mata locate.
        if _ice_broken(direction=direction, ice=ice, post_bars=scan[spring_end:]):
            return None
        return _WyckoffSpringLocate(
            prior=tuple(prior),
            spring=tuple(spring),
            close=close,
            ice=ice,
        )
    return None


def parse_wyckoff_spring_anchor(raw: object) -> dict[str, object] | None:
    """Normaliza anchor de sesión cognitiva. Forma rara → None (fail-closed)."""
    if not isinstance(raw, dict):
        return None
    direction = raw.get("direction")
    if direction not in ("long", "short"):
        return None
    ice = _finite_positive(raw.get("ice"))
    spring_low = _finite_positive(raw.get("springLow"))
    spring_high = _finite_positive(raw.get("springHigh"))
    if ice is None or spring_low is None or spring_high is None:
        return None
    out: dict[str, object] = {
        "direction": direction,
        "ice": ice,
        "springLow": spring_low,
        "springHigh": spring_high,
    }
    phase = raw.get("phase")
    if phase in ("none", "spring", "reclaim", "sos", "lps"):
        out["phase"] = phase
    return out


def snapshot_wyckoff_spring_anchor(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    atr: float | None = None,
    prior: dict[str, object] | None = None,
) -> dict[str, object] | None:
    """Ciclo 4.7: foto del spring resuelto para ``DecisionSession.runtime``."""
    locate = _resolve_wyckoff_spring(direction=direction, bars=bars, prior=prior)
    if locate is None:
        return None
    spring_lows = [v for v in (_bar_px(bar, "low") for bar in locate.spring) if v is not None]
    spring_highs = [v for v in (_bar_px(bar, "high") for bar in locate.spring) if v is not None]
    if not spring_lows or not spring_highs:
        return None
    return {
        "direction": direction,
        "ice": locate.ice,
        "springLow": min(spring_lows),
        "springHigh": max(spring_highs),
        "phase": _wyckoff_phase_evidence(
            direction=direction, bars=bars, atr=atr, prior=prior
        ),
    }


def _resolve_wyckoff_spring(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    prior: dict[str, object] | None = None,
) -> _WyckoffSpringLocate | None:
    """Ciclo 4.7: prior bound (mismo ice) si vivo; si hielo roto → None; sin prior → 4.6.

    No cae a locate genérico tras prior muerto (no resucita). No inventa spring
    si el bound ya no está en el lookback.
    """
    if direction == "none":
        return None
    anchor = parse_wyckoff_spring_anchor(prior) if prior is not None else None
    if anchor is None:
        return _locate_wyckoff_spring(direction=direction, bars=bars)
    if anchor["direction"] != direction:
        return None
    ice = float(anchor["ice"])  # type: ignore[arg-type]
    return _locate_wyckoff_spring(direction=direction, bars=bars, ice_target=ice)


def _detect_wyckoff_spring(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    prior: dict[str, object] | None = None,
) -> bool:
    """Spring vivo (4.6 scan o 4.7 bound)."""
    return _resolve_wyckoff_spring(direction=direction, bars=bars, prior=prior) is not None


def _is_wyckoff_reclaim(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    atr: float | None = None,
    prior: dict[str, object] | None = None,
) -> bool:
    """Ciclo 4.4/4.6/4.7: spring resuelto + reclaim estricto (k×ATR o fuera del rango spring)."""
    locate = _resolve_wyckoff_spring(direction=direction, bars=bars, prior=prior)
    if locate is None:
        return False
    spring = locate.spring
    close = locate.close
    atr_val = _finite_positive(atr)
    if direction == "long":
        spring_highs = [v for v in (_bar_px(bar, "high") for bar in spring) if v is not None]
        if not spring_highs:
            return False
        if close <= locate.ice:
            return False
        atr_ok = atr_val is not None and close >= locate.ice + WYCKOFF_RECLAIM_ATR_K * atr_val
        range_ok = close > max(spring_highs)
        return atr_ok or range_ok
    spring_lows = [v for v in (_bar_px(bar, "low") for bar in spring) if v is not None]
    if not spring_lows:
        return False
    if close >= locate.ice:
        return False
    atr_ok = atr_val is not None and close <= locate.ice - WYCKOFF_RECLAIM_ATR_K * atr_val
    range_ok = close < min(spring_lows)
    return atr_ok or range_ok


def _detect_wyckoff_sos(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    prior: dict[str, object] | None = None,
) -> bool:
    """SOS etiqueta/evidencia: close fuera del máximo spring o del prior (long) / espejo short.

    No cambia EntrySetup ni exige entry_ready (D2/D4).
    """
    locate = _resolve_wyckoff_spring(direction=direction, bars=bars, prior=prior)
    if locate is None:
        return False
    prior_bars, spring, close = locate.prior, locate.spring, locate.close
    if direction == "long":
        highs = [_bar_px(bar, "high") for bar in (*prior_bars, *spring)]
        valid = [v for v in highs if v is not None]
        return bool(valid) and close > max(valid)
    lows = [_bar_px(bar, "low") for bar in (*prior_bars, *spring)]
    valid = [v for v in lows if v is not None]
    return bool(valid) and close < min(valid)


def _detect_wyckoff_lps(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    atr: float | None = None,
    prior: dict[str, object] | None = None,
) -> bool:
    """LPS etiqueta: pullback sobre hielo (long) / bajo techo (short) tras reclaim formal.

    Sobre spring resuelto (4.6/4.7). Sin reclaim → False. No fuerza EntrySetup (D2).
    """
    if not _is_wyckoff_reclaim(direction=direction, bars=bars, atr=atr, prior=prior):
        return False
    locate = _resolve_wyckoff_spring(direction=direction, bars=bars, prior=prior)
    if locate is None:
        return False
    close = locate.close
    atr_val = _finite_positive(atr)
    eps = WYCKOFF_LPS_ATR_EPS * atr_val if atr_val is not None else 0.0
    if direction == "long":
        last_low = _bar_px(bars[-1], "low")
        if last_low is None or last_low <= locate.ice:
            return False
        return close >= last_low + eps
    last_high = _bar_px(bars[-1], "high")
    if last_high is None or last_high >= locate.ice:
        return False
    return close <= last_high - eps


def _wyckoff_phase_evidence(
    *,
    direction: TradePlanDirection,
    bars: Sequence[object],
    atr: float | None = None,
    prior: dict[str, object] | None = None,
) -> WyckoffPhaseEvidence:
    """SM (4.6/4.7): spring → reclaim → sos? → lps? Sobre spring resuelto.

    Interno / tests / runtime sesión. No se expone en TradePlan JSON (D4).
    """
    if direction == "none" or _resolve_wyckoff_spring(
        direction=direction, bars=bars, prior=prior
    ) is None:
        return "none"
    if not _is_wyckoff_reclaim(direction=direction, bars=bars, atr=atr, prior=prior):
        return "spring"
    if _detect_wyckoff_lps(direction=direction, bars=bars, atr=atr, prior=prior):
        return "lps"
    if _detect_wyckoff_sos(direction=direction, bars=bars, prior=prior):
        return "sos"
    return "reclaim"


def classify_entry_setup(
    *,
    action: str,
    bars: Sequence[object] | None = None,
    atr: float | None = None,
    wyckoff_prior: dict[str, object] | None = None,
) -> EntrySetup:
    """Ciclo 4.2–4.7: breakout > pullback > wyckoff > none. Sin barras → none."""
    direction = _direction_from_action(action)
    if direction == "none" or bars is None:
        return "none"
    if _is_breakout(direction=direction, bars=bars):
        return "breakout"
    if _is_pullback(direction=direction, bars=bars, atr=atr):
        return "pullback"
    # SOS/LPS son evidencia interna; no fuerzan EntrySetup (4.4 D2 / 4.5 D2).
    if _is_wyckoff_reclaim(
        direction=direction, bars=bars, atr=atr, prior=wyckoff_prior
    ):
        return "wyckoff"
    return "none"


def compute_structural_stop(
    *,
    action: str,
    entry: float | None,
    atr: float | None = None,
    bars: Sequence[object] | None = None,
) -> float | None:
    """Stop más lejano de ATR×1.5 y swing de 10 barras cerradas.

    No se acerca el stop para caber en el riesgo: se elige el candidato más
    lejos de ``entry`` (min long / max short). Sin candidatos válidos → None.
    """
    if entry is None or entry <= 0:
        return None
    direction = _direction_from_action(action)
    if direction == "none":
        return None

    candidates: list[float] = []
    atr_val = _finite_positive(atr)
    if atr_val is not None:
        if direction == "long":
            atr_stop = entry - ATR_MULT * atr_val
            if atr_stop > 0 and atr_stop < entry:
                candidates.append(atr_stop)
        else:
            atr_stop = entry + ATR_MULT * atr_val
            if atr_stop > entry:
                candidates.append(atr_stop)

    if bars is not None and len(bars) >= SWING_LOOKBACK + 1:
        window = bars[-(SWING_LOOKBACK + 1) : -1]
        if direction == "long":
            lows = [_bar_px(bar, "low") for bar in window]
            valid = [low for low in lows if low is not None and low < entry]
            if valid:
                candidates.append(min(valid))
        else:
            highs = [_bar_px(bar, "high") for bar in window]
            valid = [high for high in highs if high is not None and high > entry]
            if valid:
                candidates.append(max(valid))

    if not candidates:
        return None
    return min(candidates) if direction == "long" else max(candidates)


def entry_ready_from_ta(
    *,
    action: str,
    bias: str | None,
    exhaustion: bool = False,
    entry_setup: EntrySetup = "none",
) -> bool:
    """Ciclo 4.0+4.2: bias alineado, sin exhaustion, setup ≠ none."""
    if exhaustion or entry_setup == "none":
        return False
    if action == "recommend_long":
        return bias == "bullish"
    if action == "recommend_short":
        return bias == "bearish"
    return False


def build_v0_trade_plan_dict(
    *,
    decision_id: str,
    instrument_id: str,
    action: str,
    compliance_check: object = None,
    entry: float | None,
    opportunity_score: float | None,
    expires_at: str | None,
    expired: bool = False,
    atr: float | None = None,
    bars: Sequence[object] | None = None,
    bias: str | None = None,
    exhaustion: bool = False,
    equity: float = 0.0,
    risk_pct: float = 0.5,
    market_regime: str | None = None,
    wyckoff_prior: dict[str, object] | None = None,
) -> dict[str, object]:
    """TradePlan persistible (PLAN layer; ranking ≠ BUY).

    Freshness/mandate quedan True: esos gates viven en confirm ``check_opening``.
    Sin ATR/barras/bias (rebuild confirm) → ``WATCH`` / ``no_stop`` o ``entry``.
    Sin ``market_regime`` → no inventa veto ``regime`` (Ciclo 4.1 D6).
    ``wyckoff_prior`` (Ciclo 4.7): anchor de sesión; sin barras → classify none (D8).
    """
    structural_stop = compute_structural_stop(action=action, entry=entry, atr=atr, bars=bars)
    setup = classify_entry_setup(
        action=action, bars=bars, atr=atr, wyckoff_prior=wyckoff_prior
    )
    plan = build_trade_plan(
        decision_id=decision_id,
        instrument_id=instrument_id,
        action=action,
        fit_ok=compliance_fit_ok(compliance_check),
        freshness_ok=True,
        mandate_ok=True,
        expired=expired,
        entry_ready=entry_ready_from_ta(
            action=action,
            bias=bias,
            exhaustion=exhaustion,
            entry_setup=setup,
        ),
        entry=entry,
        structural_stop=structural_stop,
        equity=equity,
        risk_pct=risk_pct,
        opportunity_score=opportunity_score,
        expires_at=expires_at,
        market_regime=market_regime,
        entry_setup=setup,
    )
    return plan.to_dict()


def compute_risk_size(
    *,
    equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
) -> float:
    """Size = (equity × risk%) / |entry − stop|. 0 si stop inválido o equity≤0."""
    if equity <= 0 or risk_pct <= 0 or entry <= 0:
        return 0.0
    per_share = abs(entry - stop)
    if per_share <= 0:
        return 0.0
    return (equity * (risk_pct / 100.0)) / per_share


def _direction_from_action(action: str) -> TradePlanDirection:
    if action == "recommend_long":
        return "long"
    if action == "recommend_short":
        return "short"
    return "none"


def build_trade_plan(
    *,
    decision_id: str,
    instrument_id: str,
    action: str,
    fit_ok: bool = True,
    freshness_ok: bool = True,
    mandate_ok: bool = True,
    expired: bool = False,
    entry_ready: bool = False,
    entry: float | None = None,
    structural_stop: float | None = None,
    equity: float = 0.0,
    risk_pct: float = 0.5,
    opportunity_score: float | None = None,
    expires_at: str | None = None,
    market_regime: str | None = None,
    entry_setup: EntrySetup = "none",
) -> TradePlan:
    """Mapper determinista DecisionPackage + gates → TradePlan v0.

    Golden A: entry_ready + stop válido + gates OK → TRIGGERED.
    Golden B: stop OK + setup none + !entry_ready → WATCH entry.
    Ciclo 4.3: stop OK + setup ≠ none + !entry_ready → ARMED.
    Golden C: fit_ok False → BLOCKED.
    Golden G: long + risk_off/crisis → BLOCKED (why regime).
    Golden H: expired → EXPIRED.
    """
    why: list[str] = []
    direction = _direction_from_action(action)
    stop_valid = (
        structural_stop is not None
        and entry is not None
        and entry > 0
        and (
            (direction == "long" and structural_stop < entry)
            or (direction == "short" and structural_stop > entry)
        )
    )

    def _mk(
        *,
        status: TradePlanStatus,
        quantity: float,
        why_not: tuple[str, ...],
        execution_allowed: bool,
        actionability: float,
    ) -> TradePlan:
        return TradePlan(
            decision_id=decision_id,
            instrument_id=instrument_id,
            direction=direction,
            status=status,
            quantity=quantity,
            risk_pct=risk_pct,
            why_not=why_not,
            execution_allowed=execution_allowed,
            opportunity_score=opportunity_score,
            actionability=actionability,
            entry=entry,
            structural_stop=structural_stop,
            expires_at=expires_at,
            entry_setup=entry_setup,
        )

    if expired:
        why.append("expired")
        return _mk(
            status="EXPIRED",
            quantity=0.0,
            why_not=tuple(why),
            execution_allowed=False,
            actionability=0.0,
        )

    if no_new_longs_blocks(action=action, market_regime=market_regime):
        why.append("regime")
    if not fit_ok:
        why.append("fit")
    if not freshness_ok:
        why.append("freshness")
    if not mandate_ok:
        why.append("mandate")
    if why:
        return _mk(
            status="BLOCKED",
            quantity=0.0,
            why_not=tuple(why),
            execution_allowed=False,
            actionability=0.0,
        )

    if action in {"wait", "reduce", "exit_hint"} or direction == "none":
        why.append("entry")
        return _mk(
            status="WATCH",
            quantity=0.0,
            why_not=tuple(why),
            execution_allowed=False,
            actionability=0.2,
        )

    if not stop_valid:
        why.append("no_stop")
        return _mk(
            status="WATCH",
            quantity=0.0,
            why_not=tuple(why),
            execution_allowed=False,
            actionability=0.3,
        )

    if not entry_ready:
        why.append("entry")
        # Ciclo 4.3: stop + setup clasificado sin fuego → ARMED; setup none → WATCH.
        if entry_setup != "none":
            return _mk(
                status="ARMED",
                quantity=0.0,
                why_not=tuple(why),
                execution_allowed=False,
                actionability=ARMED_ACTIONABILITY,
            )
        return _mk(
            status="WATCH",
            quantity=0.0,
            why_not=tuple(why),
            execution_allowed=False,
            actionability=0.4,
        )

    qty = compute_risk_size(
        equity=equity,
        risk_pct=risk_pct,
        entry=float(entry),
        stop=float(structural_stop),
    )
    return _mk(
        status="TRIGGERED",
        quantity=qty,
        why_not=(),
        execution_allowed=qty > 0,
        actionability=0.95 if qty > 0 else 0.0,
    )
