"""Stance engine v0 — dictamen diario Estudio (long-only, conservador).

Invariantes (ADR-022 / triage R3):
Gate VETO → no_trade; TOP stale → review_strategy; FA distress → nunca buy;
sell/reduce solo con largo abierto; fail-closed datos EOD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

Stance = Literal[
    "buy",
    "hold_watch",
    "overbought",
    "reduce",
    "sell_exit",
    "no_trade",
    "review_strategy",
]

GateStatus = Literal["PASS", "VETO", "WARNING"]

TOP_STALE_DAYS = 30
ENGINE_VERSION = "opinion_v1"


@dataclass(frozen=True, slots=True)
class StanceInput:
    has_eod_bar: bool
    allow_trading: bool
    has_top: bool
    top_updated_at: datetime | None
    top_stars: float | None
    io_score: float | None
    fa_distress: bool
    position_open: bool


@dataclass(frozen=True, slots=True)
class StanceResult:
    stance: Stance
    dictamen_stars: int
    reasons: list[str]
    gate_status: GateStatus


def _clamp_stars(value: int) -> int:
    return max(1, min(5, int(value)))


def map_io_to_stars(io_score: float | None) -> int:
    if io_score is None or not isinstance(io_score, (int, float)):
        return 3
    if io_score >= 80:
        return 5
    if io_score >= 65:
        return 4
    if io_score >= 45:
        return 3
    if io_score >= 30:
        return 2
    return 1


def is_top_stale(updated_at: datetime | None, *, now: datetime | None = None, days: int = TOP_STALE_DAYS) -> bool:
    if updated_at is None:
        return True
    ref = now or datetime.now(UTC)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    return (ref - updated_at).days > days


def compute_stance(inp: StanceInput, *, now: datetime | None = None) -> StanceResult:
    """Orden: EOD → Gate → TOP → FA distress → buy/hold/reduce (long-only)."""
    reasons: list[str] = []

    if not inp.has_eod_bar:
        return StanceResult("no_trade", 1, ["eod_data_stale"], "VETO")

    if not inp.allow_trading:
        return StanceResult("no_trade", 1, ["gate_veto"], "VETO")

    if not inp.has_top or is_top_stale(inp.top_updated_at, now=now):
        code = "stale_top" if inp.has_top else "no_valid_top"
        return StanceResult("review_strategy", 1, [code], "PASS")

    if inp.fa_distress:
        reasons.append("fa_distress")
        stars = min(3, map_io_to_stars(inp.io_score))
        if not inp.position_open:
            return StanceResult("no_trade", stars, reasons, "WARNING")
        return StanceResult("reduce", stars, reasons + ["position_open"], "WARNING")

    io = inp.io_score
    stars = map_io_to_stars(io)
    top_stars = float(inp.top_stars or 0)

    if not inp.position_open:
        if io is not None and io >= 80 and stars >= 4 and top_stars >= 3:
            return StanceResult(
                "buy",
                stars,
                ["strong_buy_signal", "top_high" if top_stars >= 4 else "top_medium", "io_high"],
                "PASS",
            )
        return StanceResult("hold_watch", stars, ["neutral_no_position", "io_medium"], "PASS")

    # Posición larga abierta
    reasons.append("position_open")
    if io is not None and io <= 30:
        reasons.extend(["overbought_or_exit", "io_low"])
        return StanceResult("sell_exit", stars, reasons, "PASS")
    if io is not None and io <= 45:
        reasons.extend(["overbought_or_exit", "io_low"])
        return StanceResult("reduce", stars, reasons, "PASS")
    if top_stars < 3:
        reasons.append("top_low")
        return StanceResult("overbought", stars, reasons, "PASS")
    return StanceResult("hold_watch", stars, reasons + ["holding_position"], "PASS")
