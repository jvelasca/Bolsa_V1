"""Outcome de DecisionSession — cierra el ciclo Learning (≠ Memory Gate).

Criterio v1.1 (OUTCOME_CRITERIA_VERSION):
- Evalúa dirección del precio vs action recomendada en la barra D1 +N (horizonte).
- Si aún no hay N barras, mark-to-market con nota premature_mtm.
- hit/miss solo si |return| ≥ banda neutra; wait → skipped.
- No ajusta WeightRules automáticamente (solo métricas para Learning).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Sequence

OUTCOME_CRITERIA_VERSION = "1.1.0"

OutcomeSource = Literal["auto_mark", "manual"]
OutcomeVerdict = Literal["hit", "miss", "neutral", "invalid", "skipped"]

# Barras D1 hacia delante para marcar el desenlace
HORIZON_EVAL_BARS: dict[str, int] = {
    "intraday": 1,
    "swing": 5,
    "position": 21,
    "long_term": 63,
}

NEUTRAL_BAND_PCT = 0.5  # |return| < 0.5% → neutral


@dataclass(frozen=True, slots=True)
class SessionOutcome:
    criteria_version: str
    source: OutcomeSource
    evaluated_at: str
    horizon: str
    eval_bars: int
    recommended_action: str
    price_at_decision: float | None
    price_at_eval: float | None
    return_pct: float | None
    direction_hit: bool | None
    verdict: OutcomeVerdict
    notes: str | None = None
    mature: bool = True
    bars_elapsed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "criteriaVersion": self.criteria_version,
            "source": self.source,
            "evaluatedAt": self.evaluated_at,
            "horizon": self.horizon,
            "evalBars": self.eval_bars,
            "recommendedAction": self.recommended_action,
            "priceAtDecision": self.price_at_decision,
            "priceAtEval": self.price_at_eval,
            "returnPct": self.return_pct,
            "directionHit": self.direction_hit,
            "verdict": self.verdict,
            "notes": self.notes,
            "mature": self.mature,
            "barsElapsed": self.bars_elapsed,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def eval_bars_for_horizon(horizon: str | None) -> int:
    key = (horizon or "swing").lower().replace("-", "_").replace(" ", "_")
    return HORIZON_EVAL_BARS.get(key, HORIZON_EVAL_BARS["swing"])


def extract_recommended_action(session: dict[str, Any]) -> str:
    rec = session.get("recommendation") or {}
    if isinstance(rec, dict):
        action = rec.get("action")
        if isinstance(action, str) and action:
            return action
    runtime = session.get("runtime") or {}
    if isinstance(runtime, dict):
        pkg = runtime.get("decisionPackage") or {}
        if isinstance(pkg, dict):
            action = pkg.get("action")
            if isinstance(action, str) and action:
                return action
    return "wait"


def extract_decision_price(session: dict[str, Any]) -> float | None:
    rec = session.get("recommendation") or {}
    if isinstance(rec, dict):
        for key in ("suggestedPrice", "price", "lastClose"):
            val = rec.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
    runtime = session.get("runtime") or {}
    if isinstance(runtime, dict):
        for key in ("lastClose", "price"):
            val = runtime.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
    return None


def verdict_from_return(
    *,
    action: str,
    return_pct: float | None,
    neutral_band_pct: float = NEUTRAL_BAND_PCT,
) -> tuple[OutcomeVerdict, bool | None]:
    """Devuelve (verdict, direction_hit)."""
    act = action.lower().strip()
    if act in {"wait", "hold", "none", ""}:
        return "skipped", None
    if return_pct is None:
        return "invalid", None
    if abs(return_pct) < neutral_band_pct:
        return "neutral", None

    is_long = act in {"recommend_long", "buy", "long", "enter_long"}
    is_short = act in {"recommend_short", "sell", "short", "enter_short"}
    if not is_long and not is_short:
        return "invalid", None

    if is_long:
        hit = return_pct > 0
    else:
        hit = return_pct < 0
    return ("hit" if hit else "miss"), hit


def build_outcome_from_prices(
    *,
    action: str,
    horizon: str | None,
    price_at_decision: float | None,
    price_at_eval: float | None,
    source: OutcomeSource = "auto_mark",
    notes: str | None = None,
    evaluated_at: str | None = None,
    mature: bool = True,
    bars_elapsed: int | None = None,
) -> SessionOutcome:
    eval_bars = eval_bars_for_horizon(horizon)
    hz = (horizon or "swing").lower()
    return_pct: float | None = None
    if (
        price_at_decision is not None
        and price_at_eval is not None
        and price_at_decision != 0
    ):
        return_pct = ((price_at_eval - price_at_decision) / price_at_decision) * 100.0

    verdict, direction_hit = verdict_from_return(action=action, return_pct=return_pct)
    if price_at_decision is None or price_at_eval is None:
        if action.lower().strip() not in {"wait", "hold", "none", ""}:
            verdict, direction_hit = "invalid", None

    return SessionOutcome(
        criteria_version=OUTCOME_CRITERIA_VERSION,
        source=source,
        evaluated_at=evaluated_at or _now_iso(),
        horizon=hz,
        eval_bars=eval_bars,
        recommended_action=action,
        price_at_decision=price_at_decision,
        price_at_eval=price_at_eval,
        return_pct=round(return_pct, 4) if return_pct is not None else None,
        direction_hit=direction_hit,
        verdict=verdict,
        notes=notes,
        mature=mature,
        bars_elapsed=bars_elapsed if bars_elapsed is not None else (eval_bars if mature else None),
    )


def _parse_iso_date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        # 2026-07-23T10:00:00Z | 2026-07-23
        normalized = text.replace("Z", "+00:00")
        if len(normalized) == 10:
            return datetime.fromisoformat(normalized).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _bar_close(bar: Any) -> float | None:
    for attr in ("close", "adj_close", "adjClose"):
        if hasattr(bar, attr):
            try:
                return float(getattr(bar, attr))
            except (TypeError, ValueError):
                continue
    if isinstance(bar, dict):
        for key in ("close", "adjClose", "adj_close"):
            if bar.get(key) is not None:
                try:
                    return float(bar[key])
                except (TypeError, ValueError):
                    continue
    return None


def _bar_ts(bar: Any) -> Any:
    if hasattr(bar, "timestamp"):
        return bar.timestamp
    if isinstance(bar, dict):
        return bar.get("timestamp") or bar.get("ts")
    return None


def find_anchor_bar_index(
    bars: Sequence[Any],
    *,
    decision_at: str | None,
    price_at_decision: float | None,
) -> int:
    """Índice de la barra de ancla (decisión). Barras deben ir ASC por tiempo."""
    if not bars:
        return -1

    decision_dt = _parse_iso_date(decision_at)
    if decision_dt is not None:
        best_i = 0
        best_delta = None
        for i, bar in enumerate(bars):
            bar_dt = _parse_iso_date(_bar_ts(bar))
            if bar_dt is None:
                continue
            # Ancla = última barra con ts <= decisión
            if bar_dt <= decision_dt:
                best_i = i
                best_delta = 0
            elif best_delta is None:
                best_i = i
                best_delta = abs((bar_dt - decision_dt).total_seconds())
        if best_delta is not None:
            return best_i

    if price_at_decision is not None:
        best_i = 0
        best_diff = None
        for i, bar in enumerate(bars):
            close = _bar_close(bar)
            if close is None:
                continue
            diff = abs(close - price_at_decision)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_i = i
        if best_diff is not None:
            return best_i

    return len(bars) - 1


def resolve_eval_price_from_bars(
    bars: Sequence[Any],
    *,
    horizon: str | None,
    decision_at: str | None = None,
    price_at_decision: float | None = None,
) -> dict[str, Any]:
    """
    Precio de evaluación en barra +N D1 desde el ancla de decisión.

    Returns dict: price, mature, barsElapsed, evalBars, notes
    """
    need = eval_bars_for_horizon(horizon)
    if not bars:
        return {
            "price": None,
            "mature": False,
            "barsElapsed": 0,
            "evalBars": need,
            "notes": "sin_barras_d1",
        }

    anchor = find_anchor_bar_index(
        bars, decision_at=decision_at, price_at_decision=price_at_decision
    )
    if anchor < 0:
        return {
            "price": None,
            "mature": False,
            "barsElapsed": 0,
            "evalBars": need,
            "notes": "sin_ancla",
        }

    available = len(bars) - 1 - anchor
    if available >= need:
        eval_idx = anchor + need
        return {
            "price": _bar_close(bars[eval_idx]),
            "mature": True,
            "barsElapsed": need,
            "evalBars": need,
            "notes": f"barra_+{need}_d1",
        }

    # Premature mark-to-market: última barra disponible
    last_price = _bar_close(bars[-1])
    return {
        "price": last_price,
        "mature": False,
        "barsElapsed": max(0, available),
        "evalBars": need,
        "notes": f"premature_mtm:{max(0, available)}/{need}",
    }


def build_manual_outcome(
    *,
    action: str,
    horizon: str | None,
    verdict: OutcomeVerdict,
    return_pct: float | None = None,
    price_at_decision: float | None = None,
    price_at_eval: float | None = None,
    direction_hit: bool | None = None,
    notes: str | None = None,
) -> SessionOutcome:
    eval_bars = eval_bars_for_horizon(horizon)
    if direction_hit is None and verdict in {"hit", "miss"}:
        direction_hit = verdict == "hit"
    return SessionOutcome(
        criteria_version=OUTCOME_CRITERIA_VERSION,
        source="manual",
        evaluated_at=_now_iso(),
        horizon=(horizon or "swing").lower(),
        eval_bars=eval_bars,
        recommended_action=action,
        price_at_decision=price_at_decision,
        price_at_eval=price_at_eval,
        return_pct=return_pct,
        direction_hit=direction_hit,
        verdict=verdict,
        notes=notes,
        mature=True,
        bars_elapsed=eval_bars,
    )


def attach_outcome_to_payload(
    payload: dict[str, Any],
    outcome: SessionOutcome,
    *,
    close: bool = True,
) -> dict[str, Any]:
    """Copia el payload Session con outcome (+ status closed)."""
    next_payload = dict(payload)
    next_payload["outcome"] = outcome.to_dict()
    if close:
        next_payload["status"] = "closed"
    return next_payload


def summarize_session_outcomes(
    payloads: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Agregado Learning v1.1 — no muta pesos. Distingue mature vs premature_mtm."""
    by_horizon: dict[str, dict[str, int]] = {}
    hits = misses = neutrals = skipped = invalid = 0
    scored = 0
    mature_hits = mature_misses = mature_scored = 0
    premature_scored = 0

    for payload in payloads:
        raw = payload.get("outcome")
        if not isinstance(raw, dict):
            continue
        verdict = str(raw.get("verdict") or "")
        hz = str(raw.get("horizon") or "unknown")
        mature = raw.get("mature")
        if mature is None:
            # Outcomes antiguos sin campo → tratar como maduros si no hay premature_mtm
            notes = str(raw.get("notes") or "")
            mature = "premature_mtm" not in notes
        else:
            mature = bool(mature)

        bucket = by_horizon.setdefault(
            hz,
            {
                "hit": 0,
                "miss": 0,
                "neutral": 0,
                "skipped": 0,
                "invalid": 0,
                "scored": 0,
                "matureScored": 0,
            },
        )
        if verdict == "hit":
            hits += 1
            scored += 1
            bucket["hit"] += 1
            bucket["scored"] += 1
            if mature:
                mature_hits += 1
                mature_scored += 1
                bucket["matureScored"] += 1
            else:
                premature_scored += 1
        elif verdict == "miss":
            misses += 1
            scored += 1
            bucket["miss"] += 1
            bucket["scored"] += 1
            if mature:
                mature_misses += 1
                mature_scored += 1
                bucket["matureScored"] += 1
            else:
                premature_scored += 1
        elif verdict == "neutral":
            neutrals += 1
            bucket["neutral"] += 1
        elif verdict == "skipped":
            skipped += 1
            bucket["skipped"] += 1
        elif verdict == "invalid":
            invalid += 1
            bucket["invalid"] += 1

    hit_rate = (hits / scored) if scored else None
    mature_hit_rate = (mature_hits / mature_scored) if mature_scored else None
    return {
        "criteriaVersion": OUTCOME_CRITERIA_VERSION,
        "sampleClosed": hits + misses + neutrals + skipped + invalid,
        "scored": scored,
        "hits": hits,
        "misses": misses,
        "neutrals": neutrals,
        "skipped": skipped,
        "invalid": invalid,
        "hitRate": round(hit_rate, 4) if hit_rate is not None else None,
        "matureScored": mature_scored,
        "matureHits": mature_hits,
        "matureMisses": mature_misses,
        "matureHitRate": round(mature_hit_rate, 4) if mature_hit_rate is not None else None,
        "prematureScored": premature_scored,
        "byHorizon": by_horizon,
        "note": "Usar matureHitRate para Learning; hitRate incluye premature_mtm.",
    }
